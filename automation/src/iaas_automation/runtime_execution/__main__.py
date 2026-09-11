"""Shared container interface used by local Docker and DinD launchers."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from typing import cast

from iaas_automation.common.errors import require
from iaas_automation.common.io import write_text
from iaas_automation.runtime_config import InputRequired, SourceReader
from iaas_automation.runtime_config.compile import compile_documents
from .components import IMPLEMENTATION, run_component
from .credentials import AWS_FILE_VARIABLES, prepare_file_credentials
from .dependencies import prepare_dependencies
from .execution import Execution
from .operations import capabilities, credential_names, operation_for, process_environment
from .outputs import TaskOutputs
from .plans import apply_saved_plan, prepare_plan
from .root import materialize_root
from .selection import load_operation, rendering_credentials
from .state import S3Backend


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["capabilities"]:
        print(json.dumps(capabilities()))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--component", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--scenario")
    parser.add_argument("--scope", default="")
    parser.add_argument("--input-map", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--image-digest", default="")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--companions", type=Path)
    parser.add_argument("--discover", action="store_true")
    args = parser.parse_args(argv)
    execution = None
    outputs = None
    try:
        effects = operation_for(args.component, args.operation)
        mapping = json.loads(args.input_map.read_text()) if args.input_map else None
        reader = SourceReader(mapping)
        selected = load_operation(args.environment, args.component, args.operation, args.scenario, reader)
        render_names = rendering_credentials(selected, args.operation)
        allowed = credential_names(args.component, args.operation, render_names)
        # Explicit aliases win over host file channels, before the launcher
        # attempts to discover or transfer any stale host paths.
        allowed -= {variable for alias, variable in AWS_FILE_VARIABLES.items() if alias in selected.files}
        if args.discover:
            print(json.dumps({"status": "ready", "credential_names": sorted(allowed), "effects": asdict(effects),
                              "sources": sorted(map(str, reader.logical_sources))}))
            return 0
        require(args.output is not None, "operation requires an explicit output directory")
        require(not effects.network or bool(args.scope), "online operation requires explicit scope")
        protected = list(reader.sources)
        if args.companions:
            protected.append(args.companions)
        if args.plan:
            protected.append(args.plan)
        outputs = TaskOutputs.create(args.output, IMPLEMENTATION, protected)
        environ = process_environment(args.component, args.operation, os.environ, render_names)
        prepare_file_credentials(selected.files, outputs.path("work") / "home", environ)
        execution = Execution(outputs, environ)
        common = {"component": args.component, "operation": args.operation, "environment": selected.environment,
                  "scenario": selected.scenario, "image_digest": args.image_digest, "effects": asdict(effects),
                  "input_origins": sorted(map(str, reader.logical_sources))}
        if not effects.network:
            generated = compile_documents(selected)
            if args.operation != "check":
                for name, contents in generated.items():
                    write_text(outputs.path("generated") / name, contents)
            execution.finish(common)
        elif args.operation == "prepare-dependencies":
            require(args.scope == selected.options["root"]["id"], "dependency scope must name the complete root")
            root = materialize_root(selected.options["root"], selected.files, outputs.path("work") / "workspace")
            prepare_dependencies(root, execution, outputs.path("plan") / "dependencies.tar.gz")
            execution.finish(common)
        elif effects.state:
            backend = S3Backend.load(selected.files["backend"])
            if args.operation == "apply-saved-plan":
                require(args.plan is not None and args.companions is not None, "saved apply requires --plan and --companions")
                apply_saved_plan(cast(Path, args.plan), cast(Path, args.companions), selected, execution, backend, args.scope, args.image_digest)
            else:
                prepare_plan(selected, execution, backend, args.scope, args.image_digest)
        else:
            run_component(selected, args.operation, args.scope, execution)
        print(json.dumps({"status": "success", "output": str(outputs.root), "effects": asdict(effects),
                          "phases": [{"phase": item["phase"], "exit_code": item.get("exit_code")} for item in execution.phases]}))
        return 0
    except InputRequired as exc:
        print(json.dumps({"status": "input-required", "path": str(exc.path)}))
        return 3
    except Exception as exc:
        # Domain/native exceptions can contain credential-bearing values. Public
        # failures name phases only; original tool details stay in protected files.
        code = 2
        phases = []
        retained = False
        if execution is not None:
            phases = execution.phases
            if phases:
                code = phases[-1].get("exit_code") or 2
            retained = any(item.get("retain_storage", False) for item in phases)
            try:
                execution.outputs.summary({"status": "failed", "phases": phases, "retain_storage": retained})
            except OSError:
                retained = True
        # Only literal, value-free diagnostics are safe to surface. Never
        # expose arbitrary ValidationError text from domain parsers.
        safe_reasons = {
            "expected schema_version: 1; migrate the entry explicitly",
            "unsupported component/operation combination",
            "unknown scenario; no default fallback",
            "unknown environment entry field",
            "environment must be a logical name",
            "unknown scenario component",
            "unknown component field",
            "selected component needs explicit inputs",
            "required operation input is missing",
            "required operation file is missing",
            "declared input is not readable YAML",
            "declared input must contain a mapping",
            "declared input must be a readable regular file",
            "file reference must be a nonempty path",
            "$ref must occupy the entire node",
            "$ref must name a shared fact",
            "$ref must use facts.name.field",
            "cyclic shared-fact reference",
            "shared-fact source is not declared",
            "shared-fact field is missing",
            "saved companion file list is missing; prepare the plan again",
            "saved companion file is missing or outside its bundle",
            "deployment scope: must explicitly select all declared nodes (whole cluster); partial scope is not allowed",
            "upgrade scope: must explicitly select all declared nodes (whole cluster); partial scope is not allowed",
            "PVE scope must explicitly select the complete declared root id",
            "PVE diagnostic scope must explicitly name the complete cluster",
            "foundation health scope must explicitly name the declared environment",
            "scope includes hosts outside the selected component",
            "OPNsense diagnostics requires exactly one target",
            "online operation requires explicit scope",
        }
        safe_reasons |= {f"{field} {problem}" for field in (
            "components", "scenarios", "selected scenario", "selected component",
            "component inputs", "facts", "component files", "component options",
        ) for problem in ("must be a mapping", "keys must be strings")}
        reason = str(exc) if str(exc) in safe_reasons else "selected operation failed validation, setup or execution"
        print(json.dumps({"status": "failed", "reason": reason,
                          "output": str(outputs.root) if outputs else None,
                          "exit_code": code, "retain_storage": retained,
                          "phases": [{"phase": item["phase"], "exit_code": item.get("exit_code")} for item in phases]}))
        return code


if __name__ == "__main__":
    raise SystemExit(main())
