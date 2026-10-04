//go:build runtime_integration

package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

// Use the real runtime declaration, not a second copy of its version fixture.
// CI already runs this tag in the launcher job after uv sync.
func TestLauncherAcceptsRealRuntimeCapabilities(t *testing.T) {
	repo, err := filepath.Abs("../..")
	if err != nil {
		t.Fatal(err)
	}
	command := exec.Command("uv", "run", "--no-sync", "python", "-m", "iaas.runtime_execution", "capabilities")
	command.Dir = repo
	command.Env = append(os.Environ(), "PYTHONPATH="+filepath.Join(repo, "src"))
	output, err := command.Output()
	if err != nil {
		t.Fatalf("real runtime capabilities failed: %v", err)
	}
	var c Capabilities
	if err := json.Unmarshal(output, &c); err != nil {
		t.Fatal(err)
	}
	for component, operations := range c.Operations {
		for operation, expected := range operations {
			t.Run(component+"/"+operation, func(t *testing.T) {
				for _, platform := range c.Platforms {
					actual, err := c.operation(component, operation, platform)
					if err != nil || actual != expected {
						t.Fatalf("launcher rejected runtime operation/effects: %v", err)
					}
				}
				for _, action := range []string{"accept", "recover"} {
					if c.OperationCapabilities[component][operation][action] {
						if err := c.selectedAction(component, operation, action); err != nil {
							t.Fatal(err)
						}
					}
				}
			})
		}
	}
	for _, name := range proxyNames {
		t.Setenv(name, "")
	}
	t.Setenv("HTTP_PROXY", "http://proxy.invalid:8080")
	if err := proxyAdmission(c, Effects{Network: true}); err != nil {
		t.Fatal(err)
	}
	// Every gated field must still fail closed when missing or outdated.
	for _, target := range []struct{ component, operation, prefix string }{
		{"pve-template", "accept", "acceptance"},
		{"pve-template", "recover", "recovery"},
		{"pve", "snippet-cleanup", "snippet_cleanup"},
	} {
		fields := []string{target.prefix + "_request", target.prefix + "_result"}
		if target.component == "pve-template" {
			fields = append(fields, target.prefix+"_preview", "one_shot_execution_admission")
		}
		for _, field := range fields {
			versions := c.LifecycleVersions[target.component]
			current := versions[field]
			for _, invalid := range []int{0, current - 1} {
				versions[field] = invalid
				if _, err := c.operation(target.component, target.operation, c.Platforms[0]); err == nil {
					t.Fatalf("execution accepted stale/missing %s/%s", target.component, field)
				}
				if target.component == "pve-template" && field != "one_shot_execution_admission" {
					for _, operation := range []string{"check", "plan"} {
						if c.OperationCapabilities[target.component][operation][target.operation] {
							if err := c.selectedAction(target.component, operation, target.operation); err == nil {
								t.Fatalf("%s accepted stale/missing %s", operation, field)
							}
						}
					}
				}
			}
			versions[field] = current
		}
	}
}
