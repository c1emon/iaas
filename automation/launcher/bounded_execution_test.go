package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestBoundedExecutionContractsAndReadOnlyInputs(t *testing.T) {
	for _, target := range [][2]string{{"pve-template", "accept"}, {"pve", "snippet-cleanup"}} {
		component, operation := target[0], target[1]
		prefix := "acceptance"
		if operation == "snippet-cleanup" {
			prefix = "snippet_cleanup"
		}
		c := Capabilities{InterfaceVersion: 1, SchemaVersions: []int{1}, Platforms: []string{"linux/amd64"},
			Operations: map[string]map[string]Effects{component: {operation: {Network: true, InfrastructureWrite: true}}}}
		if _, err := c.operation(component, operation, "linux/amd64"); err == nil {
			t.Fatal("missing contract accepted")
		}
		c.LifecycleVersions = map[string]map[string]int{component: {prefix + "_request": 1, prefix + "_result": 1}}
		c.ExecutionModes = map[string]map[string]map[string]Effects{component: {operation: {"start": {Network: true, InfrastructureWrite: true}, "observe": {Network: true}}}}
		if _, err := c.operation(component, operation, "linux/amd64"); err != nil {
			t.Fatal(err)
		}
		c.LifecycleVersions[component][prefix+"_request"] = 2
		if _, err := c.operation(component, operation, "linux/amd64"); err == nil {
			t.Fatal("unknown contract accepted")
		}
		root := t.TempDir()
		source := filepath.Join(root, "evidence")
		if err := os.Mkdir(source, 0700); err != nil {
			t.Fatal(err)
		}
		work := task{options: Options{Component: component, Operation: operation, Engine: "local"}, directory: root, mapping: map[string]string{}}
		if err := work.addInput(source); err != nil {
			t.Fatal(err)
		}
		if work.files[0].writable {
			t.Fatal("evidence is writable")
		}
		if !strings.Contains(strings.Join(work.mounts(true), " "), "src="+work.files[0].actual+",dst=/inputs/files/000000,readonly") {
			t.Fatal("local evidence not read-only")
		}
		work.options.Engine = "dind"
		work.inputVolume = "inputs"
		if !strings.Contains(strings.Join(work.mounts(true), " "), "type=volume,src=inputs,dst=/inputs,readonly") {
			t.Fatal("DinD evidence not read-only")
		}
		if err := validateExecutionID(Options{Component: component, Operation: operation, ExecutionID: "execution-1", Output: "/new/execution-1"}); err != nil {
			t.Fatal(err)
		}
	}
}

func TestSuccessfulObservationCannotHideCollectionFailure(t *testing.T) {
	directory := t.TempDir()
	log := filepath.Join(directory, "calls")
	t.Setenv("TASK_CALLS", log)
	script := `#!/bin/sh
echo "$1" >> "$TASK_CALLS"
case "$1" in
run) echo '{"status":"ready","credential_names":[],"execution_id":"original-1"}' ;;
start) echo '{"status":"success","output":"/task/output"}' ;;
inspect) echo 'false 0' ;;
cp) case "$3" in *-run:/task/output/.) exit 1;; esac ;;
esac
`
	if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
	options := Options{Engine: "dind", Environment: filepath.Join(directory, "entry.yml"), Output: filepath.Join(directory, "original-1"), Component: "pve-template", Operation: "accept", ExecutionID: "original-1"}
	err := execute(options, RuntimeConfig{1, "example/iaas:v1", "linux/amd64"}, "example/iaas@sha256:"+strings.Repeat("a", 64), Effects{Network: true}, Docker{})
	if err == nil || !strings.Contains(err.Error(), "retained") {
		t.Fatalf("observation collection failure was hidden: %v", err)
	}
	calls, _ := os.ReadFile(log)
	if strings.Contains(string(calls), "rm\n") {
		t.Fatal("observation evidence storage removed")
	}
}
