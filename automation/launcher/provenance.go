package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
)

// Git is optional and only describes the environment entry's repository. The
// digest and explicit logical input origins remain the runtime's primary record.
func inputProvenance(environment string) map[string]any {
	result := map[string]any{"git_status": "unavailable", "git_revision": nil,
		"coverage": "environment entry repository only; referenced external files are not attested"}
	git, err := exec.LookPath("git")
	if err != nil {
		return result
	}
	command := func(arguments ...string) ([]byte, error) {
		args := []string{"-C", filepath.Dir(environment), "-c", "core.fsmonitor=false"}
		cmd := exec.Command(git, append(args, arguments...)...)
		cmd.Env = append(os.Environ(), "GIT_OPTIONAL_LOCKS=0")
		return cmd.Output()
	}
	data, err := command("rev-parse", "HEAD")
	revision := strings.TrimSpace(string(data))
	if err != nil || !regexp.MustCompile(`^[0-9a-f]{40,64}$`).MatchString(revision) {
		return result
	}
	result["git_revision"] = revision
	status, err := command("status", "--porcelain", "--untracked-files=normal", "--ignore-submodules=all")
	if err != nil {
		result["git_status"] = "working-tree-unconfirmed"
		return result
	}
	result["git_status"] = "clean"
	if len(status) > 0 {
		result["git_status"] = "dirty"
	}
	return result
}
