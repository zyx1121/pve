#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer", "rich"]
# ///
"""Offline self-check for scripts/pve.py's rules.v4 persistence.

Runs with no SSH and no PVE host: loads pve.py as a module, rewrites the
persist script's target to a temp rules.v4, and runs it under a local `sh`
with a fake `iptables-save` on PATH. Checks that the SDN's own SNAT is
dropped (the vnet post-up re-adds it on boot) while every manual nat rule,
including the tailnet subnet-router SNAT, survives, and that the *filter
block is left untouched. Needs a POSIX sh, awk and mktemp.

    ./tests/test_pve_persist.py
"""
from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Isolate this regression test from the operator's private profile and env.
for key in list(os.environ):
    if key.startswith(("PVE_", "UTILS_PVE_")):
        del os.environ[key]
os.environ["PVE_CONFIG_PATH"] = str(ROOT / "examples/pve.config.example.json")

spec = importlib.util.spec_from_file_location("pve", ROOT / "scripts" / "pve.py")
pve = importlib.util.module_from_spec(spec)
sys.modules["pve"] = pve
spec.loader.exec_module(pve)  # type: ignore[union-attr]

failures: list[str] = []
total = 0


def check(name: str, condition: bool) -> None:
    global total
    total += 1
    print(f"[{'ok' if condition else 'FAIL'}] {name}")
    if not condition:
        failures.append(name)


FILTER_BLOCK = """*filter
:INPUT ACCEPT [0:0]
-A INPUT -i vmbr0 -p tcp -m tcp --dport 8006 -j DROP
COMMIT
"""

OLD_NAT_BLOCK = """*nat
:PREROUTING ACCEPT [0:0]
-A PREROUTING -p tcp -m tcp --dport 50999 -j DNAT --to-destination 192.0.2.99:22
COMMIT
"""

SDN_SNAT = "-A POSTROUTING -s 192.0.2.0/24 -o vmbr0 -j SNAT --to-source 203.0.113.1"
TAILNET_SNAT = "-A POSTROUTING -s 100.64.0.0/10 -o vmbr0 -j SNAT --to-source 203.0.113.1"
REFLECTION = "-A POSTROUTING -s 192.0.2.0/24 -d 192.0.2.200/32 -p tcp -m multiport --dports 80,443 -j MASQUERADE"
PORT_SNAT = "-A POSTROUTING -s 192.0.2.0/24 -o vmbr0 -p tcp -m tcp --dport 25 -j SNAT --to-source 203.0.113.1"
FORWARD = "-A PREROUTING -p tcp -m tcp --dport 50104 -j DNAT --to-destination 192.0.2.104:22"

LIVE_NAT = f"""*nat
:PREROUTING ACCEPT [0:0]
:POSTROUTING ACCEPT [0:0]
:ts-postrouting - [0:0]
{FORWARD}
-A POSTROUTING -j ts-postrouting
{SDN_SNAT}
{TAILNET_SNAT}
{REFLECTION}
{PORT_SNAT}
COMMIT
"""

check("VM subnet is derived from the gateway IP", pve._VM_SUBNET == "192.0.2.0/24")

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    rules = tmp_path / "rules.v4"
    rules.write_text(FILTER_BLOCK + OLD_NAT_BLOCK)
    fake = tmp_path / "iptables-save"
    fake.write_text(f"#!/bin/sh\ncat <<'EOF'\n{LIVE_NAT}EOF\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)

    script = pve._PERSIST_IPTABLES_SH.replace("/etc/iptables/rules.v4", str(rules))
    env = {**os.environ, "PATH": f"{tmp}{os.pathsep}{os.environ['PATH']}"}
    run = subprocess.run(["sh", "-c", script, "persist-iptables", pve._VM_SUBNET],
                         env=env, capture_output=True, text=True)
    check("persist script exits 0", run.returncode == 0)
    out = rules.read_text()
    lines = out.splitlines()

check("SDN SNAT is dropped", SDN_SNAT not in lines)
check("tailnet SNAT survives", TAILNET_SNAT in lines)
check("NAT reflection MASQUERADE survives", REFLECTION in lines)
check("a narrower manual SNAT on the VM subnet survives", PORT_SNAT in lines)
check("live forward is written", FORWARD in lines)
check("stale nat block is replaced", "--dport 50999" not in out)
check("*filter block is left untouched", out.startswith(FILTER_BLOCK))
check("exactly one *nat block", lines.count("*nat") == 1)

if failures:
    print(f"\n{len(failures)}/{total} check(s) failed: {failures}")
    sys.exit(1)
print(f"\nall {total} checks passed")
