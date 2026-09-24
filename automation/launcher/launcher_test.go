package main

import (
	"encoding/csv"
	"os"
	"path/filepath"
	"strings"
	"syscall"
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
	if err := valid.validate(); err != nil {
		t.Fatal(err)
	}
	valid.Platform = "linux/riscv64"
	if valid.validate() == nil {
		t.Fatal("unqualified platform accepted")
	}
	caps := Capabilities{1, []int{1}, []string{"linux/amd64"}, map[string]map[string]Effects{"k3s": {"snapshot": {Network: true, InfrastructureWrite: true}}}}
	effect, err := caps.operation("k3s", "snapshot", "linux/amd64")
	if err != nil || !effect.InfrastructureWrite {
		t.Fatal("snapshot must advertise remote writes")
	}
	if _, err := caps.operation("k3s", "destroy", "linux/amd64"); err == nil {
		t.Fatal("unlisted command accepted")
	}
	if _, err := caps.operation("k3s", "snapshot", "linux/arm64"); err == nil {
		t.Fatal("image platform mismatch accepted")
	}
	caps.Platforms = []string{"linux/arm64"}
	if _, err := caps.operation("k3s", "snapshot", "linux/arm64"); err != nil {
		t.Fatal(err)
	}
}

func TestExecutionIDBindsApplyToFreshOutputIdentity(t *testing.T) {
	valid := Options{Component: "opnsense", Operation: "apply", Output: "/tmp/execution-42", ExecutionID: "execution-42"}
	if err := validateExecutionID(valid); err != nil {
		t.Fatal(err)
	}
	for _, component := range []string{"pve", "pve-template"} {
		valid = Options{Component: component, Operation: "apply", Output: "/tmp/execution-42", ExecutionID: "execution-42"}
		if err := validateExecutionID(valid); err != nil {
			t.Fatalf("%s apply did not accept execution identity: %v", component, err)
		}
	}
	for _, invalid := range []Options{
		{Component: "opnsense", Operation: "apply", Output: "/tmp/result"},
		{Component: "opnsense", Operation: "apply", Output: "/tmp/other", ExecutionID: "execution-42"},
		{Component: "opnsense", Operation: "apply", Output: "/tmp/bad/id", ExecutionID: "bad/id"},
		{Component: "pve", Operation: "plan", Output: "/tmp/execution-42", ExecutionID: "execution-42"},
	} {
		if err := validateExecutionID(invalid); err == nil {
			t.Fatalf("accepted invalid execution identity: %#v", invalid)
		}
	}
}

