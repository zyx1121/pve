"""Private environment profile shared by every PVE script operation."""
from __future__ import annotations
import ipaddress
import json
import os
from pathlib import Path

# The legacy env names are accepted while consumers migrate to the standalone plugin.
FIELDS = {
    "host": "HOST",
    "gateway": "GATEWAY",
    "template": "TEMPLATE",
    "gateway_ip": "GATEWAY_IP",
    "gateway_dns": "GATEWAY_DNS",
    "gateway_caddy": "GATEWAY_CADDY",
    "gateway_env": "GATEWAY_ENV",
    "caddy_reload": "CADDY_RELOAD",
    "bridge": "BRIDGE",
    "fw_group": "FW_GROUP",
    "ct_template": "CT_TEMPLATE",
    "debian_mirror": "DEBIAN_MIRROR",
}

def config_path(env=None):
    env = os.environ if env is None else env
    return Path(env.get("PVE_CONFIG_PATH") or
                str(Path(env.get("XDG_CONFIG_HOME") or Path.home()/".config")/"pve/config.json")).expanduser()

def load_config(env=None):
    env = os.environ if env is None else env
    file = config_path(env)
    try:
        profile = json.loads(file.read_text())
    except FileNotFoundError:
        raise ValueError(f"Create {file} from examples/pve.config.example.json; keep machine settings outside the plugin.")
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read a valid PVE profile at {file}: {error}")
    if not isinstance(profile, dict) or profile.get("version") != 1:
        raise ValueError("PVE profile requires version: 1.")
    unknown = set(profile) - set(FIELDS) - {"version"}
    if unknown:
        raise ValueError("Unknown PVE profile fields: " + ", ".join(sorted(unknown)))
    values = {}
    for key, suffix in FIELDS.items():
        value = env.get("PVE_" + suffix, env.get("UTILS_PVE_" + suffix, profile.get(key)))
        if key == "template":
            try:
                if isinstance(value, bool) or not isinstance(value, (int, str)): raise ValueError()
                value = int(value)
                if value < 100: raise ValueError()
            except (TypeError, ValueError):
                raise ValueError("template must be a VMID integer >= 100.")
        else:
            if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError(key + " must be a string without control characters.")
            if not value and key != "fw_group":
                raise ValueError(key + " must not be empty.")
        values[key] = value
    import re
    for key in ("host", "gateway"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]*", values[key]):
            raise ValueError(key + " must be an SSH alias or hostname.")
    if ipaddress.ip_address(values["gateway_ip"]).version != 4:
        raise ValueError("gateway_ip must be IPv4; current provisioning uses a /24 subnet.")
    for key in ("gateway_dns", "gateway_caddy", "gateway_env"):
        if not values[key].startswith("/") or ".." in Path(values[key]).parts:
            raise ValueError(key + " must be an absolute remote path without '..'.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", values["bridge"]):
        raise ValueError("bridge must be a bridge or VNet name.")
    if values["fw_group"] and not re.fullmatch(r"[A-Za-z0-9_.-]+", values["fw_group"]):
        raise ValueError("fw_group must be a firewall group name or empty.")
    from urllib.parse import urlparse
    mirror = urlparse(values["debian_mirror"])
    if mirror.scheme not in ("http", "https") or not mirror.hostname or mirror.username or mirror.password:
        raise ValueError("debian_mirror must be an HTTP(S) URL without credentials.")
    return values
