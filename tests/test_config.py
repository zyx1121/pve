#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer", "rich"]
# ///
"""Private profile validation, precedence, and failure before any SSH call."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
from _config import load_config, config_path


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "config.json"
        self.profile = json.loads((ROOT / "examples/pve.config.example.json").read_text())
        self.path.write_text(json.dumps(self.profile))
        self.env = {"PVE_CONFIG_PATH": str(self.path)}

    def test_precedence(self):
        self.assertEqual(load_config(self.env)["host"], self.profile["host"])
        self.env["UTILS_PVE_HOST"] = "legacy-host"
        self.assertEqual(load_config(self.env)["host"], "legacy-host")
        self.env["PVE_HOST"] = "new-host"
        self.assertEqual(load_config(self.env)["host"], "new-host")
        self.env["PVE_TEMPLATE"] = "9001"
        self.assertEqual(load_config(self.env)["template"], 9001)

    def test_xdg_path(self):
        self.assertEqual(config_path({"XDG_CONFIG_HOME": self.tmp.name}), Path(self.tmp.name) / "pve/config.json")

    def test_invalid_profiles(self):
        for key, value in [("host", "-oProxyCommand=bad"), ("gateway", "host\ncommand"),
                           ("gateway_ip", "::1"), ("gateway_dns", "relative/path"),
                           ("gateway_env", "/srv/../env"), ("template", 9000.5),
                           ("template", True), ("template", 1), ("version", 2),
                           ("bridge", "bridge;command"), ("unknown", "value"),
                           ("debian_mirror", "https://user:password@example.test")]:
            with self.subTest(key=key, value=value):
                self.path.write_text(json.dumps({**self.profile, key: value}))
                with self.assertRaises(ValueError):
                    load_config(self.env)

    def test_missing_profile_fails_before_ssh(self):
        self.path.unlink()
        marker = Path(self.tmp.name) / "ssh-called"
        ssh = Path(self.tmp.name) / "ssh"
        ssh.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexit 1\n')
        ssh.chmod(0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PVE_", "UTILS_PVE_"))}
        env.update(self.env, PATH=self.tmp.name + os.pathsep + os.environ["PATH"])
        result = subprocess.run([sys.executable, str(ROOT / "scripts/pve.py"), "list"], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["error"]["message"], "Invalid PVE configuration")
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
