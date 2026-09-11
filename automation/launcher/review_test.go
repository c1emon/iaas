package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestTagPrefersRequestedRepositoryOverCacheOrder(t *testing.T) {
	for _, reversed := range []bool{false, true} {
		directory := t.TempDir()
		wanted := "ghcr.io/example/iaas@sha256:" + strings.Repeat("a", 64)
		mirror := "mirror.example/iaas@sha256:" + strings.Repeat("a", 64)
		digests := []string{mirror, wanted}
		if reversed {
			digests = []string{wanted, mirror}
		}
		data, _ := json.Marshal(digests)
		script := "#!/bin/sh\nprintf '%s\\n' '" + string(data) + "'\n"
		if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
			t.Fatal(err)
		}
		t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
		resolved, err := (Docker{}).resolveImage("ghcr.io/example/iaas:v1")
		if err != nil || resolved != wanted {
			t.Fatalf("cache history changed plan identity: %q %v", resolved, err)
		}
	}
}

func TestDiscoveryPreservesSafeRuntimeReason(t *testing.T) {
	directory := t.TempDir()
	script := `#!/bin/sh
echo '{"status":"failed","reason":"expected schema_version: 1; migrate the entry explicitly"}'
echo synthetic-private-value >&2
exit 2
`
	if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
	work := task{options: Options{Engine: "local"}, directory: filepath.Join(directory, "task"), mapping: map[string]string{}}
	if err := work.initialize(); err != nil {
		t.Fatal(err)
	}
	_, err := work.discover()
	if err == nil || !strings.Contains(err.Error(), "schema_version: 1") || strings.Contains(err.Error(), "synthetic-private-value") {
		t.Fatalf("discovery did not preserve the safe configuration diagnostic: %v", err)
	}
}
