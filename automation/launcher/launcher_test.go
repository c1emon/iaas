package main

import (
	"encoding/csv"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestSelectionAndOperationBoundary(t *testing.T) {
	valid := RuntimeConfig{1, "example/iaas:v1.2.3", "linux/amd64"}
	if err := valid.validate(); err != nil {
		t.Fatal(err)
	}
	for _, image := range []string{"example/iaas", "example/iaas:latest", "example/iaas@sha256:bad", "-bad:v1"} {
		invalid := valid
		invalid.Image = image
		if invalid.validate() == nil {
			t.Fatalf("accepted %s", image)
		}
	}
	valid.Platform = "linux/arm64"
	if valid.validate() == nil {
		t.Fatal("unqualified platform accepted")
	}
	caps := Capabilities{1, []int{1}, []string{"linux/amd64"}, map[string]map[string]Effects{"k3s": {"snapshot": {Network: true, InfrastructureWrite: true}}}}
	effect, err := caps.operation("k3s", "snapshot")
	if err != nil || !effect.InfrastructureWrite {
		t.Fatal("snapshot must advertise remote writes")
	}
	if _, err := caps.operation("k3s", "destroy"); err == nil {
		t.Fatal("unlisted command accepted")
	}
}

func TestExplicitInputAndPortableArtifacts(t *testing.T) {
	directory := t.TempDir()
	input := filepath.Join(directory, "caller, files")
	if err := os.Mkdir(input, 0700); err != nil {
		t.Fatal(err)
	}
	key := filepath.Join(input, "protected key")
	if err := os.WriteFile(key, []byte("synthetic"), 0600); err != nil {
		t.Fatal(err)
	}
	taskDir := filepath.Join(directory, "task")
	if err := os.Mkdir(taskDir, 0700); err != nil {
		t.Fatal(err)
	}
	work := task{options: Options{Engine: "local"}, directory: taskDir, mapping: map[string]string{}}
	if err := work.initialize(); err != nil {
		t.Fatal(err)
	}
	if err := work.addInput(key); err != nil {
		t.Fatal(err)
	}
	if err := work.addInput(key); err == nil {
		t.Fatal("duplicate discovery must stop")
	}
	if err := work.addInput(filepath.Join(input, "absent")); err == nil {
		t.Fatal("missing input accepted")
	}
	fields, err := csv.NewReader(strings.NewReader(bind(key, "/input", true)[1])).Read()
	if err != nil || fields[1] != "src="+key {
		t.Fatal("bind path was not preserved")
	}
	if err := copyTree(input, filepath.Join(directory, "export")); err != nil {
		t.Fatal(err)
	}
	info, _ := os.Stat(filepath.Join(directory, "export/protected key"))
	if info.Mode().Perm() != 0600 {
		t.Fatal("private file permissions changed")
	}
	if err := os.Symlink(key, filepath.Join(input, "link")); err != nil {
		t.Fatal(err)
	}
	if err := copyTree(input, filepath.Join(directory, "reject")); err == nil {
		t.Fatal("artifact symlink accepted")
	}
}

func TestRealContainerExitCodeAndPrivateDockerErrors(t *testing.T) {
	directory := t.TempDir()
	// A command-level substitute tests the attachment protocol without Docker.
	script := "#!/bin/sh\ncase \"$1\" in\nstart) echo '{\"status\":\"failed\"}'; exit 17;;\ninspect) echo 'false 17';;\n*) echo synthetic-private-value >&2; exit 1;;\nesac\n"
	if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
	d := Docker{}
	_, code, err := d.attached("synthetic-task", make(chan os.Signal, 1))
	if err != nil || code != 17 {
		t.Fatalf("exit code %d: %v", code, err)
	}
	_, err = d.call("cp", "synthetic-source", "synthetic-destination")
	if err == nil || strings.Contains(err.Error(), "synthetic-private-value") {
		t.Fatal("raw Docker error escaped")
	}
}

func TestCancellationStopsContainerBeforeReadingExit(t *testing.T) {
	directory := t.TempDir()
	t.Setenv("TASK_STOP", filepath.Join(directory, "stopped"))
	script := "#!/bin/sh\ncase \"$1\" in\nstart) while [ ! -f \"$TASK_STOP\" ]; do sleep .02; done; exit 143;;\nstop) touch \"$TASK_STOP\";;\ninspect) test -f \"$TASK_STOP\" || exit 1; echo 'false 143';;\nesac\n"
	if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
	interrupted := make(chan os.Signal, 1)
	go func() { time.Sleep(50 * time.Millisecond); interrupted <- os.Interrupt }()
	_, code, err := (Docker{}).attached("synthetic", interrupted)
	if err != nil || code != 143 {
		t.Fatalf("cancellation exit %d: %v", code, err)
	}
}

func TestFailedCollectionDoesNotCleanUniqueStorage(t *testing.T) {
	directory := t.TempDir()
	log := filepath.Join(directory, "calls")
	t.Setenv("TASK_CALLS", log)
	script := `#!/bin/sh
echo "$1" >> "$TASK_CALLS"
case "$1" in
run) echo '{"status":"ready","credential_names":[]}' ;;
start) echo '{"status":"failed","output":"/task/output"}' ;;
inspect) echo 'false 17' ;;
cp) case "$3" in *-run:/task/output/.) exit 1;; esac ;;
esac
`
	if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
	options := Options{Engine: "dind", Environment: filepath.Join(directory, "environment.yml"), Output: filepath.Join(directory, "result"), Component: "pve", Operation: "plan"}
	err := execute(options, RuntimeConfig{1, "example/iaas:v1", "linux/amd64"}, "example/iaas@sha256:"+strings.Repeat("a", 64), Effects{Network: true, State: true}, Docker{})
	if err == nil || !strings.Contains(err.Error(), "retained") {
		t.Fatalf("failed collection was not reported: %v", err)
	}
	calls, _ := os.ReadFile(log)
	if strings.Contains(string(calls), "rm\n") {
		t.Fatal("unique task storage was removed")
	}
	retained, _ := filepath.Glob(filepath.Join(directory, ".iaas-task-*"))
	if len(retained) != 1 {
		t.Fatal("local recovery metadata was not retained")
	}
}

func TestCollectionPreservesNativeLinksWithoutFollowingThem(t *testing.T) {
	directory := t.TempDir()
	source := filepath.Join(directory, "source")
	if err := os.Mkdir(source, 0700); err != nil {
		t.Fatal(err)
	}
	outstanding := filepath.Join(directory, "original")
	if err := os.WriteFile(outstanding, []byte("unchanged"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outstanding, filepath.Join(source, "launcher-result.json")); err != nil {
		t.Fatal(err)
	}
	destination := filepath.Join(directory, "collected")
	if err := copyTaskTree(source, destination, true); err != nil {
		t.Fatal(err)
	}
	if err := writeNewPrivate(filepath.Join(destination, "launcher-result.json"), []byte("replacement")); err == nil {
		t.Fatal("collection followed a link")
	}
	data, _ := os.ReadFile(outstanding)
	if string(data) != "unchanged" {
		t.Fatal("source overwritten during result recording")
	}
}

func TestCachedRetagUsesExistingRepoDigest(t *testing.T) {
	directory := t.TempDir()
	digest := "original/image@sha256:" + strings.Repeat("a", 64)
	script := "#!/bin/sh\necho '[\"" + digest + "\"]'\n"
	if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
	resolved, err := (Docker{}).resolveImage("local-alias:v1")
	if err != nil || resolved != digest {
		t.Fatalf("invented an unavailable digest: %s %v", resolved, err)
	}
}
