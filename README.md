# OpenNV OutputFSM Packs

OutputFSM is the inverse of TextFSM: it renders deterministic, vendor-shaped
network CLI output from structured inventory data. These packs let OpenNV test
automation against a network that does not exist yet, without connecting to a
device or embedding executable code in a definition.

This initial catalog contains **160 command definitions and 320 deterministic
fixtures**—20 commands for each of eight platforms. Every command includes a
healthy baseline and a degraded scenario:

| Platform | Canonical ID | Commands |
| --- | --- | ---: |
| Cisco IOS | `cisco_ios` | 20 |
| Cisco IOS XE | `cisco_iosxe` | 20 |
| Cisco NX-OS | `cisco_nxos` | 20 |
| Cisco IOS XR | `cisco_iosxr` | 20 |
| Arista EOS | `arista_eos` | 20 |
| Juniper Junos | `juniper_junos` | 20 |
| F5 BIG-IP TMOS | `f5_tmos` | 20 |
| Citrix ADC / NetScaler | `citrix_adc` | 20 |

## Important fixture notice

All CLI text, names, serials, versions, metrics, and observations in this
repository are **original synthetic fixtures**. They are not captures from
vendor devices and are not claimed to reproduce every formatting edge case of
a vendor CLI. Command names identify interoperability targets; vendor names and
marks belong to their respective owners.

The layouts deliberately use recognizable vendor conventions—hierarchical
sections, table headings, representative record rows, prompts, and summaries—
so UI, orchestration, and validation testing has useful structure. They are not
claimed to be byte-compatible with NTC Templates, TextFSM, Genie, TTP, or any
other parser. Parser compatibility must be established by separate, versioned
conformance fixtures before it is advertised.

## Definition model

An OutputFSM definition contains:

- a canonical platform and command plus aliases;
- a `${variable}` template;
- variable rules that read inventory paths, use literals, or invoke an
  allow-listed pure generator;
- deterministic representative record arrays rendered with the safe `join`
  generator;
- a normalized result schema consumed by validation packs; and
- paired deterministic healthy/degraded input, output, and result fixtures.

Example excerpt:

```yaml
apiVersion: opennv.io/v1alpha1
kind: OutputFSM
metadata:
  id: show_version
  synthetic: true
spec:
  platform: cisco_ios
  command: show version
  aliases: [sh version]
  variables:
    hostname:
      source: inventory.hostname
    uptime:
      generator:
        name: uptime_human
        source: inventory.system.uptime_seconds
    records:
      generator:
        name: join
        source: inventory.display.records
        separator: "\n"
  template: |
    ${hostname}#${command}
    ${records}
    System uptime: ${uptime}
```

Pack files cannot execute Python, shell, Starlark, or template expressions.
The reference engine uses `yaml.safe_load`, `string.Template`, a 1 MB file
limit, explicit inventory paths, and a fixed generator allow-list.

## Repository layout

```text
catalog/index.yaml                 machine-readable full catalog
packs/<platform>/index.yaml        per-platform command catalog
packs/<platform>/commands/*.yaml   one OutputFSM definition per command
schema/                            JSON Schema contract
src/outputfsm_packs/               safe reference renderer and linter
scripts/generate.py                deterministic catalog generator
scripts/validate.py                full catalog/fixture validator
tests/                             standard-library unit tests
```

## Validate locally

Python 3.11+, PyYAML 6, and jsonschema 4 are required for the development checks.

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
```

The validator checks exact platform counts, canonical command and alias
uniqueness, schema rules, template mappings, source paths, paired scenario
coverage, deterministic rendered output, whitespace safety, and normalized
results. It exits nonzero on any error.

For a guided first render, see [docs/quickstart.md](docs/quickstart.md). The
[architecture guide](docs/architecture.md) documents repository boundaries,
consumer relationships, and compatibility rules.

To prove generated files are reproducible:

```bash
python3 scripts/generate.py
python3 scripts/validate.py
git diff --exit-code
```

## Compatibility and versioning

`apiVersion: opennv.io/v1alpha1` is intentionally explicit. Compatible fields
may be added during alpha. Breaking semantic changes require a new API version.
Consumers should resolve a platform/command through `catalog/index.yaml`, then
load the referenced definition.

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[development context](docs/development-context.md) before adding platform
content. Security reports follow [SECURITY.md](SECURITY.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
