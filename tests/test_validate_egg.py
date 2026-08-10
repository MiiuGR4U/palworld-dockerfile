from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_egg import BOOLEAN_RULE, validate_egg, validate_egg_data  # noqa: E402


class EggValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.egg_path = PROJECT_ROOT / "egg-palworld-arm64.json"
        cls.baseline = json.loads(cls.egg_path.read_text(encoding="utf-8"))

    def report_for(self, mutate=None):
        data = copy.deepcopy(self.baseline)
        if mutate:
            mutate(data)
        return validate_egg_data(data)

    def test_repository_egg_passes(self):
        report = validate_egg(self.egg_path)
        self.assertTrue(report.ok, report.errors)

    def test_invalid_json_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "egg.json"
            path.write_text("{not-json", encoding="utf-8")
            report = validate_egg(path)
        self.assertFalse(report.ok)
        self.assertTrue(any("Invalid Egg JSON" in error for error in report.errors))

    def test_reserved_variable_fails(self):
        report = self.report_for(
            lambda data: data["variables"].append(
                {
                    "name": "Bad",
                    "env_variable": "SERVER_PORT",
                    "default_value": "8211",
                    "rules": "required|integer",
                }
            )
        )
        self.assertTrue(any("Reserved" in error for error in report.errors))

    def test_duplicate_variable_is_case_insensitive(self):
        duplicate = copy.deepcopy(self.baseline["variables"][0])
        duplicate["env_variable"] = duplicate["env_variable"].lower()
        report = self.report_for(lambda data: data["variables"].append(duplicate))
        self.assertTrue(any("Duplicate" in error for error in report.errors))

    def test_hydrodactyl_boolean_rule_is_required(self):
        def mutate(data):
            variable = next(v for v in data["variables"] if v["env_variable"] == "USE_AUTH")
            variable["rules"] = "required|boolean"

        report = self.report_for(mutate)
        self.assertTrue(any(BOOLEAN_RULE in error for error in report.errors))

    def test_use_auth_must_default_false(self):
        def mutate(data):
            variable = next(v for v in data["variables"] if v["env_variable"] == "USE_AUTH")
            variable["default_value"] = "true"

        report = self.report_for(mutate)
        self.assertTrue(any("USE_AUTH" in error for error in report.errors))

    def test_public_port_must_not_be_declared(self):
        report = self.report_for(
            lambda data: data["variables"].append(
                {
                    "name": "Public port",
                    "env_variable": "PUBLIC_PORT",
                    "default_value": "8211",
                    "rules": "required|integer",
                }
            )
        )
        self.assertTrue(any("PUBLIC_PORT" in error for error in report.errors))

    def test_missing_query_port_fails(self):
        def mutate(data):
            data["variables"] = [
                v for v in data["variables"] if v["env_variable"] != "QUERY_PORT"
            ]

        report = self.report_for(mutate)
        self.assertTrue(any("QUERY_PORT" in error for error in report.errors))

    def test_missing_docker_image_fails(self):
        report = self.report_for(lambda data: data.update({"docker_images": {}}))
        self.assertTrue(any("docker_images" in error for error in report.errors))

    def test_package_manager_in_installer_fails(self):
        def mutate(data):
            data["scripts"]["installation"]["script"] += "\napt-get update\n"

        report = self.report_for(mutate)
        self.assertTrue(any("package manager" in error for error in report.errors))

    def test_dangerous_mod_default_fails_when_flag_exists(self):
        def mutate(data):
            data["variables"].append(
                {
                    "name": "Mods Enabled",
                    "env_variable": "MODS_ENABLED",
                    "default_value": "true",
                    "rules": BOOLEAN_RULE,
                }
            )

        report = self.report_for(mutate)
        self.assertTrue(any("MODS_ENABLED" in error for error in report.errors))


if __name__ == "__main__":
    unittest.main()
