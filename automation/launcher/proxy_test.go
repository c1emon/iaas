package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestProxyNormalizationAndAdmission(t *testing.T) {
	cases := []struct {
		name     string
		settings map[string]string
		want     string
		invalid  bool
	}{
		{"lowercase", map[string]string{"http_proxy": " http://proxy.example:8080 "}, "http://proxy.example:8080", false},
		{"same", map[string]string{"HTTP_PROXY": "http://proxy.example", "http_proxy": "http://proxy.example"}, "http://proxy.example", false},
		{"empty", map[string]string{"HTTP_PROXY": " ", "http_proxy": "http://proxy.example"}, "http://proxy.example", false},
		{"conflict", map[string]string{"HTTP_PROXY": "http://one", "http_proxy": "http://two"}, "", true},
		{"basic", map[string]string{"HTTP_PROXY": "https://test%40user:p%3Ass@proxy.example:443/"}, "https://test%40user:p%3Ass@proxy.example:443/", false},
		{"username only", map[string]string{"HTTP_PROXY": "http://test@proxy.example"}, "http://test@proxy.example", false},
		{"empty password", map[string]string{"HTTP_PROXY": "http://test:@proxy.example"}, "http://test:@proxy.example", false},
		{"unsupported", map[string]string{"ALL_PROXY": "socks5://ignored", "FTP_PROXY": "invalid"}, "", false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := normalizedProxy(true, func(name string) string { return tc.settings[name] })
			if (err != nil) != tc.invalid {
				t.Fatalf("unexpected error: %v", err)
			}
			if err == nil && (got["HTTP_PROXY"] != tc.want || got["http_proxy"] != tc.want || got["HTTPS_PROXY"] != "") {
				t.Fatal("normalization or protocol independence failed")
			}
		})
	}
	for _, value := range []string{"socks5://proxy", "http://", "http://proxy/path", "http://proxy?query", "http://proxy#fragment", "http://proxy#", "http://proxy/%2f", "http://proxy/%2F", "http://proxy%25", "HTTP://proxy", "Https://proxy", "http://proxy:", "http://proxy:0", "http://proxy:65536", "http://:secret@proxy", "http://user:p%zz@proxy", "http://user:p%0a@proxy", "http://user%3Aname:password@proxy", "http://user%00:password@proxy", "http://user:password@proxy host"} {
		_, err := normalizedProxy(true, func(name string) string {
			if name == "HTTP_PROXY" {
				return value
			}
			return ""
		})
		if err == nil || strings.Contains(err.Error(), value) || strings.Contains(err.Error(), "secret") || strings.Contains(err.Error(), "password") {
			t.Fatal("invalid endpoint accepted or exposed")
		}
	}
	for _, value := range []string{"service\n.example", "service\r.example", "service\x00.example"} {
		_, err := normalizedProxy(true, func(name string) string {
			if name == "NO_PROXY" {
				return value
			}
			return ""
		})
		if err == nil {
			t.Fatal("NO_PROXY control character accepted")
		}
	}
	got, err := normalizedProxy(false, func(string) string { return "malformed authentication" })
	if err != nil || len(got) != 0 {
		t.Fatal("offline configuration was parsed")
	}
	for _, name := range proxyNames {
		t.Setenv(name, "")
	}
	caps := Capabilities{}
	if proxyAdmission(caps, Effects{Network: true}) != nil {
		t.Fatal("direct operation required proxy capability")
	}
	t.Setenv("NO_PROXY", "service.example")
	if proxyAdmission(caps, Effects{Network: true}) == nil {
		t.Fatal("NO_PROXY alone bypassed admission")
	}
	if proxyAdmission(caps, Effects{}) != nil {
		t.Fatal("offline operation required proxy capability")
	}
	caps.NetworkProxyVersion = 1
	if proxyAdmission(caps, Effects{Network: true}) != nil {
		t.Fatal("compatible capability rejected")
	}
}

