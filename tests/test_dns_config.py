#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer", "rich"]
# ///
"""Offline self-check for how scripts/pve.py reads the gateway's dnsmasq config.

The DNS tools edit one hosts file; dnsmasq only answers from the files named by
addn-hosts. These checks pin the parser that decides whether an edit can take
effect, so a config pointing elsewhere fails loudly instead of reporting success.

    ./tests/test_dns_config.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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


HOSTS = "/home/user/gateway/dns/hosts"
parse = pve._parse_dnsmasq_config

check("addn-hosts naming the managed file is served",
      parse(f"listen-address=10.0.0.2\naddn-hosts={HOSTS}\n", HOSTS) == (True, "10.0.0.2"))
check("addn-hosts naming its directory is served",
      parse("addn-hosts=/home/user/gateway/dns/\n", HOSTS)[0])
check("addn-hosts naming another file is not served",
      parse("addn-hosts=/etc/dnsmasq.hosts\nlisten-address=10.0.0.2\n", HOSTS) == (False, "10.0.0.2"))
check("any of several addn-hosts lines can serve it",
      parse(f"addn-hosts=/etc/dnsmasq.hosts\naddn-hosts={HOSTS}\n", HOSTS)[0])
check("no config lines means not served and no address",
      parse("", HOSTS) == (False, None))
check("the first of several listen addresses is used",
      parse("listen-address=10.0.0.2,127.0.0.1\n", HOSTS)[1] == "10.0.0.2")
check("a prefix of the path does not count",
      not parse("addn-hosts=/home/user/gateway\n", HOSTS)[0])

print(f"\n{total - len(failures)}/{total} passed")
sys.exit(1 if failures else 0)
