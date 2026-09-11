package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
)

type discovery struct {
	Status          string   `json:"status"`
	Path            string   `json:"path"`
	CredentialNames []string `json:"credential_names"`
}

func (t *task) runtimeArgs() []string {
	args := []string{"runtime", "--environment", t.options.Environment, "--input-map", "/inputs/map.json",
		"--component", t.options.Component, "--operation", t.options.Operation, "--image-digest", t.image}
	if t.options.Scenario != "" {
		args = append(args, "--scenario", t.options.Scenario)
	}
	if t.options.Scope != "" {
		args = append(args, "--scope", t.options.Scope)
	}
	return args
}

func (t *task) discover() (discovery, error) {
	var response discovery
	if err := t.writeMap(); err != nil {
		return response, err
	}
	args := []string{"run", "--rm", "--pull", "never", "--network", "none"}
	args = append(args, t.mounts(false)...)
	args = append(args, t.image)
	args = append(args, t.runtimeArgs()...)
	args = append(args, "--discover")
	data, err := t.docker.call(args...)
	if json.Unmarshal(data, &response) != nil {
		return response, errors.New("input discovery failed; check daemon path visibility and image compatibility")
	}
	if response.Status == "input-required" {
		return response, nil
	}
	if err != nil || response.Status != "ready" {
		return response, errors.New("selected configuration could not be validated for this operation")
	}
	return response, nil
}

func (t *task) savedPlan() ([]string, error) {
	if t.options.Operation != "apply-saved-plan" {
		return nil, nil
	}
	bundle, err := filepath.EvalSymlinks(t.options.Companions)
	if err != nil {
		return nil, errors.New("saved companion directory is unavailable")
	}
	for _, name := range []string{"summary.json", "inputs.tfvars.json", "snippets/manifest.json"} {
		if info, err := os.Stat(filepath.Join(bundle, name)); err != nil || !info.Mode().IsRegular() {
			return nil, errors.New("saved companion artifacts are incomplete")
		}
	}
	staged := filepath.Join(t.directory, "inputs/saved")
	if err := os.Mkdir(staged, 0700); err != nil {
		return nil, err
	}
	// Only the saved-plan contract's files/directories are transferred, not the
	// arbitrary parent directory of a selected native plan.
	for _, name := range []string{"summary.json", "inputs.tfvars.json", "snippets", "workspace", "dependencies.tar.gz"} {
		source := filepath.Join(bundle, name)
		if _, err := os.Stat(source); os.IsNotExist(err) && name == "dependencies.tar.gz" {
			continue
		}
		if err := copyTree(source, filepath.Join(staged, name)); err != nil {
			return nil, err
		}
	}
	if err := copyTree(t.options.Plan, filepath.Join(staged, "plan.tfplan")); err != nil {
		return nil, err
	}
	if t.options.Engine == "dind" {
		if _, err := t.docker.call("cp", "-a", staged, t.seed+":/inputs/saved"); err != nil {
			return nil, err
		}
	}
	return []string{"--plan", "/inputs/saved/plan.tfplan", "--companions", "/inputs/saved"}, nil
}

