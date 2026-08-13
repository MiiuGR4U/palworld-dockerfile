from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RepositoryContractTests(unittest.TestCase):
    def test_vanilla_path_has_no_global_preload(self):
        entrypoint = (PROJECT_ROOT / "pterodactyl-entrypoint.sh").read_text(encoding="utf-8")
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertNotIn("ENV LD_PRELOAD", dockerfile)
        self.assertNotIn("export LD_PRELOAD", entrypoint)

    def test_fex_uses_authoritative_rootfs_variable(self):
        entrypoint = (PROJECT_ROOT / "pterodactyl-entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("FEX_ROOTFS", entrypoint)
        self.assertNotIn("FEX_ROOTFS_PATH", entrypoint)

    def test_upstream_manager_entry_path_is_preserved(self):
        entrypoint = (PROJECT_ROOT / "pterodactyl-entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("exec python -u /scripts/ptero_manager.py", entrypoint)
        self.assertNotIn("/entrypoint.sh", entrypoint)

    def test_image_declares_non_root_runtime(self):
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER steam", dockerfile)
        self.assertIn("/opt/palworld-mod-runtime/palmodctl", dockerfile)
        self.assertIn("DEPOT_DOWNLOADER_SHA256", dockerfile)
        self.assertIn("UE4SS_ARCHIVE_SHA256", dockerfile)
        self.assertIn("sha256:8a396f03c98f0c476275499b1ff663d7208286f37ded0c0446e7c0495c79a285", dockerfile)

    def test_directly_executed_scripts_are_executable_in_git(self):
        required = {
            "pterodactyl-entrypoint.sh",
            "scripts/FEXBash",
            "scripts/palmodctl",
            "scripts/ptero_manager.py",
            "scripts/validate-shell.sh",
            "tests/fixtures/fake_fex.sh",
            "tests/test_entrypoint.sh",
            "tests/test_fex_wrapper.sh",
        }
        output = subprocess.run(
            ["git", "ls-files", "--stage", "--", *sorted(required)],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        modes = {line.split(maxsplit=3)[3]: line.split(maxsplit=1)[0] for line in output.splitlines()}
        self.assertEqual(required, set(modes))
        self.assertTrue(all(modes[path] == "100755" for path in required), modes)

    def test_all_mod_flags_are_safe_string_booleans(self):
        egg = json.loads((PROJECT_ROOT / "egg-palworld-arm64.json").read_text(encoding="utf-8"))
        variables = {item["env_variable"]: item for item in egg["variables"]}
        expected = {
            "MODS_ENABLED": "false",
            "MODS_SAFE_MODE": "false",
            "MODS_SERVER_SIDE_ONLY": "true",
            "MODS_BACKUP_ON_CHANGE": "true",
            "MODS_FAIL_ON_ERROR": "true",
            "MODS_DEBUG": "false",
            "MODS_STRICT_VERSION_CHECK": "false",
            "MODS_UE4SS_TEST_MODE": "false",
            "ENABLE_PATCH_MODS": "true",
            "ENABLE_BLUEPRINT_MODS": "false",
            "ENABLE_LUA_MODS": "false",
            "ENABLE_CPP_MODS": "false",
        }
        for name, default in expected.items():
            self.assertIn(name, variables)
            self.assertEqual(variables[name]["default_value"], default)
            self.assertEqual(variables[name]["rules"], "required|string|in:true,false")


if __name__ == "__main__":
    unittest.main()
