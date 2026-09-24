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
			data, _ := json.Marshal(map[string]any{"schema_version": 1, "environment": "synthetic", "components": map[string]any{"pve": map[string]any{"inputs": map[string]any{}, "files": files}}})
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
