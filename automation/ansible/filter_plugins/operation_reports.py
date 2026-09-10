"""Sanitized switch previews and caller-owned report locations."""

from pathlib import Path
import re
import sys

_AUTOMATION_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_AUTOMATION_SRC) not in sys.path:
    sys.path.insert(0, str(_AUTOMATION_SRC))

from iaas_automation.runtime_paths import validate_paths


def protected_report_directory(base, target, environment=None):
    if not isinstance(target, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", target):
        raise ValueError("report target must be a safe inventory name")
    if not isinstance(base, str) or not base.strip() or not Path(base).is_absolute():
        raise ValueError("report directory must be an explicit absolute path")
    path = Path(base) / target
    validate_paths(Path(environment) if environment else None,
                   Path(__file__).resolve().parents[2], [path])
    if path.is_symlink() or path.resolve().parent != Path(base).resolve():
        raise ValueError("report target must remain inside the report directory")
    return str(path)


def switch_plan_summary(previews):
    """Show object changes without commands, descriptions or address values."""
    keys = {"vlans": ("vlan_id",), "acls": ("acl_id",),
            "static_routes": ("destination", "mask", "route_type")}
    rows = []
    for kind, registered in previews.items():
        for call, result in enumerate(registered.get("results", []), 1):
            if result.get("skipped"):
                continue
            before, after = result.get("before"), result.get("after")
            identity = keys.get(kind, ("name",))
            def indexed(objects):
                if isinstance(objects, dict) and kind in {
                    "base_interfaces", "lag_interfaces", "l2_interfaces", "l3_interfaces"
                }:
                    normalized = []
                    for name, obj in objects.items():
                        if not isinstance(obj, dict) or obj.get("name", name) != name:
                            raise ValueError("native preview has ambiguous object identity")
                        normalized.append({"name": name, **obj})
                    objects = normalized
                if not isinstance(objects, list):
                    raise ValueError("native preview lacks before/after observations")
                mapped = {}
                for obj in objects:
                    if not isinstance(obj, dict):
                        raise ValueError("native preview has malformed object observations")
                    key = tuple(str(obj.get(field, "")) for field in identity)
                    if not any(key) or key in mapped:
                        raise ValueError("native preview has ambiguous object identity")
                    mapped[key] = obj
                return mapped
            old, new = indexed(before), indexed(after)
            for ordinal, key in enumerate(sorted(old.keys() | new.keys()), 1):
                left, right = old.get(key, {}), new.get(key, {})
                if left == right:
                    continue
                label = "/".join(key)
                if kind == "static_routes" or not re.fullmatch(r"[A-Za-z0-9_ ./:-]{1,128}", label):
                    label = f"object-{ordinal}"
                rows.append({"resource": kind, "call": call, "object": label,
                             "change": "added" if key not in old else "removed" if key not in new else "updated",
                             "fields": sorted(field for field in left.keys() | right.keys()
                                              if left.get(field) != right.get(field))})
    return {"schema_version": 1, "changed_objects": len(rows), "changes": rows}


class FilterModule:
    def filters(self):
        return {"protected_report_directory": protected_report_directory,
                "switch_plan_summary": switch_plan_summary}
