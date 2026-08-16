# Development context

## Repository contract

This repository owns only declarative OutputFSM content, its schema, safe
reference renderer/linter, deterministic generator, and conformance fixtures.
It does not own network connections, scheduling, inventory synchronization,
validation policy, or the product UI.

## Invariants

1. The catalog contains exactly 20 commands for each of the eight supported
   platform IDs unless a reviewed version change says otherwise.
2. Canonical commands and aliases are unique within a platform.
3. Every template token has one explicit safe source.
4. Every definition publishes normalized result paths and types.
5. Healthy and degraded fixtures are deterministic and entirely synthetic.
6. Generated output contains no tabs, trailing whitespace, credentials,
   production data, or vendor-copyrighted captures.
7. Pack documents cannot execute general-purpose code or supply arbitrary
   regular expressions.
8. `scripts/generate.py` and checked-in generated content remain reproducible.

## Change routing

- Change the reviewed generator matrix for catalog content, then regenerate.
- Change `schema/` and the reference engine together for a document-contract
  change, with negative tests and a compatibility decision.
- Coordinate command ID or normalized-path changes with `validation-packs`, the
  CliSynth engine, the OpenNV executor, and shared contracts as applicable.

Run `make check` for every change and `make reproducible` for generated content.
Use `make integration` from `validation-packs` when both repositories are
checked out as siblings.
