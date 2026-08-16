from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from outputfsm_packs.engine import (
    DefinitionError,
    discover_definitions,
    load_definition,
    normalized_result,
    render,
    validate_definition,
)


class CatalogTests(unittest.TestCase):
    def test_all_definitions_and_fixtures(self) -> None:
        paths = list(discover_definitions(ROOT))
        self.assertEqual(160, len(paths))
        for path in paths:
            with self.subTest(path=path):
                definition = load_definition(path)
                self.assertEqual([], validate_definition(definition))

    def test_twenty_commands_per_platform(self) -> None:
        counts: dict[str, int] = {}
        for path in discover_definitions(ROOT):
            platform = load_definition(path)["spec"]["platform"]
            counts[platform] = counts.get(platform, 0) + 1
        self.assertEqual(8, len(counts))
        self.assertTrue(all(count == 20 for count in counts.values()), counts)

    def test_commands_and_aliases_are_unique_per_platform(self) -> None:
        aliases: dict[str, set[str]] = {}
        for path in discover_definitions(ROOT):
            definition = load_definition(path)
            spec = definition["spec"]
            seen = aliases.setdefault(spec["platform"], set())
            for candidate in [spec["command"], *spec["aliases"]]:
                normalized = " ".join(candidate.lower().split())
                self.assertNotIn(normalized, seen, (path, normalized))
                seen.add(normalized)

    def test_unlisted_generators_cannot_execute(self) -> None:
        path = next(iter(discover_definitions(ROOT)))
        definition = load_definition(path)
        variable = next(name for name in definition["spec"]["variables"] if name not in {"hostname", "command"})
        definition["spec"]["variables"][variable] = {
            "generator": {"name": "eval", "source": "inventory.hostname"}
        }
        with self.assertRaises(DefinitionError):
            render(definition, definition["spec"]["fixtures"][0]["inventory"])

    def test_catalog_index_matches_files(self) -> None:
        import yaml

        with (ROOT / "catalog" / "index.yaml").open("r", encoding="utf-8") as handle:
            catalog = yaml.safe_load(handle)
        indexed = {
            (platform["id"], command["id"])
            for platform in catalog["platforms"]
            for command in platform["commands"]
        }
        files = {
            (definition["spec"]["platform"], definition["metadata"]["id"])
            for definition in (load_definition(path) for path in discover_definitions(ROOT))
        }
        self.assertEqual(indexed, files)

    def test_every_command_has_healthy_and_degraded_vendor_shaped_fixtures(self) -> None:
        for path in discover_definitions(ROOT):
            with self.subTest(path=path):
                definition = load_definition(path)
                fixtures = definition["spec"]["fixtures"]
                self.assertEqual(["healthy", "degraded"], [item["name"] for item in fixtures])
                self.assertNotEqual(fixtures[0]["expected_output"], fixtures[1]["expected_output"])
                self.assertGreaterEqual(len(fixtures[0]["expected_output"].splitlines()), 6)
                records = definition["spec"]["variables"].get("records", {}).get("generator", {})
                self.assertEqual("join", records.get("name"))
                self.assertEqual("inventory.display.records", records.get("source"))
                self.assertEqual("\n", records.get("separator"))
                for fixture in fixtures:
                    self.assertGreaterEqual(len(fixture["inventory"]["display"]["records"]), 4)
                    for line in fixture["expected_output"].splitlines():
                        self.assertNotIn("\t", line)
                        self.assertEqual(line.rstrip(), line)

    def test_degraded_fixture_fails_catalog_validation_hint(self) -> None:
        import yaml

        with (ROOT / "catalog" / "index.yaml").open("r", encoding="utf-8") as handle:
            catalog = yaml.safe_load(handle)
        hints = {
            (platform["id"], command["id"]): command["validation_hint"]
            for platform in catalog["platforms"]
            for command in platform["commands"]
        }

        def lookup(document: dict, path: str):
            current = document
            for token in path.split("."):
                current = current[token]
            return current

        operators = {
            "eq": lambda actual, expected: actual == expected,
            "lte": lambda actual, expected: actual <= expected,
            "gte": lambda actual, expected: actual >= expected,
        }
        for path in discover_definitions(ROOT):
            with self.subTest(path=path):
                definition = load_definition(path)
                key = (definition["spec"]["platform"], definition["metadata"]["id"])
                hint = hints[key]
                healthy, degraded = definition["spec"]["fixtures"]
                healthy_result = normalized_result(definition, healthy["inventory"])
                degraded_result = normalized_result(definition, degraded["inventory"])
                operation = operators[hint["operator"]]
                self.assertTrue(operation(lookup(healthy_result, hint["path"]), hint["expected"]))
                self.assertFalse(operation(lookup(degraded_result, hint["path"]), hint["expected"]))


if __name__ == "__main__":
    unittest.main()
