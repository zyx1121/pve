#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer", "rich"]
# ///
"""Offline check of the per-node rules in scripts/pve.py: node selection, VMID and IP
derivation from vmid_base, SSH alias advice, and refusing forwards on a node without them.

    ./tests/test_nodes.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "pve.py"

for key in list(os.environ):
    if key.startswith(("PVE_", "UTILS_PVE_")):
        del os.environ[key]
os.environ["PVE_CONFIG_PATH"] = str(ROOT / "examples/pve.config.example.json")

failures: list[str] = []
total = 0


def check(name: str, condition: bool) -> None:
    global total
    total += 1
    print(f"[{'ok' if condition else 'FAIL'}] {name}")
    if not condition:
        failures.append(name)


def load(argv: list[str]):
    """Import pve.py as if run with argv, so the leading --node is honoured."""
    saved = sys.argv[:]
    sys.argv = [str(SCRIPT), *argv]
    try:
        spec = importlib.util.spec_from_file_location("pve_" + "_".join(argv).replace("-", ""), SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module, sys.argv[:]
    finally:
        sys.argv = saved


default, rest = load(["list"])
check("default node comes from default_node", default.NODE == "pve" and default.VMID_BASE == 0)
check("argv without --node is untouched", rest[1:] == ["list"])
check("default node: first VM is 100", default._next_vmid({100, 101}, 100) == 102)
check("default node: IP octet is the VMID", default._derive_ip(117, 100) == "192.0.2.117")

second, rest = load(["--node", "pve2", "clone", "web"])
check("--node selects the node", second.NODE == "pve2" and second.PVE_HOST == "pve2")
check("--node is removed before typer parses", rest[1:] == ["clone", "web"])
check("vmid_base shifts the first VM", second._next_vmid(set(), 100) == 1100)
check("vmid_base shifts the first container", second._next_vmid({1200}, 200) == 1201)
check("IP octet is VMID minus vmid_base", second._derive_ip(1117, 100) == "198.51.100.117")
try:
    second._derive_ip(1300, 100)
    refused = False
except SystemExit:
    refused = True
check("an octet outside 1-254 is refused", refused)
check("no forwards on a node with ssh_forward false", second.SSH_FORWARD is False)
alias = second._ssh_alias("web", "198.51.100.117", None, "user")
check("routed alias points at the guest IP", "HostName 198.51.100.117" in alias["ssh_alias_block"] and "User user" in alias["ssh_alias_block"])
forwarded = default._ssh_alias("web", "192.0.2.117", 50117, "user")
check("forwarded alias keeps the port block", forwarded["ssh_alias_block"] == "Host web\n  Port 50117")

_, rest = load(["clone", "--node", "pve2"])
check("a later --node is left to typer", rest[1:] == ["clone", "--node", "pve2"])

with tempfile.TemporaryDirectory() as tmp:
    marker = Path(tmp) / "ssh-called"
    ssh = Path(tmp) / "ssh"
    ssh.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexit 1\n')
    ssh.chmod(0o755)
    env = {**os.environ, "PATH": tmp + os.pathsep + os.environ["PATH"]}

    def run(*argv: str) -> dict:
        result = subprocess.run([sys.executable, str(SCRIPT), *argv], env=env, capture_output=True, text=True)
        return json.loads(result.stdout or "{}")

    out = run("--node", "pve2", "forward", "1:198.51.100.5:22")
    check("forward add is refused on a node without forwards",
          "does not take port forwards" in out.get("error", {}).get("message", "") and not marker.exists())
    out = run("--node", "missing", "list")
    check("an unknown node fails as a configuration error",
          out.get("error", {}).get("message") == "Invalid PVE configuration" and not marker.exists())

print(f"\n{total - len(failures)}/{total} passed")
sys.exit(1 if failures else 0)
