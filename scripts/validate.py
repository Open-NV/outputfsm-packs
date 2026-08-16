#!/usr/bin/env python3
"""Validate every OutputFSM pack and print a machine-readable summary."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import sys

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from outputfsm_packs.engine import discover_definitions, load_definition, validate_definition  # noqa: E402


def main() -> int:
    with (ROOT / "schema" / "outputfsm-v1alpha1.schema.json").open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    schema_validator = Draft202012Validator(schema)
    paths = list(discover_definitions(ROOT))
    errors: list[str] = []
    counts: Counter[str] = Counter()
    identities: set[tuple[str, str]] = set()
    aliases: dict[str, set[str]] = {}
    fixtures = 0
    for path in paths:
        definition = load_definition(path)
        for schema_error in schema_validator.iter_errors(definition):
            location = ".".join(str(part) for part in schema_error.absolute_path) or "<root>"
            errors.append(f"{path}: JSON Schema at {location}: {schema_error.message}")
        platform = definition.get("spec", {}).get("platform", "unknown")
        command = definition.get("spec", {}).get("command", "")
        counts[platform] += 1
        fixtures += len(definition.get("spec", {}).get("fixtures", []))
        identity = (platform, command.lower().strip())
        if identity in identities:
            errors.append(f"{path}: duplicate canonical command {identity}")
        identities.add(identity)
        platform_aliases = aliases.setdefault(platform, set())
        for alias in [command, *definition.get("spec", {}).get("aliases", [])]:
            normalized = " ".join(alias.lower().split())
            if normalized in platform_aliases:
                errors.append(f"{path}: duplicate command or alias {normalized!r}")
            platform_aliases.add(normalized)
        spec = definition.get("spec", {})
        scenario_fixtures = spec.get("fixtures", [])
        if [item.get("name") for item in scenario_fixtures] != ["healthy", "degraded"]:
            errors.append(f"{path}: fixtures must be ordered healthy, degraded")
        records_rule = spec.get("variables", {}).get("records", {}).get("generator", {})
        if records_rule != {
            "name": "join",
            "source": "inventory.display.records",
            "separator": "\n",
        }:
            errors.append(f"{path}: records must use the deterministic newline join generator")
        for fixture in scenario_fixtures:
            fixture_name = fixture.get("name", "unnamed")
            record_values = fixture.get("inventory", {}).get("display", {}).get("records", [])
            if not isinstance(record_values, list) or len(record_values) < 4:
                errors.append(f"{path}: fixture {fixture_name}: expected at least four representative records")
            output_lines = fixture.get("expected_output", "").splitlines()
            if len(output_lines) < 6:
                errors.append(f"{path}: fixture {fixture_name}: output is not structurally rich enough")
            for line_number, line in enumerate(output_lines, start=1):
                if "\t" in line or line.rstrip() != line:
                    errors.append(
                        f"{path}: fixture {fixture_name}: unsafe whitespace on output line {line_number}"
                    )
        errors.extend(f"{path}: {message}" for message in validate_definition(definition))
    expected_platforms = {
        "cisco_ios", "cisco_iosxe", "cisco_nxos", "cisco_iosxr",
        "arista_eos", "juniper_junos", "f5_tmos", "citrix_adc",
    }
    if set(counts) != expected_platforms:
        errors.append(f"platform set mismatch: {sorted(counts)}")
    for platform in expected_platforms:
        if counts[platform] != 20:
            errors.append(f"{platform}: expected exactly 20 definitions, found {counts[platform]}")
    summary = {
        "definitions": len(paths),
        "fixtures": fixtures,
        "platform_counts": dict(sorted(counts.items())),
        "errors": errors,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
