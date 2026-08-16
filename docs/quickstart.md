# Quickstart

## Prerequisites

Use Python 3.11 or newer and Git.

```bash
git clone https://github.com/open-nv/outputfsm-packs.git
cd outputfsm-packs
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
make check
```

The check validates the schema, exact eight-platform catalog cardinality,
command and alias uniqueness, every variable mapping, and all deterministic
fixtures. It then executes the reference-engine unit tests.

## Inspect one command

Resolve commands through `catalog/index.yaml`, then open the referenced file:

```bash
python - <<'PY'
from pathlib import Path
import yaml

root = Path.cwd()
catalog = yaml.safe_load((root / "catalog/index.yaml").read_text())
platform = next(item for item in catalog["platforms"] if item["id"] == "cisco_ios")
command = next(item for item in platform["commands"] if item["command"] == "show version")
print(command)
PY
```

## Render the checked-in fixture

```bash
PYTHONPATH=src python - <<'PY'
from pathlib import Path
from outputfsm_packs.engine import load_definition, render

path = Path("packs/cisco_ios/commands/show_version.yaml")
definition = load_definition(path)
fixture = definition["spec"]["fixtures"][0]
print(render(definition, fixture["inventory"]), end="")
PY
```

This renders synthetic fixture text only; it does not contact a device.

## Change the generated catalog

Edit the reviewed matrix in `scripts/generate.py`, then run:

```bash
make generate
make check
make reproducible
```

Inspect the full generated diff. A command or normalized-path change also
requires a coordinated update to `validation-packs` and its integration test.
Read [CONTRIBUTING.md](../CONTRIBUTING.md) before submitting content.
