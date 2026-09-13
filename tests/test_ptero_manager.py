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

if __name__ == "__main__":
    unittest.main()
