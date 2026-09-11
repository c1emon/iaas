"""Small version/platform contract shared by runtime preparation and discovery."""

from __future__ import annotations

from dataclasses import dataclass
import platform
import re
from typing import Any

from iaas_automation.common.errors import require


def runtime_platform() -> str:
    architecture = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(platform.machine())
    require(architecture is not None, "unsupported runtime architecture")
    return f"linux/{architecture}"


@dataclass(frozen=True)
class RuntimeSelection:
    image: str
    platform: str
    interface_version: int = 1

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> RuntimeSelection:
        require(set(document) == {"interface_version", "image", "platform"}, "runtime selection needs interface_version, image and platform")
        require(type(document["interface_version"]) is int and document["interface_version"] == 1,
                "unsupported launcher interface version")
        image = document["image"]
        require(isinstance(image, str) and not any(c.isspace() for c in image), "invalid image reference")
        if "@" in image:
            require(re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", image), "invalid image digest")
        else:
            leaf = image.rsplit("/", 1)[-1]
            require(":" in leaf and leaf.rsplit(":", 1)[1] not in {"", "latest"},
                    "select an explicit release tag or digest; latest is unsupported")
        require(document["platform"] in ("linux/amd64", "linux/arm64"),
                "unsupported runtime platform; explicitly select linux/amd64 or linux/arm64")
        return cls(image=image, platform=document["platform"])
