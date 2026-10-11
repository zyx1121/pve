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
import subprocess
import sys
import tempfile
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

check("a managed= line resolves a symlinked hosts file",
      parse("addn-hosts=/real/dns/hosts\nmanaged=/real/dns/hosts\n", "/link/hosts")[0])

# Hostnames reach remote shell commands, so anything else is refused.
def refused(host: str) -> bool:
    try:
        pve._valid_dns_host(host)
    except SystemExit:
        return True
    return False

check("plain and dotted hostnames pass",
      not refused("sandbox") and not refused("spawner.internal") and not refused("a-1.b2.internal"))
for bad in ["x';id;'", "a b", "$(id)", "a;b", "-x", "a..b", "", "a" * 64,
            "sandbox.internal\n", "a\nb", "a\t"]:
    check(f"hostname {bad[:20]!r} is refused", refused(bad))
check("the field pattern is one shell word matching dots literally",
      pve._host_field_pattern("a.b") == "'[[:space:]]a[.]b([[:space:]]|$)'")

check("hosts-file records skip comments and blank lines",
      pve._parse_dns_records("# c\n\n10.0.0.1 a.internal\n  10.0.0.2   b  \n") ==
      [{"ip": "10.0.0.1", "host": "a.internal"}, {"ip": "10.0.0.2", "host": "b"}])

# dig output: ";;" lines are dig's own errors, not answers.
def answer(out: str):
    pve.ssh_run = lambda *a, **k: out
    return pve._dnsmasq_answer("x.internal", "10.0.0.2")

check("dig answers are returned", answer("10.0.0.5\n__end\n") == ["10.0.0.5"])
check("no answer is an empty list", answer("__end\n") == [])
check("a dig timeout means it could not ask",
      answer(";; communications error to 10.0.0.2#53: timed out\n__end\n") is None)
check("no dig on the gateway means it could not ask", answer("") is None)

# Removing a record must keep a symlinked hosts file a symlink (`mv` did not).
with tempfile.TemporaryDirectory() as d:
    real, link = Path(d, "hosts"), Path(d, "dnsmasq.hosts")
    real.write_text("# header\n10.0.0.1 keep.internal\n10.0.0.2 gone.internal\n")
    link.symlink_to(real)
    pve.GATEWAY_DNS_HOSTS = str(link)
    pve.ssh_run = lambda host, *args, **k: subprocess.run(
        list(args), capture_output=True, text=True, check=True).stdout
    removed = pve._remove_dns_record("gone.internal")
    check("remove reports the record as removed", removed)
    check("the symlink is still a symlink", link.is_symlink())
    check("the record is gone and the rest stays",
          real.read_text() == "# header\n10.0.0.1 keep.internal\n")
    check("removing an absent record changes nothing", not pve._remove_dns_record("gone.internal"))

print(f"\n{total - len(failures)}/{total} passed")
sys.exit(1 if failures else 0)
