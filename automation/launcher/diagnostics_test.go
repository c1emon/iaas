package main

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
)

func TestPublicDiagnosticsRetainErrorsWarningsAndRejectRawText(t *testing.T) {
	var entries []PublicDiagnostic
	data := `[{"code":"api_port_invalid","field":"destination_port","resource":"filter-rules","message":"private-message","status_code":400},
	{"code":"permission_denied","status_code":403},
	{"code":"opnsense_native_limit","resource":"aliases"},
	{"code":"protected_warning","warning_count":2},
	{"code":"timeout","field":"private-field","resource":"private-resource","exit_code":999},
	{"code":"private-code","message":"private-message"}]`
	if err := json.Unmarshal([]byte(data), &entries); err != nil {
		t.Fatal(err)
	}
	var output bytes.Buffer
	writePublicDiagnostics(&output, entries)
	text := output.String()
	for _, required := range []string{"ERROR [api_port_invalid]", "field=destination_port", "resource=filter-rules", "HTTP=400", "HTTP=403", "WARNING [opnsense_native_limit]", "WARNING [protected_warning]", "warnings=2", "Operation timed out"} {
		if !strings.Contains(text, required) {
			t.Fatalf("missing diagnostic %q in %s", required, text)
		}
	}
	if strings.Contains(text, "private-") || strings.Contains(text, "exit=999") {
		t.Fatalf("untrusted diagnostic leaked: %s", text)
	}
}

func TestFailedPhaseOutputPreservesStageAndExitStatus(t *testing.T) {
	code := 17
	var output bytes.Buffer
	writeFailedPhases(&output, []PublicPhase{{Phase: "pve-health", ExitCode: &code},
		{Phase: "k3s-deploy", Status: "not-started"}, {Phase: "private-token\n", ExitCode: &code}})
	text := output.String()
	if !strings.Contains(text, "phase=pve-health exit=17") || !strings.Contains(text, "phase=k3s-deploy status=not-started") || strings.Contains(text, "private-token") {
		t.Fatal(text)
	}
}

func TestProcessSetupReportDisplaysSafeCodeAndPhase(t *testing.T) {
	var report struct {
		Phases      []PublicPhase      `json:"phases"`
		Diagnostics []PublicDiagnostic `json:"diagnostics"`
	}
	data := `{"phases":[{"phase":"opnsense-workflow-save-filter-rules","status":"not-started","exit_code":null}],"diagnostics":[{"code":"process_start_failed","message":"private-setup-sentinel"}]}`
	if err := json.Unmarshal([]byte(data), &report); err != nil {
		t.Fatal(err)
	}
	var output bytes.Buffer
	writeFailedPhases(&output, report.Phases)
	writePublicDiagnostics(&output, report.Diagnostics)
	text := output.String()
	for _, required := range []string{"phase=opnsense-workflow-save-filter-rules status=not-started", "[process_start_failed]", "Child process could not start"} {
		if !strings.Contains(text, required) {
			t.Fatalf("missing %q: %s", required, text)
		}
	}
	if strings.Contains(text, "private-setup-sentinel") {
		t.Fatal(text)
	}
}
