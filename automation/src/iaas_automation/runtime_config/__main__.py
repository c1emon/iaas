"""Offline component compilation and file discovery for the native launcher."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from iaas_automation.common.errors import ValidationError
from .compile import compile_documents, export_generated
from .loader import COMPONENTS, InputRequired, SourceReader, load_environment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True, type=Path)
    parser.add_argument("--component", required=True, choices=sorted(COMPONENTS))
    parser.add_argument("--scenario")
    parser.add_argument("--operation", choices=["discover", "check", "generate"], default="check")
    parser.add_argument("--input-map", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        mapping = json.loads(args.input_map.read_text()) if args.input_map else None
        selected = load_environment(args.environment, args.component, args.scenario, SourceReader(mapping))
        if args.operation == "discover":
            print(json.dumps({"status": "ready", "sources": sorted(map(str, selected.reader.logical_sources))}))
            return 0
        if args.operation == "generate":
            if args.output is None:
                raise ValidationError("generate requires --output")
            export_generated(selected, Path(__file__).resolve().parents[4], args.output)
        else:
            compile_documents(selected)
        print(json.dumps({"status": "success", "component": args.component, "operation": args.operation}))
        return 0
    except InputRequired as exc:
        print(json.dumps({"status": "input-required", "path": str(exc.path)}))
        return 3
    except ValidationError as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}))
        return 2
    except (OSError, ValueError):
        print(json.dumps({"status": "error", "reason": "configuration or output could not be processed"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
