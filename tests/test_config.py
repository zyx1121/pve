#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer", "rich"]
# ///
"""Private profile validation, node selection, precedence, and failure before any SSH call."""
import copy
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
        self.write(self.profile)
        self.env = {"PVE_CONFIG_PATH": str(self.path)}

    def write(self, profile):
        self.path.write_text(json.dumps(profile))

    def test_default_node(self):
        config = load_config(self.env)
        self.assertEqual(config["node"], "pve")
        self.assertEqual(config["host"], "pve")
        self.assertEqual(config["vmid_base"], 0)
        self.assertTrue(config["ssh_forward"])
        self.assertEqual(config["nodes"], ["pve", "pve2"])
        self.assertEqual(config["gateway"], self.profile["gateway"])

    def test_select_node(self):
        config = load_config(self.env, node="pve2")
        self.assertEqual((config["host"], config["template"], config["vmid_base"], config["ssh_forward"]),
                         ("pve2", 1900, 1000, False))
        self.assertEqual(config["gateway_dns"], self.profile["gateway_dns"])
        self.env["PVE_NODE"] = "pve2"
        self.assertEqual(load_config(self.env)["node"], "pve2")
        self.assertEqual(load_config(self.env, node="pve")["node"], "pve")

    def test_node_defaults(self):
        profile = copy.deepcopy(self.profile)
        del profile["nodes"]["pve"]["vmid_base"], profile["nodes"]["pve"]["ssh_forward"]
        self.write(profile)
        config = load_config(self.env)
        self.assertEqual((config["vmid_base"], config["ssh_forward"]), (0, True))

    def test_precedence(self):
        self.env["UTILS_PVE_HOST"] = "legacy-host"
        self.assertEqual(load_config(self.env)["host"], "legacy-host")
        self.env["PVE_HOST"] = "new-host"
        self.assertEqual(load_config(self.env)["host"], "new-host")
        self.env["PVE_TEMPLATE"] = "9001"
        self.assertEqual(load_config(self.env)["template"], 9001)
        self.env["PVE_SSH_FORWARD"] = "false"
        self.assertFalse(load_config(self.env)["ssh_forward"])

    def test_xdg_path(self):
        self.assertEqual(config_path({"XDG_CONFIG_HOME": self.tmp.name}), Path(self.tmp.name) / "pve/config.json")

    def test_invalid_profiles(self):
        node_cases = [("host", "-oProxyCommand=bad"), ("gateway_ip", "::1"), ("template", 9000.5),
                      ("template", True), ("template", 1), ("bridge", "bridge;command"),
                      ("vmid_base", 1500), ("vmid_base", -1000), ("ssh_forward", "maybe"),
                      ("unknown", "value"), ("gateway", "gateway"),
                      ("debian_mirror", "https://user:password@example.test")]
        for key, value in node_cases:
            with self.subTest(node_key=key, value=value):
                profile = copy.deepcopy(self.profile)
                profile["nodes"]["pve"][key] = value
                self.write(profile)
                with self.assertRaises(ValueError):
                    load_config(self.env)
        top_cases = [("gateway", "host\ncommand"), ("gateway_dns", "relative/path"),
                     ("gateway_env", "/srv/../env"), ("version", 1), ("host", "pve"),
                     ("default_node", "missing"), ("nodes", {}), ("nodes", {"bad name": {}})]
        for key, value in top_cases:
            with self.subTest(key=key, value=value):
                self.write({**self.profile, key: value})
                with self.assertRaises(ValueError):
                    load_config(self.env)

    def test_unknown_node(self):
        with self.assertRaisesRegex(ValueError, "pve, pve2"):
            load_config(self.env, node="missing")

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
