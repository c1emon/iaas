//go:build runtime_integration

package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// The Python regression creates a genuine frozen bundle. Only the Docker mount
// boundary is replaced; savedPlan and Python admission execute without mocks.
func TestTransferredSavedPlanRealAdmission(t *testing.T) {
	bundle := os.Getenv("IAAS_TEST_SAVED_BUNDLE")
	if bundle == "" {
		t.Skip("requires the generated bundle from the Python saved-plan regression")
	}
	for _, operation := range []string{"apply", "verify"} {
		t.Run(operation, func(t *testing.T) {
			directory := t.TempDir()
			if err := os.Mkdir(filepath.Join(directory, "inputs"), 0700); err != nil {
				t.Fatal(err)
			}
			work := task{options: Options{Component: "pve", Operation: operation, Engine: "local",
				Companions: bundle, Plan: filepath.Join(bundle, "plan.tfplan")}, directory: directory}
			if _, err := work.savedPlan(); err != nil {
				t.Fatal(err)
			}
			repo, _ := filepath.Abs("../..")
			script := `
import sys
from pathlib import Path
from iaas.runtime_execution.plans import admit_plan
bundle = Path(sys.argv[1])
admit_plan(bundle / 'plan.tfplan', bundle, {}, None)
`
			staged := filepath.Join(directory, "inputs/saved")
			command := exec.Command("uv", "run", "--no-sync", "python", "-c", script, staged)
			if image := os.Getenv("IAAS_TEST_RUNTIME_IMAGE"); image != "" {
				command = exec.Command("docker", "run", "--rm", "--pull", "never", "--network", "none",
					"--mount", "type=bind,src="+staged+",dst=/saved,readonly", "--entrypoint", "python",
					image, "-c", script, "/saved")
			}
			command.Dir = repo
			command.Env = append(os.Environ(), "PYTHONPATH="+filepath.Join(repo, "src"))
			if output, err := command.CombinedOutput(); err != nil {
				t.Fatalf("transferred bundle admission failed: %v %s", err, output)
			}
		})
	}
}

// Exercise the real Python entrypoint with the argument vector produced by
// Go, including discovery before savedPlan stages any native artifacts.
func TestPVELauncherDiscoveryWithRealRuntime(t *testing.T) {
	repo, err := filepath.Abs("../..")
	if err != nil {
		t.Fatal(err)
	}
	for _, operation := range []string{"apply", "verify"} {
		t.Run(operation, func(t *testing.T) {
			directory := t.TempDir()
			files := map[string]string{}
			for _, name := range []string{"backend", "execution_admission", "state_admission"} {
				path := filepath.Join(directory, name+".json")
				if err := os.WriteFile(path, []byte("{}"), 0600); err != nil {
					t.Fatal(err)
				}
				files[name] = path
			}
			entry := filepath.Join(directory, "environment.json")
			inputs := map[string]string{
				"cluster": filepath.Join(repo, "tests/fixtures/runtime/pve-cluster.yml"),
				"vms":     filepath.Join(repo, "tests/fixtures/runtime/vms.yml"),
			}
			data, _ := json.Marshal(map[string]any{"schema_version": 1, "environment": "synthetic", "components": map[string]any{"pve": map[string]any{"inputs": inputs, "files": files}}})
			if err := os.WriteFile(entry, data, 0600); err != nil {
				t.Fatal(err)
			}
			work := task{options: Options{Environment: entry, Component: "pve", Operation: operation}, image: "synthetic@sha256:" + strings.Repeat("a", 64)}
			if operation == "apply" {
				work.options.ExecutionID = "execution-42"
			}
			args := work.runtimeArgs()[1:]
			// The Docker mount translation is the only replaced boundary. All runtime
			// selection and validation executes unmocked against local fixture files.
			for i, arg := range args {
				if arg == "--input-map" {
					args = append(args[:i], args[i+2:]...)
					break
				}
			}
			run := func(extra ...string) ([]byte, error) {
				command := exec.Command("uv", append([]string{"run", "--no-sync", "python", "-m", "iaas.runtime_execution"}, append(append([]string{}, args...), extra...)...)...)
				command.Dir = repo
				command.Env = append(os.Environ(), "PYTHONPATH="+filepath.Join(repo, "src"))
				return command.CombinedOutput()
			}
			output, err := run("--discover")
			if err != nil {
				t.Fatalf("launcher discovery rejected by runtime: %v %s", err, output)
			}
			var found discovery
			if err := json.Unmarshal(output, &found); err != nil || found.Status != "ready" || found.ExecutionID != work.options.ExecutionID {
				t.Fatalf("unexpected discovery: %s (%v)", output, err)
			}
			outputPath := filepath.Join(directory, "output")
			output, err = run("--output", outputPath)
			if err == nil || !strings.Contains(string(output), "requires --plan and --companions") {
				t.Fatalf("execution did not reject absent bundle: %v %s", err, output)
			}
			if _, err := os.Stat(outputPath); !os.IsNotExist(err) {
				t.Fatalf("rejected execution created output: %v", err)
			}
		})
	}
}