func TestRuntimeArgsCarriesExecutionIDToDiscoveryAndRun(t *testing.T) {
	work := task{options: Options{Environment: "/inputs/environment.yml", Component: "opnsense",
		Operation: "apply", ExecutionID: "execution-42"}, image: "example/iaas@sha256:" + strings.Repeat("a", 64)}
	args := strings.Join(work.runtimeArgs(), " ")
	if !strings.Contains(args, "--execution-id execution-42") {
		t.Fatalf("runtime args did not carry execution identity: %s", args)
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
	mapped := filepath.Join(taskDir, strings.TrimPrefix(work.mapping[key], "/"))
	info, err := os.Stat(mapped)
	if err != nil {
		t.Fatalf("local input was not copied with caller ownership and mode: %v", err)
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || !info.Mode().IsRegular() || info.Mode().Perm() != 0600 || int(stat.Uid) != os.Getuid() {
		t.Fatalf("local input was not copied with caller ownership and mode: %v", err)
	}
	if data, err := os.ReadFile(mapped); err != nil || string(data) != "synthetic" {
		t.Fatalf("local input snapshot is incorrect: %v", err)
	}
	if err := os.WriteFile(key, []byte("changed"), 0600); err != nil {
		t.Fatal(err)
	}
	if data, err := os.ReadFile(mapped); err != nil || string(data) != "synthetic" {
		t.Fatalf("local input copy changed with caller source: %v", err)
	}
	if mounts := strings.Join(work.mounts(false), " "); strings.Contains(mounts, "src="+key) {
		t.Fatal("local regular input still uses a single-file bind")
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
	exportInfo, _ := os.Stat(filepath.Join(directory, "export/protected key"))
	if exportInfo.Mode().Perm() != 0600 {
		t.Fatal("private file permissions changed")
	}
	if err := os.Symlink(key, filepath.Join(input, "link")); err != nil {
		t.Fatal(err)
	}
	if err := copyTree(input, filepath.Join(directory, "reject")); err == nil {
		t.Fatal("artifact symlink accepted")
	}
}

func TestDindRegularInputUsesTheInputVolume(t *testing.T) {
	work := task{options: Options{Engine: "dind"}, inputVolume: "task-inputs",
		files: []inputFile{{logical: "/caller/key", actual: "/caller/key",
			remote: "/inputs/files/000000", writable: false, directory: false}},
	}
	mounts := strings.Join(work.mounts(false), " ")
	if !strings.Contains(mounts, "type=volume,src=task-inputs,dst=/inputs,readonly") {
		t.Fatal("dind input volume was not mounted read-only")
	}
	if strings.Contains(mounts, "src=/caller/key") {
		t.Fatal("dind regular input unexpectedly used a host file bind")
	}
}

func TestImageTaskDirectoryInputIsMountedWritableOnlyForLocalReadClean(t *testing.T) {
	directory := t.TempDir()
	taskDir := filepath.Join(directory, "task")
	if err := os.Mkdir(taskDir, 0700); err != nil {
		t.Fatal(err)
	}
	work := task{options: Options{Engine: "local", Component: "image", Operation: "clean"},
		directory: taskDir, mapping: map[string]string{}}
	if err := work.initialize(); err != nil {
		t.Fatal(err)
	}
	if err := work.addInput(directory); err != nil {
		t.Fatal(err)
	}
	if len(work.files) != 1 || !work.files[0].writable {
		t.Fatal("image cleanup directory was not marked writable")
	}
	mounts := strings.Join(work.mounts(false), " ")
	if strings.Contains(mounts, "readonly,src="+directory) {
		t.Fatal("image cleanup directory was mounted read-only")
	}
	verify := task{options: Options{Engine: "local", Component: "image", Operation: "verify"},
		directory: taskDir, mapping: map[string]string{}}
	if err := verify.initialize(); err != nil {
		t.Fatal(err)
	}
	if err := verify.addInput(directory); err != nil {
		t.Fatal(err)
	}
	if len(verify.files) != 1 || verify.files[0].writable {
		t.Fatal("image verification directory was not kept read-only")
	}
	verifyMounts := strings.Join(verify.mounts(false), " ")
	if !strings.Contains(verifyMounts, ",dst=/inputs/files/000000,readonly") {
		t.Fatal("image verification directory was not mounted read-only")
	}
	recovery := task{options: Options{Engine: "local", Component: "pve-template", Operation: "apply"},
		directory: taskDir, mapping: map[string]string{}}
	if err := recovery.initialize(); err != nil {
		t.Fatal(err)
	}
	if err := recovery.addInput(directory); err != nil {
		t.Fatal(err)
	}
	if len(recovery.files) != 1 || recovery.files[0].writable {
		t.Fatal("PVE cleanup recovery directory was not kept read-only")
	}
	recoveryMounts := strings.Join(recovery.mounts(false), " ")
	if !strings.Contains(recoveryMounts, ",dst=/inputs/files/000000,readonly") {
		t.Fatal("PVE cleanup recovery directory was not mounted read-only")
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

func TestImageLocalOutputRelocationPreservesTaskIdentity(t *testing.T) {
	directory := t.TempDir()
	source := filepath.Join(directory, ".iaas-task-1", "work", "output")
	destination := filepath.Join(directory, "result")
	if err := os.MkdirAll(source, 0700); err != nil {
		t.Fatal(err)
	}
	taskFile := filepath.Join(source, "work", "image", "task.json")
	if err := os.MkdirAll(filepath.Dir(taskFile), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(taskFile, []byte("task"), 0600); err != nil {
		t.Fatal(err)
	}
	before, err := os.Stat(taskFile)
	if err != nil {
		t.Fatal(err)
	}
	if err := relocateImageOutput(source, destination, []byte("result"), []byte("provenance")); err != nil {
		t.Fatal(err)
	}
	after, err := os.Stat(filepath.Join(destination, "work", "image", "task.json"))
	if err != nil {
		t.Fatal(err)
	}
	if !os.SameFile(before, after) {
		t.Fatal("local image collection copied instead of relocating the task workspace")
	}
	if _, err := os.Stat(source); !os.IsNotExist(err) {
		t.Fatalf("source workspace remained after relocation: %v", err)
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
