package main

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type inputFile struct{ logical, actual, remote string }

type task struct {
	options       Options
	configuration RuntimeConfig
	image         string
	docker        Docker
	directory     string
	name          string
	seed          string
	container     string
	inputVolume   string
	outputVolume  string
	files         []inputFile
	mapping       map[string]string
	retained      bool
}

func bind(source, destination string, readonly bool) []string {
	var value bytes.Buffer
	writer := csv.NewWriter(&value)
	fields := []string{"type=bind", "src=" + source, "dst=" + destination}
	if readonly {
		fields = append(fields, "readonly")
	}
	_ = writer.Write(fields)
	writer.Flush()
	return []string{"--mount", strings.TrimSpace(value.String())}
}

func (t *task) initialize() error {
	for _, directory := range []string{"inputs/files", "work"} {
		if err := os.MkdirAll(filepath.Join(t.directory, directory), 0700); err != nil {
			return err
		}
	}
	uid, gid := os.Getuid(), os.Getgid()
	passwd := fmt.Sprintf("root:x:0:0:root:/root:/bin/sh\niaas:x:%d:%d:runtime:/task/output/work/home:/bin/sh\n", uid, gid)
	if uid == 0 {
		passwd = "root:x:0:0:runtime:/task/output/work/home:/bin/sh\n"
	}
	for name, contents := range map[string]string{
		"passwd": passwd, "group": fmt.Sprintf("root:x:0:\niaas:x:%d:\n", gid),
	} {
		if err := os.WriteFile(filepath.Join(t.directory, "inputs", name), []byte(contents), 0644); err != nil {
			return err
		}
	}
	if t.options.Engine == "local" {
		return nil
	}
	for _, target := range []*string{&t.inputVolume, &t.outputVolume} {
		volume := t.name + "-inputs"
		if target == &t.outputVolume {
			volume = t.name + "-output"
		}
		if _, err := t.docker.call("volume", "create", volume); err != nil {
			return err
		}
		*target = volume
	}
	script := "import os,sys\nfor p in ['/inputs','/inputs/files','/task']:\n os.makedirs(p,exist_ok=True); os.chown(p,int(sys.argv[1]),int(sys.argv[2])); os.chmod(p,0o700)"
	seed := t.name + "-transfer"
	_, err := t.docker.call("create", "--name", seed, "--pull", "never", "--platform", t.configuration.Platform,
		"--network", "none", "--read-only", "--mount", "type=volume,src="+t.inputVolume+",dst=/inputs",
		"--mount", "type=volume,src="+t.outputVolume+",dst=/task", "--entrypoint", "python", t.image,
		"-c", script, strconv.Itoa(uid), strconv.Itoa(gid))
	if err != nil {
		return err
	}
	t.seed = seed
	if _, err = t.docker.call("start", "--attach", t.seed); err != nil {
		return err
	}
	for _, name := range []string{"passwd", "group"} {
		if _, err = t.docker.call("cp", "-a", filepath.Join(t.directory, "inputs", name), t.seed+":/inputs/"+name); err != nil {
			return err
		}
	}
	return nil
}

func (t *task) addInput(logical string) error {
	if !filepath.IsAbs(logical) {
		return errors.New("runtime requested a non-absolute client input")
	}
	if _, exists := t.mapping[logical]; exists {
		return errors.New("runtime requested an input that was already supplied")
	}
	actual, err := filepath.EvalSymlinks(logical)
	if err != nil {
		return fmt.Errorf("cannot supply declared input: %s", logical)
	}
	info, err := os.Stat(actual)
	if err != nil || !info.Mode().IsRegular() {
		return errors.New("declared input must be a readable regular file")
	}
	remote := fmt.Sprintf("/inputs/files/%06d", len(t.files))
	if t.options.Engine == "dind" {
		if _, err := t.docker.call("cp", "-a", actual, t.seed+":"+remote); err != nil {
			return errors.New("explicit input transfer failed")
		}
	} else {
		// A placeholder allows a file bind below the read-only metadata bind.
		if err := os.WriteFile(filepath.Join(t.directory, remote[1:]), nil, 0600); err != nil {
			return err
		}
	}
	t.files = append(t.files, inputFile{logical, actual, remote})
	t.mapping[logical] = remote
	return nil
}

