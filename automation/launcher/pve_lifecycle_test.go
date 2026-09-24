package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestPVESavedPlanTransfersNativeReview(t *testing.T) {
	for _, operation := range []string{"apply", "verify"} {
		for _, missing := range []bool{false, true} {
			t.Run(operation+map[bool]string{false: "/complete", true: "/missing-review"}[missing], func(t *testing.T) {
				directory := t.TempDir()
				bundle := filepath.Join(directory, "bundle")
				contents := map[string]string{"summary.json": "{}", "native-plan.json": "{\"resource_changes\":[]}", "inputs.tfvars.json": "{}", "snippets/manifest.json": "{}", "workspace/main.tf": "# retained root", "plan.tfplan": "native binary"}
				for name, content := range contents {
					if missing && name == "native-plan.json" {
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
				work := task{options: Options{Component: "pve", Operation: operation, Engine: "local", Companions: bundle, Plan: filepath.Join(bundle, "plan.tfplan")}, directory: taskDir}
				args, err := work.savedPlan()
				if missing {
					if err == nil {
						t.Fatal("missing native review accepted")
					}
					return
				}
				if err != nil {
					t.Fatal(err)
				}
				if len(args) != 4 {
					t.Fatalf("missing saved arguments: %v", args)
				}
				for name, expected := range contents {
					actual, err := os.ReadFile(filepath.Join(taskDir, "inputs/saved", name))
					if err != nil || string(actual) != expected {
						t.Fatalf("lost companion %s: %v", name, err)
					}
				}
			})
		}
	}
}
