"""SKS8300 running-configuration redaction."""

from __future__ import annotations

import re


def redact_switch_running_config(config: str) -> str:
    """Redact common plaintext/reversible switch management secrets."""
    redactors = [
        re.compile(r"^(\s*username\s+\S+.*\bpassword\s+(?:0|7|encrypted)?\s+)(\S+)(.*)$", re.IGNORECASE),
        re.compile(r"^(\s*(?:enable\s+)?password\s+(?:0|7|encrypted)?\s+)(\S+)(.*)$", re.IGNORECASE),
        re.compile(r"^(\s*(?:auth-secret-key|acct-secret-key)\s+)(\S+)(.*)$", re.IGNORECASE),
        re.compile(r"^(\s*snmp-server\s+community\s+)(\S+)(.*)$", re.IGNORECASE),
        re.compile(r"^(\s*(?:radius-server|tacacs-server).*\b(?:secret|key)\s+)(\S+)(.*)$", re.IGNORECASE),
    ]
    redacted_lines: list[str] = []
    for line in config.splitlines():
        redacted = line
        for pattern in redactors:
            redacted = pattern.sub(r"\1<redacted>\3", redacted)
        redacted_lines.append(redacted)
    return "\n".join(redacted_lines) + ("\n" if config.endswith("\n") else "")
