"""Check execution output locations before a generator or tool writes files."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path


def validate_paths(environment: Path | None, implementation: Path, outputs: list[Path], inputs: Sequence[Path] = ()) -> None:
    """Allow committed generated subtrees, but never overwrite authored inputs."""
    environment = environment.resolve() if environment is not None else None
    implementation = implementation.resolve()
    protected = [implementation, *(path.resolve() for path in inputs)]
    if environment is not None:
        protected.extend([environment / "inventory", environment / "ansible"])
    for output in outputs:
        output = output.resolve()
        if environment is not None and (output == environment or output in environment.parents):
            raise ValueError("output must not contain the environment directory")
        for source in protected:
            if output == source or source in output.parents or output in source.parents:
                raise ValueError("output overlaps authored inputs or implementation resources")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", type=Path)
    parser.add_argument("--implementation", required=True, type=Path)
    parser.add_argument("--output", action="append", required=True, type=Path)
    parser.add_argument("--input", action="append", default=[], type=Path)
    args = parser.parse_args()
    try:
        validate_paths(args.environment, args.implementation, args.output, args.input)
    except ValueError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
