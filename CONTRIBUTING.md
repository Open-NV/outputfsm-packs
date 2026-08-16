# Contributing to OpenNV OutputFSM Packs

Thank you for helping make network automation testable without production
devices.

By submitting a contribution, you agree that it is licensed under Apache-2.0
and that you have the right to submit it. Please follow the
[Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities through
[SECURITY.md](SECURITY.md), not a public issue.

## Content rules

1. Submit original synthetic output. Do not paste device captures, vendor
   documentation examples, secrets, addresses, serials, or customer data.
2. Use the canonical lowercase platform ID and a stable lower snake-case
   command ID.
3. Add aliases only when they resolve unambiguously within that platform.
4. Map every placeholder to an inventory source, literal, or existing safe
   generator. Pack files must never execute code.
5. Declare every normalized result path and its type.
6. Include deterministic `healthy` and `degraded` fixtures with both expected
   CLI output and expected normalized data. The degraded fixture must fail the
   command's catalog validation hint.
7. Use recognizable vendor hierarchy, headings, and representative record rows
   where useful. Keep output purpose-built: the goal is automation behavior,
   not a byte-for-byte clone of proprietary CLI output.
8. Keep generated output free of tabs and trailing whitespace. Use the
   allow-listed `join` generator for deterministic multi-record blocks.
9. Do not claim NTC Templates, TextFSM, Genie, TTP, or other parser compatibility
   without separate conformance fixtures that prove it for an explicit version.

The current v1 catalog is generated from the reviewed matrix in
`scripts/generate.py`. Change that matrix and regenerate instead of editing
generated definitions by hand.

## Required checks

```bash
python3 scripts/generate.py
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
git diff --check
```

Pull requests should explain the automation scenario enabled, platform/version
scope, new normalized paths, and why the synthetic fixture is representative.

For contract changes, describe compatibility impact and coordinate updates to
validation-packs and consuming engines. All required GitHub checks and review
must pass before merge.

## Security

Do not open a public issue containing credentials or production output. Follow
the private process in [SECURITY.md](SECURITY.md).