func TestProxyDockerEnvironmentAndHelpers(t *testing.T) {
	value := "http://test-user:test-password@proxy.example"
	settings, err := normalizedProxy(true, func(name string) string {
		if name == "http_proxy" {
			return value
		}
		return ""
	})
	if err != nil {
		t.Fatal(err)
	}
	args, environment := proxyContainerEnvironment([]string{"HTTP_PROXY=old", "http_proxy=old"}, settings)
	joined := strings.Join(args, " ")
	if strings.Contains(joined, value) || !strings.Contains(joined, "--env HTTP_PROXY --env http_proxy") {
		t.Fatal("proxy authentication passed in argv")
	}
	for _, name := range []string{"HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy", "ALL_PROXY", "all_proxy", "FTP_PROXY", "ftp_proxy"} {
		if !strings.Contains(joined, "--env "+name+"=") {
			t.Fatal("implicit proxy not cleared")
		}
	}
	for _, name := range []string{"HTTP_PROXY", "http_proxy"} {
		if !strings.Contains(strings.Join(environment, "\n"), name+"="+value) {
			t.Fatal("normalized proxy not in client environment")
		}
	}
	directory := t.TempDir()
	log := filepath.Join(directory, "arguments")
	if err := os.WriteFile(filepath.Join(directory, "docker"), []byte("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$PROXY_TEST_LOG\"\n"), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
	t.Setenv("PROXY_TEST_LOG", log)
	for _, command := range []string{"run", "create"} {
		if _, err := (Docker{}).call(command, "--network", "none", "image"); err != nil {
			t.Fatal(err)
		}
		data, err := os.ReadFile(log)
		if err != nil {
			t.Fatal(err)
		}
		for _, name := range proxyNames {
			if !strings.Contains(string(data), "\n"+name+"=\n") {
				t.Fatalf("helper %s did not clear %s", command, name)
			}
		}
	}
	for _, name := range []string{"hTtP_PrOxY", "ALL_PROXY", "fTp_PrOxY"} {
		if !reservedProxyName(name) {
			t.Fatal("proxy credential alias not reserved")
		}
	}
}

// This exercises the production execute path and Docker argument construction;
// the fake daemon is a fixture, not a real container/network acceptance claim.
func TestProxyExecutionLocalAndDinD(t *testing.T) {
	for _, engine := range []string{"local", "dind"} {
		for _, network := range []bool{false, true} {
			t.Run(engine+map[bool]string{true: "/online", false: "/offline"}[network], func(t *testing.T) {
				directory := t.TempDir()
				log := filepath.Join(directory, "calls")
				environmentLog := filepath.Join(directory, "execution-environment")
				script := `#!/bin/sh
printf '%s\n' "$*" >> "$PROXY_TEST_LOG"
case "$1" in
 run) printf '%s\n' '{"status":"ready","credential_names":[]}' ;;
 create)
  case "$*" in
   *-run*) env | sed -n '/^[Hh][Tt][Tt][Pp][Ss]*_[Pp][Rr][Oo][Xx][Yy]=/p' > "$PROXY_TEST_ENV" ;;
  esac ;;
 start)
  case "$*" in
   *-run*) printf '%s\n' '{"status":"success"}' ;;
  esac ;;
 inspect) printf '%s\n' 'false 0' ;;
esac
`
				if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
					t.Fatal(err)
				}
				t.Setenv("PATH", directory+string(os.PathListSeparator)+os.Getenv("PATH"))
				t.Setenv("PROXY_TEST_LOG", log)
				t.Setenv("PROXY_TEST_ENV", environmentLog)
				for _, name := range proxyNames {
					t.Setenv(name, "")
				}
				value := "http://fixture-user:fixture-password@proxy.example:8080"
				t.Setenv("http_proxy", value)
				output := filepath.Join(directory, "result")
				// Local fixtures need a source output directory for the result collector.
				// Fake create finds its task bind mount and creates that empty directory.
				if engine == "local" {
					script = strings.Replace(script, "create)\n", "create)\n  for arg in \"$@\"; do\n   case \"$arg\" in type=bind,src=*,dst=/task) task_path=${arg#type=bind,src=}; task_path=${task_path%,dst=/task}; mkdir -p \"$task_path/output\" ;; esac\n  done\n", 1)
					if err := os.WriteFile(filepath.Join(directory, "docker"), []byte(script), 0700); err != nil {
						t.Fatal(err)
					}
				}
				err := execute(Options{Engine: engine, Output: output, Component: "pve", Operation: "prepare-dependencies"}, RuntimeConfig{Platform: "linux/amd64"}, "fixture-image", Effects{Network: network}, Docker{})
				if err != nil {
					t.Fatal(err)
				}
				calls, err := os.ReadFile(log)
				if err != nil {
					t.Fatal(err)
				}
				if strings.Contains(string(calls), value) || strings.Contains(string(calls), "fixture-password") {
					t.Fatal("proxy secret entered Docker argv")
				}
				var executionCall string
				for _, line := range strings.Split(string(calls), "\n") {
					if strings.HasPrefix(line, "create ") && strings.Contains(line, "-run ") {
						executionCall = line
					}
				}
				if executionCall == "" {
					t.Fatal("execution container was not created")
				}
				if network {
					if !strings.Contains(executionCall, "--env HTTP_PROXY --env http_proxy") {
						t.Fatal("execution proxy not explicitly selected")
					}
					env, err := os.ReadFile(environmentLog)
					if err != nil {
						t.Fatal(err)
					}
					if !strings.Contains(string(env), "HTTP_PROXY="+value) || !strings.Contains(string(env), "http_proxy="+value) {
						t.Fatal("normalized environment did not reach Docker client")
					}
				} else {
					if !strings.Contains(executionCall, "--network none") || !strings.Contains(executionCall, "--env HTTP_PROXY= --env http_proxy=") {
						t.Fatal("offline proxy or network was not isolated")
					}
				}
				for _, name := range []string{"ALL_PROXY", "all_proxy", "FTP_PROXY", "ftp_proxy"} {
					if !strings.Contains(executionCall, "--env "+name+"=") {
						t.Fatal("unsupported implicit proxy not neutralized")
					}
				}
				result, err := os.ReadFile(filepath.Join(output, "launcher-result.json"))
				if err != nil {
					t.Fatal(err)
				}
				if strings.Contains(string(result), "fixture-user") || strings.Contains(string(result), "fixture-password") {
					t.Fatal("proxy entered launcher result")
				}
			})
		}
	}
}
