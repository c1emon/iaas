package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
)

var version = "development"

var executionIDPattern = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,128}$`)

type Options struct {
	Environment, RuntimeConfig, Engine, Component, Operation, Scenario, Scope string
	Output, Plan, Companions, ExecutionID                                     string
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "iaas:", err)
		var operationError *ExitError
		if errors.As(err, &operationError) {
			os.Exit(operationError.Code)
		}
		os.Exit(2)
	}
}

func run(args []string) error {
	if len(args) == 0 || args[0] == "--help" || args[0] == "help" {
		fmt.Println("iaas run --runtime-config runtime.json --environment environment.yml --engine local|dind --component NAME --operation NAME --output NEW_DIRECTORY [--scope NAME] [--scenario NAME] [--execution-id ID] [--plan FILE --companions DIRECTORY]")
		fmt.Println("iaas prepare --runtime-config runtime.json   # explicit image download")
		fmt.Println("iaas capabilities --runtime-config runtime.json")
		return nil
	}
	if args[0] == "version" || args[0] == "--version" {
		fmt.Println("iaas", version)
		return nil
	}
	command := args[0]
	if command != "run" && command != "prepare" && command != "capabilities" {
		return errors.New("unknown command; use iaas --help")
	}
	flags := flag.NewFlagSet(command, flag.ContinueOnError)
	var options Options
	flags.StringVar(&options.RuntimeConfig, "runtime-config", "", "caller-owned runtime selection JSON")
	flags.StringVar(&options.Environment, "environment", "", "caller-owned environment YAML")
	flags.StringVar(&options.Engine, "engine", "", "local or dind")
	flags.StringVar(&options.Component, "component", "", "explicit component")
	flags.StringVar(&options.Operation, "operation", "", "explicit operation")
	flags.StringVar(&options.Scenario, "scenario", "", "named scenario")
	flags.StringVar(&options.Scope, "scope", "", "explicit root, cluster or host scope")
	flags.StringVar(&options.Output, "output", "", "new output directory")
	flags.StringVar(&options.Plan, "plan", "", "selected native plan file")
	flags.StringVar(&options.Companions, "companions", "", "saved-plan companion directory")
	flags.StringVar(&options.ExecutionID, "execution-id", "", "caller-owned execution identity")
	if err := flags.Parse(args[1:]); err != nil {
		return err
	}
	if flags.NArg() != 0 || options.RuntimeConfig == "" {
		return errors.New("provide --runtime-config and named flags only")
	}
	configuration, err := readRuntime(options.RuntimeConfig)
	if err != nil {
		return err
	}
	if options.Component == "pve" && (options.Operation == "prepare-plan" || options.Operation == "apply-saved-plan") {
		return errors.New("prepare-plan/apply-saved-plan were removed; use PVE plan/apply")
	}
	docker := Docker{}
	if command == "prepare" {
		if _, err = docker.call("pull", "--platform", configuration.Platform, configuration.Image); err != nil {
			return errors.New("image preparation failed; check Docker/registry access")
		}
	}
	image, err := docker.resolveImage(configuration.Image)
	if err != nil {
		return err
	}
	capabilities, err := docker.capabilities(image, configuration.Platform)
	if err != nil {
		return err
	}
	if command != "run" {
		return json.NewEncoder(os.Stdout).Encode(map[string]any{"image": image, "capabilities": capabilities})
	}
	if options.Engine != "local" && options.Engine != "dind" {
		return errors.New("explicit --engine local or dind is required")
	}
	if options.Engine == "dind" && options.Component == "image" && (options.Operation == "read" || options.Operation == "clean") {
		return errors.New("image read/clean requires the local engine to preserve the caller-owned task workspace")
	}
	if options.Environment == "" || options.Output == "" {
		return errors.New("run requires --environment and --output")
	}
	effects, err := capabilities.operation(options.Component, options.Operation, configuration.Platform)
	if err != nil {
		return err
	}
	if effects.Network && options.Scope == "" {
		return errors.New("online operation requires explicit --scope")
	}
	options.Environment, err = filepath.Abs(options.Environment)
	if err != nil {
		return err
	}
	options.Output, err = filepath.Abs(options.Output)
	if err != nil {
		return err
	}
	if _, err = os.Lstat(options.Output); !os.IsNotExist(err) {
		return errors.New("output must be a new directory")
	}
	if options.Component == "pve" && (options.Operation == "apply" || options.Operation == "verify") &&
		(options.Plan == "" || options.Companions == "") {
		return errors.New("PVE apply/verify requires --plan and --companions")
	}
	if err := validateExecutionID(options); err != nil {
		return err
	}
	fmt.Printf("Operation %s/%s: network=%t state=%t infrastructure_write=%t\n", options.Component, options.Operation,
		effects.Network, effects.State, effects.InfrastructureWrite)
	return execute(options, configuration, image, effects, docker)
}

func validateExecutionID(options Options) error {
	mutation := (options.Component == "opnsense" && options.Operation == "apply") ||
		(options.Component == "pve" && options.Operation == "apply") ||
		(options.Component == "pve-template" && options.Operation == "apply") ||
		(options.Component == "image" && (options.Operation == "build" || options.Operation == "test" || options.Operation == "clean" || options.Operation == "read"))
	if options.ExecutionID == "" {
		if mutation {
			return errors.New("mutation apply requires --execution-id")
		}
		return nil
	}
	if !executionIDPattern.MatchString(options.ExecutionID) {
		return errors.New("execution-id must be a bounded identifier")
	}
	if !mutation {
		return errors.New("execution-id is only supported for apply")
	}
	if filepath.Base(options.Output) != options.ExecutionID {
		return errors.New("output directory basename must equal execution-id")
	}
	return nil
}
