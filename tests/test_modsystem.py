from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch as mock_patch
from dataclasses import replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modsystem.backup import BackupManager  # noqa: E402
from modsystem.config import ModConfig  # noqa: E402
from modsystem.deployer import Deployer, MANAGED_BLOCK_START  # noqa: E402
from modsystem.state import read_json  # noqa: E402
from modsystem.validators import inspect_elf_shared_object, validate  # noqa: E402


def write_manifest(path: Path, **values) -> None:
    path.write_text(json.dumps(values), encoding="utf-8")


def fake_elf_x86_64_shared_object() -> bytes:
    header = bytearray(64)
    header[:4] = b"\x7fELF"
    header[4] = 2
    header[5] = 1
    header[6] = 1
    header[16:20] = struct.pack("<HH", 3, 62)
    return bytes(header)


class ModSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = ModConfig.for_test(
            self.root,
            enabled=True,
            server_side_only=False,
            backup_on_change=True,
        )
        self.config.initialize_directories()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def mod_dir(self, category: str, name: str) -> Path:
        path = self.config.mods_root / category / name
        path.mkdir(parents=True)
        return path

    def create_fake_ue4ss_bundle(self, config: ModConfig) -> Path:
        bundle = config.ue4ss_bundle_root
        bundle.mkdir(parents=True)
        (bundle / "libUE4SS.so").write_bytes(fake_elf_x86_64_shared_object())
        (bundle / "UE4SS-settings.ini").write_text("[General]\n", encoding="utf-8")
        (bundle / "MemberVariableLayout.ini").write_text("[UObject]\n", encoding="utf-8")
        (bundle / "version.json").write_text(
            json.dumps(
                {
                    "ue4ss_linux": "test",
                    "backend": "linux-fex",
                    "last_tested_palworld_build_id": "unknown",
                }
            ),
            encoding="utf-8",
        )
        return bundle

    def add_fake_blueprint_loader(self, bundle: Path) -> None:
        shared = bundle / "Mods" / "shared"
        shared.mkdir(parents=True)
        (shared / "UEHelpers.lua").write_text("return {}", encoding="utf-8")
        for builtin in ("BPML_GenericFunctions", "BPModLoaderMod"):
            scripts = bundle / "Mods" / builtin / "Scripts"
            scripts.mkdir(parents=True)
            (scripts / "main.lua").write_text("print('builtin')", encoding="utf-8")
        (bundle / "Mods" / "BPModLoaderMod" / "load_order.txt").write_text(
            "old-order\n", encoding="utf-8"
        )

    def test_patch_single_pak_is_supported(self):
        mod = self.mod_dir("patch", "SimplePatch")
        (mod / "Simple.pak").write_bytes(b"pak")
        result = validate(self.config)
        self.assertFalse(result.errors, result.errors)
        self.assertEqual(result.mods[0].status, "SUPPORTED")

    def test_incomplete_pak_trio_is_rejected(self):
        mod = self.mod_dir("patch", "BrokenPatch")
        (mod / "Broken.pak").write_bytes(b"pak")
        (mod / "Broken.utoc").write_bytes(b"utoc")
        result = validate(self.config)
        self.assertTrue(any("incomplete pak trio" in error for error in result.errors))

    def test_lua_requires_case_sensitive_main(self):
        config = replace(self.config, enable_lua=True)
        mod = self.mod_dir("lua", "LuaMod")
        scripts = mod / "Scripts"
        scripts.mkdir()
        (scripts / "main.lua").write_text("error('must never execute')", encoding="utf-8")
        result = validate(config)
        self.assertTrue(any("case-sensitive scripts/main.lua" in error for error in result.errors))

    def test_windows_dll_is_rejected_with_clear_backend_message(self):
        config = replace(self.config, enable_cpp=True)
        mod = self.mod_dir("cpp", "WindowsNative")
        (mod / "main.dll").write_bytes(b"MZ" + bytes(62))
        result = validate(config)
        joined = " | ".join(result.errors)
        self.assertIn("Windows DLL detected", joined)
        self.assertIn("Linux x86_64 under FEX", joined)

    def test_renamed_pe_binary_is_not_accepted_as_so(self):
        path = self.root / "fake.so"
        path.write_bytes(b"MZ" + bytes(62))
        valid, reason = inspect_elf_shared_object(path)
        self.assertFalse(valid)
        self.assertIn("Windows DLL detected", reason)

    def test_linux_x86_64_elf_shared_object_is_accepted(self):
        path = self.root / "main.so"
        path.write_bytes(fake_elf_x86_64_shared_object())
        valid, reason = inspect_elf_shared_object(path)
        self.assertTrue(valid, reason)

    def test_server_side_strict_rejects_client_required(self):
        config = replace(self.config, server_side_only=True)
        mod = self.mod_dir("patch", "ClientMod")
        (mod / "Client.pak").write_bytes(b"pak")
        write_manifest(
            mod / "mod.json",
            id="client-mod",
            type="patch",
            client_required=True,
            server_side=False,
        )
        result = validate(config)
        self.assertTrue(any("client_required=true" in error for error in result.errors))

    def test_load_order_and_hash_are_deterministic(self):
        later = self.mod_dir("patch", "Later")
        (later / "Later.pak").write_bytes(b"later")
        write_manifest(later / "mod.json", id="later", type="patch", priority=100)
        first = self.mod_dir("patch", "First")
        (first / "First.pak").write_bytes(b"first")
        write_manifest(first / "mod.json", id="first", type="patch", priority=10)
        one = validate(self.config)
        two = validate(self.config)
        self.assertEqual([mod.id for mod in one.mods], ["first", "later"])
        self.assertEqual(one.inventory_hash, two.inventory_hash)

    def test_patch_deploy_is_idempotent_and_safe_mode_preserves_source(self):
        mod = self.mod_dir("patch", "Patch")
        (mod / "Patch.pak").write_bytes(b"pak")
        first = Deployer(self.config).deploy()
        self.assertEqual(first["status"], "deployed")
        deployed = list((self.root / "Pal" / "Content" / "Paks" / "~mods").glob("*.pak"))
        self.assertEqual(len(deployed), 1)
        backup_count = len(list(self.config.backup_root.iterdir()))

        second = Deployer(self.config).deploy()
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(len(list(self.config.backup_root.iterdir())), backup_count)

        safe = replace(self.config, safe_mode=True)
        safe_result = Deployer(safe).deploy()
        self.assertEqual(safe_result["status"], "safe-mode")
        self.assertTrue((mod / "Patch.pak").is_file())
        self.assertFalse(deployed[0].exists())

    def test_invalid_mod_is_logically_quarantined(self):
        mod = self.mod_dir("patch", "Broken")
        (mod / "Broken.ucas").write_bytes(b"ucas")
        with self.assertRaises(ValueError):
            Deployer(self.config).deploy()
        quarantine = read_json(self.config.quarantine_path, {})
        self.assertIn("broken", quarantine)

    def test_state_write_failure_rolls_back_deployed_files(self):
        mod = self.mod_dir("patch", "Atomic")
        (mod / "Atomic.pak").write_bytes(b"pak")
        with mock_patch("modsystem.deployer.atomic_write_json", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                Deployer(self.config).deploy()
        target_root = self.root / "Pal" / "Content" / "Paks" / "~mods"
        self.assertFalse(any(target_root.glob("*.pak")) if target_root.exists() else False)
        self.assertFalse(self.config.inventory_path.exists())

    def test_ue4ss_mods_txt_preserves_manual_entries_and_clean_removes_managed_block(self):
        config = replace(self.config, enable_lua=True)
        self.create_fake_ue4ss_bundle(config)
        mod = self.mod_dir("lua", "Hello")
        (mod / "scripts").mkdir()
        (mod / "scripts" / "main.lua").write_text("print('hello')", encoding="utf-8")
        write_manifest(mod / "mod.json", id="hello", type="lua", server_side=True)
        mods_txt = config.ue4ss_mods_root / "mods.txt"
        mods_txt.parent.mkdir(parents=True)
        mods_txt.write_text("ManualMod : 1\n", encoding="utf-8")

        deployed = Deployer(config).deploy()
        self.assertEqual(deployed["status"], "deployed")
        content = mods_txt.read_text(encoding="utf-8")
        self.assertIn("ManualMod : 1", content)
        self.assertIn("hello : 1", content)
        self.assertIn(MANAGED_BLOCK_START, content)
        self.assertTrue((config.ue4ss_deploy_root / "libUE4SS.so").is_file())
        self.assertTrue((config.ue4ss_mods_root / "hello" / "Scripts" / "main.lua").is_file())

        Deployer(replace(config, safe_mode=True)).deploy()
        cleaned = mods_txt.read_text(encoding="utf-8")
        self.assertIn("ManualMod : 1", cleaned)
        self.assertNotIn(MANAGED_BLOCK_START, cleaned)
        self.assertFalse((config.ue4ss_deploy_root / "libUE4SS.so").exists())

    def test_rollback_restores_mod_source_but_not_saves_without_explicit_flag(self):
        mod = self.mod_dir("patch", "RollbackPatch")
        pak = mod / "Rollback.pak"
        pak.write_bytes(b"before")
        save = self.root / "Pal" / "Saved" / "SaveGames" / "world.sav"
        save.parent.mkdir(parents=True)
        save.write_bytes(b"save-before")
        backup = BackupManager(self.config).create("test")

        pak.write_bytes(b"after")
        save.write_bytes(b"save-after")
        BackupManager(self.config).rollback(backup.name, restore_saves=False)
        self.assertEqual(pak.read_bytes(), b"before")
        self.assertEqual(save.read_bytes(), b"save-after")

    def test_blueprint_deploys_loader_and_deterministic_load_order(self):
        config = replace(self.config, enable_blueprint=True)
        bundle = self.create_fake_ue4ss_bundle(config)
        self.add_fake_blueprint_loader(bundle)
        mod = self.mod_dir("blueprint", "Logic")
        (mod / "LogicMod.pak").write_bytes(b"pak")
        write_manifest(mod / "mod.json", id="logic", type="blueprint", server_side=True)

        deployment = Deployer(config).deploy()
        self.assertEqual(deployment["status"], "deployed")
        self.assertTrue(
            (
                self.root
                / "Pal"
                / "Content"
                / "Paks"
                / "LogicMods"
                / "logic"
                / "LogicMod.pak"
            ).is_file()
        )
        self.assertTrue(
            (config.ue4ss_mods_root / "BPModLoaderMod" / "Scripts" / "main.lua").is_file()
        )
        load_order = (
            config.ue4ss_mods_root / "BPModLoaderMod" / "load_order.txt"
        ).read_text(encoding="utf-8")
        self.assertEqual(load_order, "LogicMod\n")
        mods_txt = (config.ue4ss_mods_root / "mods.txt").read_text(encoding="utf-8")
        self.assertIn("BPML_GenericFunctions : 1", mods_txt)
        self.assertIn("BPModLoaderMod : 1", mods_txt)

    def test_cpp_deploys_only_to_linux_libs_directory(self):
        config = replace(self.config, enable_cpp=True)
        self.create_fake_ue4ss_bundle(config)
        mod = self.mod_dir("cpp", "Native")
        (mod / "main.so").write_bytes(fake_elf_x86_64_shared_object())
        write_manifest(
            mod / "mod.json",
            id="native",
            type="cpp",
            platform="linux-x86_64",
            server_side=True,
        )

        deployment = Deployer(config).deploy()
        self.assertEqual(deployment["status"], "deployed")
        self.assertTrue((config.ue4ss_mods_root / "native" / "libs" / "main.so").is_file())
        self.assertFalse((config.ue4ss_mods_root / "native" / "dlls").exists())

    def test_all_four_structural_types_can_share_one_transaction(self):
        config = replace(
            self.config,
            enable_blueprint=True,
            enable_lua=True,
            enable_cpp=True,
        )
        bundle = self.create_fake_ue4ss_bundle(config)
        self.add_fake_blueprint_loader(bundle)

        patch = self.mod_dir("patch", "Patch")
        (patch / "Patch.pak").write_bytes(b"patch")
        blueprint = self.mod_dir("blueprint", "Blueprint")
        (blueprint / "Blueprint.pak").write_bytes(b"blueprint")
        lua = self.mod_dir("lua", "Lua")
        (lua / "scripts").mkdir()
        (lua / "scripts" / "main.lua").write_text("print('lua')", encoding="utf-8")
        native = self.mod_dir("cpp", "Native")
        (native / "main.so").write_bytes(fake_elf_x86_64_shared_object())
        for path, values in (
            (patch, {"id": "patch", "type": "patch"}),
            (blueprint, {"id": "blueprint", "type": "blueprint"}),
            (lua, {"id": "lua", "type": "lua"}),
            (
                native,
                {"id": "native", "type": "cpp", "platform": "linux-x86_64"},
            ),
        ):
            write_manifest(path / "mod.json", server_side=True, **values)

        deployment = Deployer(config).deploy()
        self.assertEqual(deployment["status"], "deployed")
        inventory = read_json(config.inventory_path, {})
        self.assertEqual(len(inventory["mods"]), 4)
        self.assertTrue(inventory["ue4ss_required"])

    def test_ue4ss_no_mod_test_mode_deploys_only_loader_core(self):
        config = replace(self.config, ue4ss_test_mode=True)
        self.create_fake_ue4ss_bundle(config)

        deployment = Deployer(config).deploy()
        self.assertEqual(deployment["status"], "deployed")
        self.assertTrue(deployment["ue4ss_required"])
        self.assertTrue((config.ue4ss_deploy_root / "libUE4SS.so").is_file())
        self.assertFalse((config.ue4ss_mods_root / "mods.txt").exists())
        inventory = read_json(config.inventory_path, {})
        self.assertEqual(inventory["mods"], [])
        self.assertTrue(inventory["ue4ss_required"])


if __name__ == "__main__":
    unittest.main()
