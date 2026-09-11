package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
)

type Docker struct{}

type ExitError struct {
	Code int
}

func (e *ExitError) Error() string { return fmt.Sprintf("operation exited with status %d", e.Code) }

func (d Docker) call(args ...string) ([]byte, error) {
	cmd := exec.Command("docker", args...)
	var output, privateError bytes.Buffer
	cmd.Stdout, cmd.Stderr = &output, &privateError
	if err := cmd.Run(); err != nil {
		// Docker errors may include supplied environment/container configuration.
		return output.Bytes(), fmt.Errorf("docker %s failed; check daemon access and task resources", args[0])
	}
	return output.Bytes(), nil
}

func (d Docker) resolveImage(reference string) (string, error) {
	data, err := d.call("image", "inspect", "--format", "{{json .RepoDigests}}", reference)
	if err != nil {
		return "", errors.New("selected image is not available locally; run iaas prepare explicitly")
	}
	var digests []string
	if json.Unmarshal(data, &digests) != nil || len(digests) == 0 {
		return "", errors.New("selected image has no repository digest; prepare a digest-addressable image")
	}
	if strings.Contains(reference, "@sha256:") {
		return reference, nil
	}
	// Prefer the requested repository when the same content was also pulled
	// through a mirror. Cache insertion order must not change plan identity.
	repository := reference
	if colon := strings.LastIndex(repository, ":"); colon > strings.LastIndex(repository, "/") {
		repository = repository[:colon]
	}
	for _, digest := range digests {
		if strings.HasPrefix(digest, repository+"@sha256:") {
			return digest, nil
		}
	}
	if !strings.Contains(digests[0], "@sha256:") {
		return "", errors.New("invalid Docker image digest metadata")
	}
	// Retagging does not create a new RepoDigest association. Use the actual
	// locally addressable digest rather than inventing one under the tag name.
	return digests[0], nil
}

func (d Docker) capabilities(image, platform string) (Capabilities, error) {
	var result Capabilities
	data, err := d.call("run", "--rm", "--pull", "never", "--network", "none", "--platform", platform, image, "capabilities")
	if err != nil || json.Unmarshal(data, &result) != nil {
		return result, errors.New("image does not expose a compatible runtime interface")
	}
	return result, nil
}

// attached forwards cancellation to the container, then obtains its actual exit
// status. Killing the local Docker CLI alone would leave a mutation running.
func (d Docker) attached(container string, interrupted <-chan os.Signal) ([]byte, int, error) {
	cmd := exec.Command("docker", "start", "--attach", container)
	var output, privateError bytes.Buffer
	cmd.Stdout, cmd.Stderr = &output, &privateError
	if err := cmd.Start(); err != nil {
		return nil, 2, errors.New("could not start container attachment")
	}
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	cancelled := false
	select {
	case <-done:
	case <-interrupted:
		cancelled = true
		if _, err := d.call("stop", "--time", "20", container); err != nil {
			return nil, 130, errors.New("could not confirm container cancellation; task storage and container retained")
		}
		<-done
	}
	state, err := d.call("inspect", "--format", "{{.State.Running}} {{.State.ExitCode}}", container)
	if err != nil {
		return output.Bytes(), 2, err
	}
	parts := strings.Fields(string(state))
	if len(parts) != 2 || parts[0] != "false" {
		return output.Bytes(), 2, errors.New("container completion is unconfirmed; retain task resources")
	}
	code, err := strconv.Atoi(parts[1])
	if err != nil {
		return output.Bytes(), 2, errors.New("container exit status is unavailable")
	}
	if cancelled && code == 0 {
		code = 130
	}
	return output.Bytes(), code, nil
}
