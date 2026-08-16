"""Small, safe reference renderer for the OpenNV OutputFSM v1alpha1 format.

OutputFSM is deliberately constrained: templates use ``string.Template``
placeholders and variable values can only come from inventory paths, literals,
or a small allow-list of pure generators.  Pack files never execute code.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from string import Template
from typing import Any, Iterable
import re

import yaml


class DefinitionError(ValueError):
    """Raised when a definition is malformed or cannot be rendered safely."""


_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,79}$")
_PATH_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_ALLOWED_TYPES = {"string", "integer", "number", "boolean", "array", "object"}


def _lookup(document: dict[str, Any], path: str) -> Any:
    current: Any = document
    for token in path.split("."):
        if not isinstance(current, dict) or token not in current:
            raise DefinitionError(f"missing source path: {path}")
        current = current[token]
    return current


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    tokens = path.split(".")
    current = document
    for token in tokens[:-1]:
        current = current.setdefault(token, {})
    current[tokens[-1]] = deepcopy(value)


def _generator(name: str, value: Any, options: dict[str, Any]) -> str:
    if name == "identity":
        return str(value)
    if name == "uptime_human":
        seconds = int(value)
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    if name == "yes_no":
        return "yes" if bool(value) else "no"
    if name == "up_down":
        return "up" if bool(value) else "down"
    if name == "percent":
        precision = int(options.get("precision", 1))
        return f"{float(value):.{precision}f}%"
    if name == "join":
        if not isinstance(value, list):
            raise DefinitionError("join generator requires an array")
        return str(options.get("separator", ", ")).join(str(item) for item in value)
    if name == "on_off":
        return "on" if bool(value) else "off"
    raise DefinitionError(f"generator is not allow-listed: {name}")


def _resolve(rule: dict[str, Any], inventory: dict[str, Any]) -> Any:
    choices = sum(key in rule for key in ("source", "literal", "generator"))
    if choices != 1:
        raise DefinitionError("variable rule must set exactly one of source, literal, generator")
    if "literal" in rule:
        return rule["literal"]
    if "source" in rule:
        return _lookup({"inventory": inventory}, str(rule["source"]))
    generator = rule["generator"]
    if not isinstance(generator, dict) or "name" not in generator or "source" not in generator:
        raise DefinitionError("generator requires name and source")
    value = _lookup({"inventory": inventory}, str(generator["source"]))
    return _generator(str(generator["name"]), value, generator)


def load_definition(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    if path.stat().st_size > 1_000_000:
        raise DefinitionError(f"definition exceeds 1 MB safety limit: {path}")
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise DefinitionError(f"definition must be a mapping: {path}")
    return loaded


def render(definition: dict[str, Any], inventory: dict[str, Any]) -> str:
    spec = definition["spec"]
    values = {name: str(_resolve(rule, inventory)) for name, rule in spec["variables"].items()}
    try:
        return Template(spec["template"]).substitute(values)
    except KeyError as exc:
        raise DefinitionError(f"template references undefined variable: {exc.args[0]}") from exc


def normalized_result(definition: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in definition["spec"]["result_schema"]:
        _set_path(result, field["path"], _lookup({"inventory": inventory}, field["source"]))
    return result


def _validate_top_level(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if definition.get("apiVersion") != "opennv.io/v1alpha1":
        errors.append("apiVersion must be opennv.io/v1alpha1")
    if definition.get("kind") != "OutputFSM":
        errors.append("kind must be OutputFSM")
    metadata = definition.get("metadata")
    if not isinstance(metadata, dict) or not _ID_RE.fullmatch(str(metadata.get("id", ""))):
        errors.append("metadata.id must be a lower snake_case identifier")
    if not isinstance(metadata, dict) or metadata.get("synthetic") is not True:
        errors.append("metadata.synthetic must be true")
    spec = definition.get("spec")
    if not isinstance(spec, dict):
        return errors + ["spec must be a mapping"]
    platform = spec.get("platform")
    if not isinstance(platform, str) or not _ID_RE.fullmatch(platform):
        errors.append("spec.platform must be a lower snake_case identifier")
    if not isinstance(spec.get("command"), str) or not spec["command"].strip():
        errors.append("spec.command must be a non-empty string")
    aliases = spec.get("aliases")
    if not isinstance(aliases, list) or not all(isinstance(item, str) and item for item in aliases):
        errors.append("spec.aliases must be a string array")
    if not isinstance(spec.get("template"), str) or not spec["template"]:
        errors.append("spec.template must be non-empty")
    variables = spec.get("variables")
    if not isinstance(variables, dict) or not variables:
        errors.append("spec.variables must be a non-empty mapping")
    result_schema = spec.get("result_schema")
    if not isinstance(result_schema, list) or not result_schema:
        errors.append("spec.result_schema must be a non-empty array")
    else:
        paths: set[str] = set()
        for field in result_schema:
            if not isinstance(field, dict):
                errors.append("every result_schema entry must be a mapping")
                continue
            path = str(field.get("path", ""))
            if not _PATH_RE.fullmatch(path):
                errors.append(f"invalid result path: {path}")
            if path in paths:
                errors.append(f"duplicate result path: {path}")
            paths.add(path)
            if field.get("type") not in _ALLOWED_TYPES:
                errors.append(f"invalid result type for {path}")
            if not str(field.get("source", "")).startswith("inventory."):
                errors.append(f"result source must begin with inventory.: {path}")
    fixtures = spec.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        errors.append("spec.fixtures must be a non-empty array")
    return errors


def validate_definition(definition: dict[str, Any]) -> list[str]:
    errors = _validate_top_level(definition)
    if errors:
        return errors
    spec = definition["spec"]
    placeholders = set(Template.pattern.findall(spec["template"]))
    # findall returns tuples for Template's named/braced groups.
    referenced = {next((part for part in match if part), "") for match in placeholders}
    undefined = sorted(referenced - set(spec["variables"]))
    if undefined:
        errors.append(f"undefined template variables: {', '.join(undefined)}")
    for fixture in spec["fixtures"]:
        name = fixture.get("name", "unnamed") if isinstance(fixture, dict) else "unnamed"
        try:
            inventory = fixture["inventory"]
            actual_output = render(definition, inventory)
            actual_result = normalized_result(definition, inventory)
            if actual_output != fixture.get("expected_output"):
                errors.append(f"fixture {name}: rendered output mismatch")
            if actual_result != fixture.get("expected_result"):
                errors.append(f"fixture {name}: normalized result mismatch")
        except (DefinitionError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"fixture {name}: {exc}")
    return errors


def discover_definitions(root: Path | str) -> Iterable[Path]:
    return sorted(Path(root).glob("packs/*/commands/*.yaml"))
