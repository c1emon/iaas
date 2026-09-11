package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"regexp"
	"strings"
)

type RuntimeConfig struct {
	InterfaceVersion int    `json:"interface_version"`
	Image            string `json:"image"`
	Platform         string `json:"platform"`
}

type Effects struct {
	Network             bool `json:"network"`
	State               bool `json:"state"`
	InfrastructureWrite bool `json:"infrastructure_write"`
	LocalWrite          bool `json:"local_write"`
}

type Capabilities struct {
	InterfaceVersion int                           `json:"interface_version"`
	SchemaVersions   []int                         `json:"schema_versions"`
	Platforms        []string                      `json:"platforms"`
	Operations       map[string]map[string]Effects `json:"operations"`
}

func readRuntime(path string) (RuntimeConfig, error) {
	var result RuntimeConfig
	file, err := os.Open(path)
	if err != nil {
		return result, errors.New("cannot read runtime configuration")
	}
	defer file.Close()
	decoder := json.NewDecoder(file)
	decoder.DisallowUnknownFields()
	if err = decoder.Decode(&result); err != nil {
		return result, errors.New("runtime configuration must be JSON with interface_version, image and platform")
	}
	if err = decoder.Decode(new(any)); err != io.EOF {
		return result, errors.New("unexpected trailing runtime configuration")
	}
	return result, result.validate()
}

func (r RuntimeConfig) validate() error {
	if r.InterfaceVersion != 1 {
		return errors.New("unsupported launcher interface version")
	}
	if r.Platform != "linux/amd64" {
		return errors.New("unsupported platform; explicitly select linux/amd64 (including Apple Silicon emulation)")
	}
	if r.Image == "" || strings.ContainsAny(r.Image, " \n\t\r") || strings.HasPrefix(r.Image, "-") {
		return errors.New("invalid image reference")
	}
	if strings.Contains(r.Image, "@") {
		if !regexp.MustCompile(`^[^@]+@sha256:[0-9a-f]{64}$`).MatchString(r.Image) {
			return errors.New("invalid image digest")
		}
	} else {
		leaf := r.Image[strings.LastIndex(r.Image, "/")+1:]
		_, tag, ok := strings.Cut(leaf, ":")
		if !ok || tag == "" || tag == "latest" {
			return errors.New("select an explicit release tag or digest; latest is unsupported")
		}
	}
	return nil
}

func (c Capabilities) operation(component, operation string) (Effects, error) {
	if c.InterfaceVersion != 1 {
		return Effects{}, errors.New("image and launcher interface versions are incompatible")
	}
	platform := false
	for _, p := range c.Platforms {
		platform = platform || p == "linux/amd64"
	}
	schema := false
	for _, v := range c.SchemaVersions {
		schema = schema || v == 1
	}
	if !platform || !schema {
		return Effects{}, errors.New("image does not support the selected platform/configuration schema")
	}
	operationEffects, ok := c.Operations[component][operation]
	if !ok {
		return Effects{}, fmt.Errorf("unsupported component/operation: %s/%s", component, operation)
	}
	return operationEffects, nil
}
