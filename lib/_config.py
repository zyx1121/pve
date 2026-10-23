"""Private environment profile shared by every PVE script operation."""
from __future__ import annotations
import ipaddress
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

# Shared by every node: the gateway runs dnsmasq and Caddy for the whole lab.
GATEWAY_FIELDS = {
    "gateway": "GATEWAY",
    "gateway_dns": "GATEWAY_DNS",
    "gateway_caddy": "GATEWAY_CADDY",
    "gateway_env": "GATEWAY_ENV",
    "caddy_reload": "CADDY_RELOAD",
}
# One set per Proxmox node.
NODE_FIELDS = {
    "host": "HOST",
    "template": "TEMPLATE",
    "gateway_ip": "GATEWAY_IP",
    "bridge": "BRIDGE",
    "fw_group": "FW_GROUP",
    "ct_template": "CT_TEMPLATE",
    "debian_mirror": "DEBIAN_MIRROR",
    "vmid_base": "VMID_BASE",
    "ssh_forward": "SSH_FORWARD",
}
FIELDS = {**GATEWAY_FIELDS, **NODE_FIELDS}
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


def config_path(env=None):
    env = os.environ if env is None else env
    return Path(env.get("PVE_CONFIG_PATH") or
                str(Path(env.get("XDG_CONFIG_HOME") or Path.home()/".config")/"pve/config.json")).expanduser()


def _int(key, value, low):
    try:
        if isinstance(value, bool) or not isinstance(value, (int, str)): raise ValueError()
        value = int(value)
        if value < low: raise ValueError()
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be an integer >= {low}.")
    return value


def _bool(key, value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("1", "true", "0", "false"):
        return value.lower() in ("1", "true")
    raise ValueError(key + " must be true or false.")


def load_config(env=None, node=None):
    """Return the flat settings of one node plus the shared gateway.

    `node` picks a key of `nodes`; without it the profile's `default_node` applies.
    PVE_<KEY> environment variables override the chosen node's values."""
    env = os.environ if env is None else env
    file = config_path(env)
    try:
        profile = json.loads(file.read_text())
    except FileNotFoundError:
        raise ValueError(f"Create {file} from examples/pve.config.example.json; keep machine settings outside the plugin.")
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read a valid PVE profile at {file}: {error}")
    if not isinstance(profile, dict) or profile.get("version") != 2:
        raise ValueError("PVE profile requires version: 2 (one gateway, several nodes); see examples/pve.config.example.json.")
    unknown = set(profile) - set(GATEWAY_FIELDS) - {"version", "default_node", "nodes"}
    if unknown:
        raise ValueError("Unknown PVE profile fields: " + ", ".join(sorted(unknown)))
    nodes = profile.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        raise ValueError("nodes must map each node name to its settings.")
    for name in nodes:
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError(f"node name {name!r} must be letters, digits, '.', '_' or '-'.")
    chosen = node or env.get("PVE_NODE") or profile.get("default_node")
    if chosen not in nodes:
        raise ValueError(f"Unknown node {chosen!r}; the profile has: {', '.join(sorted(nodes))}.")
    settings = nodes[chosen]
    if not isinstance(settings, dict):
        raise ValueError(f"nodes.{chosen} must be an object.")
    unknown = set(settings) - set(NODE_FIELDS)
    if unknown:
        raise ValueError(f"Unknown fields in nodes.{chosen}: " + ", ".join(sorted(unknown)))

    defaults = {"vmid_base": 0, "ssh_forward": True}
    values = {"node": chosen, "nodes": sorted(nodes)}
    for key, suffix in FIELDS.items():
        source = settings if key in NODE_FIELDS else profile
        value = env.get("PVE_" + suffix, env.get("UTILS_PVE_" + suffix, source.get(key, defaults.get(key))))
        if key == "template":
            value = _int(key, value, 100)
        elif key == "vmid_base":
            value = _int(key, value, 0)
            if value % 1000:
                raise ValueError("vmid_base must be a multiple of 1000.")
        elif key == "ssh_forward":
            value = _bool(key, value)
        else:
            if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
                raise ValueError(key + " must be a string without control characters.")
            if not value and key != "fw_group":
                raise ValueError(key + " must not be empty.")
        values[key] = value
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
    mirror = urlparse(values["debian_mirror"])
    if mirror.scheme not in ("http", "https") or not mirror.hostname or mirror.username or mirror.password:
        raise ValueError("debian_mirror must be an HTTP(S) URL without credentials.")
    return values
