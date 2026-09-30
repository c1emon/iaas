package main

import (
	"errors"
	"net/url"
	"os"
	"strconv"
	"strings"
	"unicode"
)

var proxyNames = []string{"HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy", "ALL_PROXY", "all_proxy", "FTP_PROXY", "ftp_proxy"}

func reservedProxyName(name string) bool {
	for _, candidate := range proxyNames {
		if strings.EqualFold(name, candidate) {
			return true
		}
	}
	return false
}

func normalizedProxy(network bool, lookup func(string) string) (map[string]string, error) {
	result := map[string]string{}
	if !network {
		return result, nil
	}
	for _, upper := range []string{"HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"} {
		lower := strings.ToLower(upper)
		a, b := strings.TrimSpace(lookup(upper)), strings.TrimSpace(lookup(lower))
		if a != "" && b != "" && a != b {
			return nil, errors.New("conflicting " + upper + "/" + lower + " proxy configuration")
		}
		value := a
		if value == "" {
			value = b
		}
		if value == "" {
			continue
		}
		if strings.ContainsFunc(value, unicode.IsControl) || (upper != "NO_PROXY" && !validProxyEndpoint(value)) {
			return nil, errors.New("invalid " + upper + " proxy endpoint or authentication")
		}
		result[upper], result[lower] = value, value
	}
	return result, nil
}

func validProxyEndpoint(value string) bool {
	if (!strings.HasPrefix(value, "http://") && !strings.HasPrefix(value, "https://")) || strings.ContainsAny(value, "?#") || strings.ContainsFunc(value, func(r rune) bool { return unicode.IsSpace(r) || unicode.IsControl(r) }) {
		return false
	}
	parsed, err := url.Parse(value)
	if err != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") || parsed.Hostname() == "" || parsed.Opaque != "" || parsed.RawQuery != "" || parsed.Fragment != "" || parsed.ForceQuery || (parsed.EscapedPath() != "" && parsed.EscapedPath() != "/") {
		return false
	}
	if strings.HasSuffix(parsed.Host, ":") || strings.Contains(parsed.Host, "%") {
		return false
	}
	if port := parsed.Port(); port != "" {
		n, err := strconv.Atoi(port)
		if err != nil || n < 1 || n > 65535 {
			return false
		}
	}
	if parsed.User != nil {
		if parsed.User.Username() == "" || strings.Contains(parsed.User.Username(), ":") {
			return false
		}
		password, _ := parsed.User.Password()
		if strings.ContainsFunc(parsed.User.Username()+password, unicode.IsControl) {
			return false
		}
	}
	return true
}

func proxyAdmission(c Capabilities, effects Effects) error {
	settings, err := normalizedProxy(effects.Network, os.Getenv)
	if err != nil {
		return err
	}
	if len(settings) != 0 && c.NetworkProxyVersion != 1 {
		return errors.New("image lacks network_proxy_version=1; select a runtime with controlled proxy and Basic authentication support")
	}
	return nil
}

// Empty assignments override Docker client defaults and image ENV. Configured
// values travel only through the Docker client's environment, never its argv.
func proxyContainerEnvironment(environment []string, settings map[string]string) ([]string, []string) {
	var args []string
	for _, name := range proxyNames {
		if value, configured := settings[name]; configured {
			environment = replaceEnvironment(environment, name, value)
			args = append(args, "--env", name)
		} else {
			args = append(args, "--env", name+"=")
		}
	}
	return args, environment
}
