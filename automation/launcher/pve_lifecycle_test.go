package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPVESavedPlanTransfersNativeReview(t *testing.T) {
	for _, engine := range []string{"local", "dind"} {
		for _, operation := range []string{"apply", "verify"} {
			for _, missing := range []bool{false, true} {
				t.Run(engine+"/"+operation+map[bool]string{false: "/complete", true: "/missing-review"}[missing], func(t *testing.T) {
					directory := t.TempDir()
					bundle := filepath.Join(directory, "bundle")
					contents := map[string]string{"summary.json": "{}", "native-plan.json": "{\"resource_changes\":[]}", "review.json": "{\"vm_policy\":{}}\n", "inputs.tfvars.json": "{}", "snippets/manifest.json": "{}", "workspace/main.tf": "# retained root", "plan.tfplan": "native binary", "trust/api-ca.pem": "caller-owned CA"}
					for name, content := range contents {
						if missing && name == "review.json" {
							continue
						}
						path := filepath.Join(bundle, name)
						if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
							t.Fatal(err)
						}
						if err := os.WriteFile(path, []byte(content), 0600); err != nil {
							t.Fatal(err)
						}
					}
					taskDir := filepath.Join(directory, "task")
					if err := os.MkdirAll(filepath.Join(taskDir, "inputs"), 0700); err != nil {
						t.Fatal(err)
					}
					work := task{options: Options{Component: "pve", Operation: operation, Engine: engine, Companions: bundle, Plan: filepath.Join(bundle, "plan.tfplan")}, directory: taskDir, seed: "transfer"}
					remote := filepath.Join(directory, "remote-inputs")
					if engine == "dind" {
						t.Setenv("TEST_REMOTE_INPUTS", remote)
						script := `#!/bin/sh
[ "$1" = cp ] && [ "$2" = -a ] && [ "$4" = transfer:/inputs/saved ] || exit 1
cp -R "$3" "$TEST_REMOTE_INPUTS"
`
						if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
							t.Fatal(err)
						}
						t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
					}
					args, err := work.savedPlan()
					if missing {
						if err == nil || !strings.Contains(err.Error(), "required review.json") {
							t.Fatalf("missing review lost its admission diagnostic: %v", err)
						}
						if _, err := os.Stat(filepath.Join(taskDir, "inputs/saved")); !os.IsNotExist(err) {
							t.Fatal("missing review staged inputs before rejection")
						}
						return
					}
					if err != nil {
						t.Fatal(err)
					}
					if len(args) != 4 {
						t.Fatalf("missing saved arguments: %v", args)
					}
					transferred := filepath.Join(taskDir, "inputs/saved")
					if engine == "dind" {
						transferred = remote
					}
					for name, expected := range contents {
						actual, err := os.ReadFile(filepath.Join(transferred, name))
						if err != nil || string(actual) != expected {
							t.Fatalf("lost companion %s: %v", name, err)
						}
					}
				})
			}
		}
	}
}

func TestPVEPlanOutputCollectionRetainsTrust(t *testing.T) {
	directory := t.TempDir()
	source := filepath.Join(directory, "work/output")
	trust := filepath.Join(source, "plan/trust/api-ca.pem")
	if err := os.MkdirAll(filepath.Dir(trust), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(trust, []byte("caller-owned CA"), 0600); err != nil {
		t.Fatal(err)
	}
	output := filepath.Join(directory, "collected")
	if err := copyTaskTree(source, output, true); err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(filepath.Join(output, "plan/trust/api-ca.pem"))
	if err != nil || string(data) != "caller-owned CA" {
		t.Fatalf("collected plan lost trust: %v", err)
	}
	work := task{directory: filepath.Join(directory, "work"), retained: true}
	if err := work.cleanup(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(trust); err != nil {
		t.Fatalf("retained task lost CA: %v", err)
	}
}