func (t *task) writeMap() error {
	data, err := json.Marshal(t.mapping)
	if err != nil {
		return err
	}
	path := filepath.Join(t.directory, "inputs/map.json")
	if err := os.WriteFile(path, data, 0600); err != nil {
		return err
	}
	if t.options.Engine == "dind" {
		_, err = t.docker.call("cp", "-a", path, t.seed+":/inputs/map.json")
	}
	return err
}

func (t *task) mounts(withOutput bool) []string {
	args := []string{"--platform", t.configuration.Platform, "--read-only", "--tmpfs", "/tmp:rw,mode=1777",
		"--user", fmt.Sprintf("%d:%d", os.Getuid(), os.Getgid())}
	if t.options.Engine == "dind" {
		args = append(args, "--mount", "type=volume,src="+t.inputVolume+",dst=/inputs,readonly")
		if withOutput {
			args = append(args, "--mount", "type=volume,src="+t.outputVolume+",dst=/task")
		}
	} else {
		args = append(args, bind(filepath.Join(t.directory, "inputs"), "/inputs", true)...)
		for _, file := range t.files {
			args = append(args, bind(file.actual, file.remote, true)...)
		}
		if withOutput {
			args = append(args, bind(filepath.Join(t.directory, "work"), "/task", false)...)
		}
	}
	if t.options.Engine == "local" {
		args = append(args, bind(filepath.Join(t.directory, "inputs/passwd"), "/etc/passwd", true)...)
		args = append(args, bind(filepath.Join(t.directory, "inputs/group"), "/etc/group", true)...)
	} else {
		for _, name := range []string{"passwd", "group"} {
			args = append(args, "--mount", "type=volume,src="+t.inputVolume+",dst=/etc/"+name+",volume-subpath="+name+",readonly")
		}
	}
	return args
}

func copyTree(source, destination string) error {
	return copyTaskTree(source, destination, false)
}

func copyTaskTree(source, destination string, preserveLinks bool) error {
	return filepath.WalkDir(source, func(path string, entry os.DirEntry, walkError error) error {
		if walkError != nil {
			return walkError
		}
		relative, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		target := filepath.Join(destination, relative)
		if entry.Type()&os.ModeSymlink != 0 {
			if preserveLinks {
				link, err := os.Readlink(path)
				if err != nil {
					return err
				}
				return os.Symlink(link, target)
			}
			return errors.New("artifact directory contains a symlink")
		}
		if entry.IsDir() {
			return os.MkdirAll(target, 0700)
		}
		info, err := entry.Info()
		if err != nil || !info.Mode().IsRegular() {
			return errors.New("artifact must be a regular file")
		}
		input, err := os.Open(path)
		if err != nil {
			return err
		}
		defer input.Close()
		output, err := os.OpenFile(target, os.O_CREATE|os.O_EXCL|os.O_WRONLY, info.Mode().Perm()&0700)
		if err != nil {
			return err
		}
		_, err = io.Copy(output, input)
		closeError := output.Close()
		if err != nil {
			return err
		}
		return closeError
	})
}

func writeNewPrivate(path string, data []byte) error {
	file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	_, err = file.Write(data)
	closeError := file.Close()
	if err != nil {
		return err
	}
	return closeError
}

func (t *task) cleanup() error {
	if t.retained {
		return nil
	}
	for _, container := range []string{t.container, t.seed} {
		if container != "" {
			if _, err := t.docker.call("rm", "--force", container); err != nil {
				return err
			}
		}
	}
	for _, volume := range []string{t.inputVolume, t.outputVolume} {
		if volume != "" {
			if _, err := t.docker.call("volume", "rm", volume); err != nil {
				return err
			}
		}
	}
	return os.RemoveAll(t.directory)
}
