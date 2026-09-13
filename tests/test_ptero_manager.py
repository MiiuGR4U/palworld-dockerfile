import os
import sys
import unittest
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import ptero_manager
import log_filter

class PteroManagerTests(unittest.TestCase):
    def test_is_truthy(self):
        for val in ("true", "TRUE", "True", "1", "yes", "YES", "on", "ON"):
            self.assertTrue(ptero_manager.is_truthy(val), f"Expected truthy for {val}")
        for val in ("false", "FALSE", "0", "no", "NO", "off", None, ""):
            self.assertFalse(ptero_manager.is_truthy(val), f"Expected falsy for {val}")

    def test_update_enabled_auto_update(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = os.environ.copy()
            try:
                ptero_manager.SERVER_ROOT = tmpdir
                os.environ["UPDATE_ON_START"] = "false"
                os.environ["AUTO_UPDATE"] = "1"
                self.assertTrue(ptero_manager.check_update_enabled())
            finally:
                os.environ.clear()
                os.environ.update(old_env)

    def test_update_enabled_force_marker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = os.environ.copy()
            try:
                ptero_manager.SERVER_ROOT = tmpdir
                os.environ["UPDATE_ON_START"] = "false"
                os.environ.pop("AUTO_UPDATE", None)
                os.environ.pop("FORCE_UPDATE", None)

                marker_dir = Path(tmpdir) / "tmp"
                marker_dir.mkdir(parents=True, exist_ok=True)
                marker_file = marker_dir / ".force_update_next_boot"
                marker_file.write_text("1")

                self.assertTrue(ptero_manager.check_update_enabled())
                self.assertFalse(marker_file.exists(), "Marker file should have been removed")
            finally:
                os.environ.clear()
                os.environ.update(old_env)

    def test_suppress_patterns_cover_api_and_monitoring_warnings(self):
        lines = [
            "[WARNING] 2026-09-13T18:17:37 API returned None (attempt 1)",
            "[WARNING] 2026-09-13T18:17:47 Monitoring cycle took 1001ms - performance issue detected",
            "* Connected to o1291919.ingest.us.sentry.io (34.160.81.0) port 443 (#0)",
            "> POST /api/6513339/envelope/ HTTP/2",
            "< HTTP/2 200",
            "{}* Connection #0 to host o1291919.ingest.us.sentry.io left intact",
            "[S_API FAIL] Tried to access Steam interface SteamUser021 before SteamAPI_Init succeeded."
        ]
        for line in lines:
            matched = any(p.search(line) for p in log_filter.SUPPRESS_PATTERNS)
            self.assertTrue(matched, f"Expected line to be suppressed: {line}")
            formatted = log_filter.format_line(line)
            self.assertEqual(formatted, "", f"Expected format_line to return empty string for: {line}")

    def test_configure_palworld_ini(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_ini = Path(tmpdir) / "PalWorldSettings.ini"
            test_ini.write_text("[/Script/Pal.PalGameWorldSettings]\nOptionSettings=(Difficulty=None,ServerName=\"TestServer\",PublicPort=8211,bUseAuth=True)\n", encoding="utf-8")
            
            old_env = os.environ.copy()
            try:
                os.environ["SERVER_PORT"] = "25565"
                os.environ["USE_AUTH"] = "false"
                modified = ptero_manager.configure_palworld_ini(str(test_ini))
                self.assertTrue(modified)
                
                content = test_ini.read_text(encoding="utf-8")
                self.assertIn("bIsUseRestAPI=True", content)
                self.assertIn("RESTAPIPort=8212", content)
                self.assertIn("bUseAuth=False", content)
                self.assertIn("PublicPort=25565", content)
            finally:
                os.environ.clear()
                os.environ.update(old_env)

    def test_version_and_readiness_format(self):
        v_line = "Game version is 1.0.4.102642"
        f_v = log_filter.format_line(v_line)
        self.assertIn("1.0.4.102642", f_v)
        self.assertIn("[VERSÃO]", f_v)

        r_line = "[PALWORLD] Servidor pronto para conexões na porta 25565! Versão: 1.0.4.102642"
        f_r = log_filter.format_line(r_line)
        self.assertIn("[PRONTO]", f_r)
        self.assertIn("25565", f_r)

    def test_no_duplicate_modifications_in_configure_ini(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_ini = Path(tmpdir) / "PalWorldSettings.ini"
            test_ini.write_text("[/Script/Pal.PalGameWorldSettings]\nOptionSettings=(Difficulty=None,bIsUseRestAPI=True,RESTAPIPort=8212,bUseAuth=False,PublicPort=25565)\n", encoding="utf-8")
            
            old_env = os.environ.copy()
            try:
                os.environ["SERVER_PORT"] = "25565"
                os.environ["USE_AUTH"] = "false"
                # First run on already-compliant file should NOT modify
                modified = ptero_manager.configure_palworld_ini(str(test_ini), log_action=False)
                self.assertFalse(modified, "Should not modify file if settings are already compliant")
            finally:
                os.environ.clear()
                os.environ.update(old_env)

    def test_handle_post_config_generation_preserves_custom_settings_when_not_updated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_server_root = ptero_manager.SERVER_ROOT
            try:
                ptero_manager.SERVER_ROOT = tmpdir
                ptero_manager.UPDATE_ACTUALLY_DOWNLOADED = False

                saved_dir = Path(tmpdir) / "Pal" / "Saved" / "Config" / "LinuxServer"
                saved_dir.mkdir(parents=True, exist_ok=True)
                tmp_dir = Path(tmpdir) / "tmp"
                tmp_dir.mkdir(parents=True, exist_ok=True)

                preboot_ini = tmp_dir / "PalWorldSettings.ini.preboot"
                preboot_ini.write_text("[/Script/Pal.PalGameWorldSettings]\nOptionSettings=(ExpRate=5.000000,PalSpawnNumRate=3.000000,bIsUseRestAPI=True,RESTAPIPort=8212,bUseAuth=False,PublicPort=25565)\n", encoding="utf-8")

                active_ini = saved_dir / "PalWorldSettings.ini"
                # Upstream manager reset it to defaults (ExpRate=1.0)
                active_ini.write_text("[/Script/Pal.PalGameWorldSettings]\nOptionSettings=(ExpRate=1.000000,PalSpawnNumRate=1.000000)\n", encoding="utf-8")

                ptero_manager.handle_post_config_generation()

                content = active_ini.read_text(encoding="utf-8")
                self.assertIn("ExpRate=5.000000", content, "Custom ExpRate must be restored")
                self.assertIn("PalSpawnNumRate=3.000000", content, "Custom PalSpawnNumRate must be restored")
            finally:
                ptero_manager.SERVER_ROOT = saved_server_root

    def test_traceback_and_asyncio_shutdown_suppressed(self):
        user_traceback_lines = [
            'File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run',
            '^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^',
            '^^^^^^^^^^^^^^^',
            'await asyncio.sleep(60)',
            'File "/usr/lib/python3.12/asyncio/tasks.py", line 665, in sleep',
            '^^^^^^^^^^^^',
            'During handling of the above exception, another exception occurred:',
            'File "<frozen runpy>", line 88, in _run_code',
            'exit_code = asyncio.run(main())',
            '^^^^^^^^^^^^^^^^^^^',
            'File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run',
            'return runner.run(main)',
            '^^^^^^^^^^^^^^^^',
            'File "/usr/lib/python3.12/asyncio/runners.py", line 123, in run',
            'KeyboardInterrupt',
            'asyncio.exceptions.CancelledError',
            'Traceback (most recent call last):',
        ]
        for line in user_traceback_lines:
            self.assertTrue(
                ptero_manager.is_traceback_line(line),
                f"is_traceback_line must identify: {line}"
            )
            self.assertEqual(
                log_filter.format_line(line),
                "",
                f"format_line must suppress: {line}"
            )

    def test_shutdown_messages_formatted_in_portuguese(self):
        stop_line = "[INFO] 2026-09-13T19:09:30 Server stopped successfully"
        formatted_stop = log_filter.format_line(stop_line)
        self.assertIn("[FINALIZADO]", formatted_stop)
        self.assertIn("Servidor Palworld finalizado com sucesso", formatted_stop)

        backup_line = "[INFO] Backup cleanup"
        formatted_backup = log_filter.format_line(backup_line)
        self.assertIn("[BACKUP]", formatted_backup)
        self.assertIn("Limpeza de backups temporários concluída", formatted_backup)

    def test_stream_output_suppresses_tracebacks_cleanly(self):
        import io
        from unittest.mock import MagicMock

        lines = [
            "[INFO] 2026-09-13T19:09:30 Server stopped successfully\n",
            "[INFO] Backup cleanup\n",
            'File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run\n',
            '^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n',
            'await asyncio.sleep(60)\n',
            'File "/usr/lib/python3.12/asyncio/tasks.py", line 665, in sleep\n',
            '^^^^^^^^^^^^\n',
            'During handling of the above exception, another exception occurred:\n',
            'File "<frozen runpy>", line 88, in _run_code\n',
            'exit_code = asyncio.run(main())\n',
            '^^^^^^^^^^^^^^^^^^^\n',
            'File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run\n',
            'return runner.run(main)\n',
            '^^^^^^^^^^^^^^^^\n',
            'File "/usr/lib/python3.12/asyncio/runners.py", line 123, in run\n',
            'KeyboardInterrupt\n',
        ]

        wrapper = ptero_manager.ManagerWrapper()
        fake_process = MagicMock()
        fake_process.stdout = lines
        wrapper.process = fake_process

        captured = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = captured
            wrapper._stream_output()
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("FINALIZADO", output)
        self.assertIn("BACKUP", output)
        self.assertNotIn("runners.py", output)
        self.assertNotIn("^^^^", output)
        self.assertNotIn("asyncio.sleep", output)
        self.assertNotIn("KeyboardInterrupt", output)
        self.assertNotIn("During handling", output)
        self.assertTrue(wrapper.shutdown_requested)

if __name__ == "__main__":
    unittest.main()
