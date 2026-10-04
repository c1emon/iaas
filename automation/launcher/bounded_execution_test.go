package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestBoundedExecutionTransferPreservesFrozenDeadlines(t *testing.T) {
	// Exercise the real local snapshot and Docker archive transfer paths with
	// synthetic transport; no real daemon or facility qualification is claimed.
	for _, operation := range []string{"accept", "recover"} {
		for _, engine := range []string{"local", "dind"} {
			t.Run(operation+"/"+engine, func(t *testing.T) {
				root := t.TempDir()
				source := filepath.Join(root, "request.json")
				example := "../../docs/examples/pve-acceptance/acceptance-request.json"
				if operation == "recover" {
					example = "../../docs/examples/recovery/recovery-request.json"
				}
				contents, err := os.ReadFile(example)
				if err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(source, contents, 0600); err != nil {
					t.Fatal(err)
				}
				work := task{options: Options{Component: "pve-template", Operation: operation, Engine: engine}, directory: root, seed: "transfer", mapping: map[string]string{}}
				transferred := filepath.Join(root, "inputs/files/000000")
				if engine == "dind" {
					transferred = filepath.Join(root, "remote-request.json")
					t.Setenv("DEADLINE_TRANSFER_TARGET", transferred)
					script := "#!/bin/sh\n[ \"$1\" = cp ] && [ \"$2\" = -a ] && [ \"$4\" = transfer:/inputs/files/000000 ] || exit 1\ncp \"$3\" \"$DEADLINE_TRANSFER_TARGET\"\n"
					if err := os.WriteFile(filepath.Join(root, "docker"), []byte(script), 0700); err != nil {
						t.Fatal(err)
					}
					t.Setenv("PATH", root+string(os.PathListSeparator)+os.Getenv("PATH"))
				} else if err := os.MkdirAll(filepath.Dir(transferred), 0700); err != nil {
					t.Fatal(err)
				}
				if err := work.addInput(source); err != nil {
					t.Fatal(err)
				}
				actual, err := os.ReadFile(transferred)
				if err != nil || !bytes.Equal(actual, contents) {
					t.Fatalf("frozen request bytes changed during %s transfer: %v", engine, err)
				}
			})
		}
	}
}

func TestBoundedExecutionContractsAndReadOnlyInputs(t *testing.T) {
	for _, target := range [][2]string{{"pve-template", "accept"}, {"pve-template", "recover"}, {"pve", "snippet-cleanup"}} {
		component, operation := target[0], target[1]
		prefix := "acceptance"
		requestVersion, resultVersion := 3, 4
		if operation == "recover" {
			prefix, requestVersion, resultVersion = "recovery", 1, 2
		}
		if operation == "snippet-cleanup" {
			prefix = "snippet_cleanup"
			requestVersion, resultVersion = 2, 3
		}
		c := Capabilities{InterfaceVersion: 1, SchemaVersions: []int{1}, Platforms: []string{"linux/amd64"},
			Operations: map[string]map[string]Effects{component: {operation: {Network: true, InfrastructureWrite: true}}}}
		if _, err := c.operation(component, operation, "linux/amd64"); err == nil {
			t.Fatal("missing contract accepted")
		}
		c.LifecycleVersions = map[string]map[string]int{component: {prefix + "_request": requestVersion, prefix + "_result": resultVersion, prefix + "_preview": 2, "one_shot_execution_admission": 2}}
		c.ExecutionModes = map[string]map[string]map[string]Effects{component: {operation: {"start": {Network: true, InfrastructureWrite: true}, "observe": {}}}}
		if _, err := c.operation(component, operation, "linux/amd64"); err == nil {
			t.Fatal("missing absolute deadline capability accepted")
		}
		c.OperationCapabilities = map[string]map[string]map[string]bool{component: {operation: {"absolute_deadlines": true}}}
		if _, err := c.operation(component, operation, "linux/amd64"); err != nil {
			t.Fatal(err)
		}
		c.LifecycleVersions[component][prefix+"_request"] = 0
		if _, err := c.operation(component, operation, "linux/amd64"); err == nil {
			t.Fatal("old contract accepted")
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

func TestAcceptanceRecoveryPlanCapabilityGates(t *testing.T) {
	c := Capabilities{
		LifecycleVersions: map[string]map[string]int{"pve-template": {
			"acceptance_request": 3, "acceptance_result": 4, "acceptance_preview": 2,
			"recovery_request": 1, "recovery_result": 2, "recovery_preview": 2}},
		OperationCapabilities: map[string]map[string]map[string]bool{"pve-template": {
			"plan": {"accept": true, "recover": true, "absolute_deadlines": true}, "check": {"accept": true}}},
	}
	for _, action := range []string{"accept", "recover"} {
		if err := c.selectedAction("pve-template", "plan", action); err != nil {
			t.Fatal(err)
		}
		c.OperationCapabilities["pve-template"]["plan"][action] = false
		if err := c.selectedAction("pve-template", "plan", action); err == nil {
			t.Fatal("missing action capability accepted")
		}
		c.OperationCapabilities["pve-template"]["plan"][action] = true
	}
	if err := c.selectedAction("pve-template", "check", "recover"); err == nil {
		t.Fatal("offline recovery check advertised")
	}
	c.LifecycleVersions["pve-template"]["acceptance_request"] = 2
	if err := c.selectedAction("pve-template", "plan", "accept"); err == nil {
		t.Fatal("old acceptance request accepted")
	}
}

func TestRecoveryObserveHasNoNetworkOrCredentialsInBothEngines(t *testing.T) {
	for _, engine := range []string{"local", "dind"} {
		t.Run(engine, func(t *testing.T) {
			directory := t.TempDir()
			log := filepath.Join(directory, "calls")
			t.Setenv("RECOVERY_CALLS", log)
			t.Setenv("PVE_API_TOKEN", "must-not-forward")
			t.Setenv("AWS_SECRET_ACCESS_KEY", "must-not-forward")
			t.Setenv("HTTP_PROXY", "bad proxy ignored offline")
			script := `#!/bin/sh
printf '%s\n' "$*" >> "$RECOVERY_CALLS"
case "$1" in
run) echo '{"status":"ready","credential_names":[],"execution_id":"recovery-1","execution_mode":"observe","effects":{"network":false,"state":false,"infrastructure_write":false,"local_write":true}}' ;;
create)
 for arg in "$@"; do
  case "$arg" in type=bind,src=*,dst=/task) task_path=${arg#type=bind,src=}; task_path=${task_path%,dst=/task}; mkdir -p "$task_path/output" ;; esac
 done ;;
start) echo '{"status":"success"}' ;;
inspect) echo 'false 0' ;;
esac
`
			if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
				t.Fatal(err)
			}
			t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
			options := Options{Engine: engine, Component: "pve-template", Operation: "recover", Output: filepath.Join(directory, "new-parent", "recovery-1"), ExecutionID: "recovery-1"}
			if err := validateExecutionID(options); err != nil {
				t.Fatal(err)
			}
			if err := execute(options, RuntimeConfig{Platform: "linux/amd64"}, "fixture", Effects{Network: true, InfrastructureWrite: true}, Docker{}); err != nil {
				t.Fatal(err)
			}
			calls, _ := os.ReadFile(log)
			for _, line := range strings.Split(string(calls), "\n") {
				if strings.HasPrefix(line, "create ") && strings.Contains(line, "-run ") {
					if !strings.Contains(line, "--network none") || strings.Contains(line, "--env PVE_API_TOKEN") || strings.Contains(line, "--env AWS_") {
						t.Fatal("observe forwarded network or credentials")
					}
				}
			}
		})
	}
}
