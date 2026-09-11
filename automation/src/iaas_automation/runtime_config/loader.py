"""Resolve selected YAML inputs without evaluating templates or unrelated scenes.

SourceReader also supports the launcher discovery protocol: logical client paths
are mapped to individual supplied files, never interpreted as daemon paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
import os
import re

import yaml

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.runtime_paths import validate_paths


COMPONENTS = {"opnsense", "switch", "pve", "services", "foundation", "k3s"}
NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")


class InputRequired(Exception):
    """An explicit client file must be supplied before discovery can continue."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__("declared input is not supplied")


@dataclass
class SourceReader:
    mapping: dict[str, str] | None = None
    sources: set[Path] = field(default_factory=set)
    logical_sources: set[Path] = field(default_factory=set)

    def locate(self, logical: Path) -> Path:
        require(logical.is_absolute(), "source paths must be absolute")
        # Do not resolve a client path against the container's filesystem.
        if self.mapping is not None:
            if str(logical) not in self.mapping:
                raise InputRequired(logical)
            supplied = Path(self.mapping[str(logical)])
            require(not supplied.is_symlink(), "supplied input must not be a symlink")
            path = supplied.resolve()
        else:
            path = logical.resolve()
        require(path.is_file(), "declared input must be a readable regular file")
        self.sources.add(path)
        self.logical_sources.add(logical)
        return path

    def document(self, logical: Path) -> dict[str, Any]:
        path = self.locate(logical)
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError):
            # YAML parser errors can contain source values, including secrets.
            raise ValidationError("declared input is not readable YAML") from None
        require(isinstance(value, dict), "declared input must contain a mapping")
        return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be a mapping")
    require(all(isinstance(key, str) for key in value), f"{label} keys must be strings")
    return value


def _path(value: Any, declaring: Path) -> Path:
    require(isinstance(value, str) and bool(value), "file reference must be a nonempty path")
    path = Path(value)
    # abspath normalizes '..' without consulting the daemon filesystem.
    return Path(os.path.abspath(path if path.is_absolute() else declaring.parent / path))


@dataclass
class SelectedConfig:
    environment: str
    component: str
    scenario: str | None
    documents: dict[str, dict[str, Any]]
    input_paths: dict[str, Path]
    files: dict[str, Path]
    options: dict[str, Any]
    reader: SourceReader

    def protect_outputs(self, implementation: Path, *outputs: Path) -> None:
        validate_paths(None, implementation, list(outputs), list(self.reader.sources))


def load_environment(
    entry: Path, component: str, scenario: str | None = None,
    reader: SourceReader | None = None,
) -> SelectedConfig:
    """Load one component; scenario mappings replace rather than merge defaults."""
    require(component in COMPONENTS, "unsupported component")
    reader = reader if reader is not None else SourceReader()
    entry = Path(os.path.abspath(entry))
    config = reader.document(entry)
    require(type(config.get("schema_version")) is int and config["schema_version"] == 1,
            "expected schema_version: 1; migrate the entry explicitly")
    require(not config.keys() - {"schema_version", "environment", "facts", "components", "scenarios"},
            "unknown environment entry field")
    environment = config.get("environment")
    require(isinstance(environment, str) and NAME.fullmatch(environment), "environment must be a logical name")
    components = _mapping(config.get("components", {}), "components")
    selected = components.get(component)
    if scenario is not None:
        scenes = _mapping(config.get("scenarios", {}), "scenarios")
        require(scenario in scenes, "unknown scenario; no default fallback")
        replacement = _mapping(scenes[scenario], "selected scenario")
        require(not replacement.keys() - COMPONENTS, "unknown scenario component")
        if component in replacement:
            selected = replacement[component]
    selected = _mapping(selected, "selected component")
    require(not selected.keys() - {"inputs", "files", "options"}, "unknown component field")
    inputs = _mapping(selected.get("inputs", {}), "component inputs")
    require(bool(inputs), "selected component needs explicit inputs")
    facts = _mapping(config.get("facts", {}), "facts")
    fact_docs: dict[str, Any] = {}

    def resolve(value: Any, stack: tuple[str, ...] = ()) -> Any:
        if isinstance(value, list):
            return [resolve(item, stack) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" not in value:
            return {key: resolve(item, stack) for key, item in value.items()}
        require(set(value) == {"$ref"}, "$ref must occupy the entire node")
        ref = value["$ref"]
        require(isinstance(ref, str), "$ref must name a shared fact")
        parts = ref.split(".")
        require(len(parts) >= 3 and parts[0] == "facts" and all(parts), "$ref must use facts.name.field")
        require(ref not in stack, "cyclic shared-fact reference")
        name = parts[1]
        require(name in facts, "shared-fact source is not declared")
        if name not in fact_docs:
            fact_docs[name] = reader.document(_path(facts[name], entry))
        result = fact_docs[name]
        for part in parts[2:]:
            # Resolve aliases on the reachable path, not the whole fact file.
            if isinstance(result, dict) and "$ref" in result:
                result = resolve(result, (*stack, ref))
            require(isinstance(result, dict) and part in result, "shared-fact field is missing")
            result = result[part]
        return resolve(result, (*stack, ref))

    paths: dict[str, Path] = {}
    documents: dict[str, dict[str, Any]] = {}
    for name, source in inputs.items():
        require(NAME.fullmatch(name), "input name must be a logical name")
        paths[name] = _path(source, entry)
        documents[name] = resolve(reader.document(paths[name]))
    files = {}
    for name, source in _mapping(selected.get("files", {}), "component files").items():
        require(NAME.fullmatch(name), "file name must be a logical name")
        logical = _path(source, entry)
        files[name] = reader.locate(logical)
    options = resolve(_mapping(selected.get("options", {}), "component options"))
    return SelectedConfig(cast(str, environment), component, scenario, documents, paths, files, options, reader)