func execute(options Options, configuration RuntimeConfig, image string, effects Effects, docker Docker) (resultError error) {
	if err := os.MkdirAll(filepath.Dir(options.Output), 0700); err != nil {
		return err
	}
	directory, err := os.MkdirTemp(filepath.Dir(options.Output), ".iaas-task-")
	if err != nil {
		return err
	}
	t := task{options: options, configuration: configuration, image: image, docker: docker,
		directory: directory, name: "iaas-" + strings.TrimPrefix(filepath.Base(directory), ".iaas-task-"), mapping: map[string]string{}}
	defer func() {
		if t.retained {
			fmt.Fprintf(os.Stderr, "Task resources retained: %s (local metadata %s)\n", t.name, t.directory)
		} else if cleanupError := t.cleanup(); cleanupError != nil {
			fmt.Fprintf(os.Stderr, "Task cleanup incomplete: %s (local metadata %s)\n", t.name, t.directory)
			if resultError == nil {
				resultError = cleanupError
			}
		}
	}()
	cancelled := make(chan os.Signal, 1)
	signal.Notify(cancelled, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(cancelled)
	if err := t.initialize(); err != nil {
		return err
	}
	var ready discovery
	for {
		select {
		case <-cancelled:
			return &ExitError{130}
		default:
		}
		ready, err = t.discover()
		if err != nil {
			return err
		}
		if ready.Status == "ready" {
			break
		}
		if err := t.addInput(ready.Path); err != nil {
			return err
		}
	}
	extra, err := t.savedPlan()
	if err != nil {
		return err
	}
	var credentials []string
	// File-valued AWS channels are explicit inputs too. Rewrite only their
	// client path, never a credential value into the Docker command line.
	childEnvironment := os.Environ()
	for _, name := range ready.CredentialNames {
		if strings.HasPrefix(name, "OP_") {
			return errors.New("image requested an unsupported bootstrap credential")
		}
		value, exists := os.LookupEnv(name)
		if !exists {
			continue
		}
		if name == "AWS_SHARED_CREDENTIALS_FILE" || name == "AWS_SHARED_CONFIG_FILE" || name == "AWS_CA_BUNDLE" || name == "AWS_WEB_IDENTITY_TOKEN_FILE" {
			logical, err := filepath.Abs(value)
			if err != nil {
				return err
			}
			if _, ok := t.mapping[logical]; !ok {
				if err := t.addInput(logical); err != nil {
					return err
				}
			}
			childEnvironment = replaceEnvironment(childEnvironment, name, t.mapping[logical])
		}
		credentials = append(credentials, "--env", name)
	}
	// New file-valued environment inputs must be reflected in local mounts.
	// Assemble mounts after gathering them, rather than creating empty paths.
	base := []string{"create", "--name", t.name + "-run", "--pull", "never"}
	if !effects.Network {
		base = append(base, "--network", "none")
	}
	base = append(base, t.mounts(true)...)
	base = append(base, credentials...)
	if err := t.writeMap(); err != nil {
		return err
	}
	base = append(base, image)
	base = append(base, t.runtimeArgs()...)
	base = append(base, "--output", "/task/output")
	base = append(base, extra...)
	select {
	case <-cancelled:
		return &ExitError{130}
	default:
	}
	create := exec.Command("docker", base...)
	create.Env = childEnvironment
	if err := create.Run(); err != nil {
		return errors.New("execution container creation failed")
	}
	t.container = t.name + "-run"
	select {
	case <-cancelled:
		return &ExitError{130}
	default:
	}
	data, code, err := docker.attached(t.container, cancelled)
	if err != nil {
		t.retained = true
		return err
	}
	var report struct {
		Status        string `json:"status"`
		Output        string `json:"output"`
		RetainStorage bool   `json:"retain_storage"`
		Reason        string `json:"reason"`
	}
	validReport := json.Unmarshal(data, &report) == nil
	// Incomplete recovery cannot be upgraded to complete by a successful copy.
	t.retained = report.RetainStorage || !validReport
	if err := os.Mkdir(options.Output, 0700); err != nil {
		t.retained = true
		return errors.New("output destination changed or cannot be created; execution results retained")
	}
	if options.Engine == "local" {
		// Native provider caches contain symlinks. Preserve links without
		// following them; saved-plan input admission remains stricter.
		err = copyTaskTree(filepath.Join(t.directory, "work/output"), options.Output, true)
	} else {
		_, err = docker.call("cp", "-a", t.container+":/task/output/.", options.Output)
	}
	if err != nil {
		t.retained = true
		return errors.New("result collection failed; container and task storage retained")
	}
	if err := writeNewPrivate(filepath.Join(options.Output, "launcher-result.json"), data); err != nil {
		t.retained = true
		return errors.New("result recording failed; task storage retained")
	}
	provenance, _ := json.Marshal(inputProvenance(options.Environment))
	if err := writeNewPrivate(filepath.Join(options.Output, "input-provenance.json"), provenance); err != nil {
		t.retained = true
		return errors.New("input provenance recording failed; task storage retained")
	}
	fmt.Printf("Results: %s\n", options.Output)
	if code != 0 {
		if validReport && report.Reason != "" {
			fmt.Fprintln(os.Stderr, report.Reason)
		}
		return &ExitError{code}
	}
	if !validReport || report.Status != "success" {
		return errors.New("runtime did not confirm successful execution")
	}
	return nil
}

func replaceEnvironment(environment []string, name, value string) []string {
	result := make([]string, 0, len(environment)+1)
	for _, entry := range environment {
		if !strings.HasPrefix(entry, name+"=") {
			result = append(result, entry)
		}
	}
	return append(result, name+"="+value)
}
