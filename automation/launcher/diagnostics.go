package main

import (
	"fmt"
	"io"
	"regexp"
	"strings"
)

// Reconstruct messages instead of printing arbitrary runtime or provider text.
var diagnosticMessages = map[string]string{
	"k3s_model_invalid":          "K3s validated model/node admission gate failed.",
	"registry_bearer_invalid":    "Registry authentication requires a same-authority HTTPS Bearer realm and credentials.",
	"credential_scope_missing":   "Declared endpoint access requires an action-scoped runtime credential.",
	"registry_tls_invalid":       "Registry TLS files must be regular and have restrictive permissions.",
	"switch_call_invalid":        "Switch resource calls must declare config and an allowed state.",
	"secret_channel_missing":     "An explicit resolvable protected runtime secret channel is required.",
	"k3s_tls_invalid":            "Declared K3s TLS files must be regular and have restrictive permissions.",
	"k3s_runtime_unhealthy":      "K3s runtime failed the post-restart health gate.",
	"artifact_selection_invalid": "K3s artifact selection requires HTTPS, SHA-256 and its scoped credential.",
	"k3s_version_drift":          "Installed K3s version differs from reviewed observations; regenerate the plan.",
	"k3s_bootstrap_not_ready":    "Bootstrap API did not become ready; dependent joins stopped.",
	"k3s_token_mismatch":         "Bootstrap secure token does not match its protected external reference.",
	"k3s_ca_invalid":             "Authoritative K3s server CA must contain exactly one X.509 certificate.",
	"task_failed":                "Task failed.",
	"task_unreachable":           "Task could not reach its target.",
	"task_warning":               "Task reported warnings.",
	"protected_task_failed":      "Protected task failed; raw arguments and output remain private.",
	"protected_task_unreachable": "Protected task could not reach its target.",
	"protected_warning":          "Protected task reported warnings; warning text remains private.",
	"authentication_failed":      "Authentication failed.",
	"permission_denied":          "Permission denied.",
	"http_failure":               "HTTP request failed.",
	"timeout":                    "Operation timed out.",
	"connection_failed":          "Connection failed.",
	"api_validation_failed":      "API rejected a field value; unrecognized reason text is redacted.",
	"api_port_invalid":           "API requires a valid port number, port alias or continuous range.",
	"api_network_invalid":        "API requires a valid network segment or alias.",
	"api_gateway_invalid":        "API requires a gateway matching the network IP protocol.",
	"api_sequence_invalid":       "API requires a sequence between 1 and 999999.",
	"api_field_required":         "API requires a value for this field.",
	"process_failed":             "Child process failed; inspect the protected capture for details.",
	"process_start_failed":       "Child process could not start; inspect task setup and protected output.",
	"process_interrupted":        "Child process was interrupted; completion is unconfirmed.",
	"capture_incomplete":         "Protected output capture is incomplete; retain task storage.",
	"operation_failed":           "Operation failed; unrecognized exception text remains private.",
	"invalid_value":              "Input validation failed.",
	"opnsense_native_limit":      "Native OPNsense success does not independently prove internal completion or active state.",
	"activation_failed":          "Activation failed or is unconfirmed; dependent stages stopped.",
}

type PublicDiagnostic struct {
	Action       string `json:"action"`
	Code         string `json:"code"`
	Field        string `json:"field"`
	Resource     string `json:"resource"`
	StatusCode   *int   `json:"status_code"`
	ExitCode     *int   `json:"exit_code"`
	WarningCount *int   `json:"warning_count"`
}

func writePublicDiagnostics(destination io.Writer, diagnostics []PublicDiagnostic) {
	for index, entry := range diagnostics {
		if index >= 64 {
			break
		}
		message, known := diagnosticMessages[entry.Code]
		if !known {
			continue
		}
		severity := "ERROR"
		if entry.Code == "task_warning" || entry.Code == "protected_warning" || entry.Code == "opnsense_native_limit" {
			severity = "WARNING"
		}
		fmt.Fprintf(destination, "%s [%s]: %s", severity, entry.Code, message)
		if strings.Contains("|command|shell|uri|assert|fail|copy|template|set_fact|service|systemd|systemd_service|get_url|fetch|slurp|stat|wait_for|alias|alias_multi|rule|rule_multi|interface_vip|gateway|raw|nat_destination|nat_one_to_one|rule_interface_group|protected_task|", "|"+entry.Action+"|") {
			fmt.Fprintf(destination, " action=%s", entry.Action)
		}
		if strings.Contains("|source_port|destination_port|local_port|source_net|destination_net|interface|gateway|protocol|ipprotocol|sequence|action|direction|enabled|quick|description|name|type|content|target|external|address|members|statetype|replyto|source_not|destination_not|unknown_field|value|row|selected|identity|references|", "|"+entry.Field+"|") {
			fmt.Fprintf(destination, " field=%s", entry.Field)
		}
		if strings.Contains("|aliases|vips|gateways|filter-rules|dnat|one-to-one-nat|interface-groups|", "|"+entry.Resource+"|") {
			fmt.Fprintf(destination, " resource=%s", entry.Resource)
		}
		if entry.StatusCode != nil && *entry.StatusCode >= 100 && *entry.StatusCode <= 599 {
			fmt.Fprintf(destination, " HTTP=%d", *entry.StatusCode)
		}
		if entry.ExitCode != nil && *entry.ExitCode >= 0 && *entry.ExitCode <= 255 {
			fmt.Fprintf(destination, " exit=%d", *entry.ExitCode)
		}
		if entry.WarningCount != nil && *entry.WarningCount >= 1 && *entry.WarningCount <= 1000 {
			fmt.Fprintf(destination, " warnings=%d", *entry.WarningCount)
		}
		fmt.Fprintln(destination)
	}
}

type PublicPhase struct {
	Phase    string `json:"phase"`
	Status   string `json:"status"`
	ExitCode *int   `json:"exit_code"`
}

var publicPhaseName = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9_-]{0,127}$`)

func writeFailedPhases(destination io.Writer, phases []PublicPhase) {
	for index, phase := range phases {
		if index >= 64 {
			break
		}
		if !publicPhaseName.MatchString(phase.Phase) {
			continue
		}
		if phase.ExitCode != nil && *phase.ExitCode > 0 && *phase.ExitCode <= 255 {
			fmt.Fprintf(destination, "ERROR phase=%s exit=%d\n", phase.Phase, *phase.ExitCode)
		} else if phase.Status == "not-started" {
			fmt.Fprintf(destination, "ERROR phase=%s status=not-started\n", phase.Phase)
		}
	}
}
