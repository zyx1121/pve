<div align="center">

<h1>PVE</h1>

<p><strong>Proxmox guests, port forwards, internal DNS and Caddy sites as MCP tools.</strong></p>

[![CI](https://img.shields.io/github/actions/workflow/status/zyx1121/pve/check.yml?branch=main&style=flat-square&label=CI)](https://github.com/zyx1121/pve/actions)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-D97757?style=flat-square)](https://github.com/zyx1121/marketplace)
[![License](https://img.shields.io/github/license/zyx1121/pve?style=flat-square)](LICENSE)

**English** | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

</div>

```console
$ pve_add_dns { "host": "dnscheck.internal", "ip": "10.10.10.250", "yes": true }
{"host": "dnscheck.internal", "ip": "10.10.10.250", "action": "added", "verified": true}
```

A single-node Proxmox lab with a gateway runs on many small chores: guests, port forwards, internal DNS records and reverse-proxy sites. This plugin gives Codex and Claude Code 16 tools for them over SSH. Each tool that changes something needs an explicit confirmation.

## Features

- **Manages guests**: lists, inspects, starts, stops, clones and destroys VMs and containers. A destroy also removes the guest's forwards, DNS records, Caddy sites and SSH alias.
- **Forwards ports**: adds and removes iptables DNAT rules on the host and keeps them across reboots.
- **Edits internal DNS**: adds and removes `*.internal` records in the gateway's dnsmasq, then verifies each change with dnsmasq.
- **Edits Caddy sites**: previews the diff, runs `caddy validate`, reloads Caddy and rolls back when the reload fails.

## Quick start

```sh
claude plugin marketplace add zyx1121/marketplace
claude plugin install pve@zyx1121
```

Codex: `codex plugin marketplace add zyx1121/marketplace`, then `codex plugin add pve@zyx1121`.

Copy [examples/pve.config.example.json](examples/pve.config.example.json) to `~/.config/pve/config.json` (mode 600), and set your host aliases, gateway paths and template IDs. Start a new session and ask "List my VMs".

The plugin needs Bun 1.3.13 or later, uv, SSH, and Python 3.11 or later. The MCP server ships bundled.

## Usage

| Area | Tools |
|------|-------|
| Guests | `pve_list_guests`, `pve_get_status`, `pve_start_guest`, `pve_stop_guest`, `pve_destroy_guest`, `pve_clone_vm`, `pve_create_ct` |
| Port forwards | `pve_list_forwards`, `pve_add_forward`, `pve_remove_forward` |
| Internal DNS | `pve_list_dns`, `pve_add_dns`, `pve_remove_dns` |
| Caddy | `pve_list_caddy`, `pve_add_caddy`, `pve_remove_caddy` |

- Tools that change something need `yes` or `confirm`. `pve_stop_guest` cuts the power, and `pve_destroy_guest` cannot be undone.
- The DNS tools manage the internal dnsmasq only, not public DNS.
- A call has a 120-second limit. A timeout does not mean a rollback, so look at the remote state before you retry.

## Configuration

`~/.config/pve/config.json` holds the profile. `PVE_CONFIG_PATH` and `XDG_CONFIG_HOME` move it.

| Key | Sets |
|-----|------|
| `host`, `gateway` | SSH aliases of the Proxmox host and the gateway |
| `gateway_ip` | gateway address on the guest bridge, which sets the subnet |
| `gateway_dns`, `gateway_caddy`, `gateway_env` | the dnsmasq hosts file, the Caddyfile and the environment file on the gateway |
| `caddy_reload` | the command that reloads Caddy |
| `template`, `ct_template`, `bridge`, `fw_group`, `debian_mirror` | defaults for new guests |

Each key also reads `PVE_<KEY>`, which wins over the older `UTILS_PVE_<KEY>`, which wins over the file. SSH config keeps the users and keys. Secrets stay on the gateway. Without a profile, the tools return a setup error instead of guessing a network.

## How it works

The Bun MCP server runs each call as a Python script under uv. The script works over SSH on the host or the gateway.

- DNS edits fail before they write when dnsmasq does not read the configured hosts file. After a reload, the tools ask dnsmasq with `dig` and report `verified`.
- The tools write the hosts file in place, so a symlinked file stays a symlink.
- Port forwards persist to `/etc/iptables/rules.v4` without the rules that the SDN adds by itself.

## Limits

- One Proxmox node with an IPv4 /24 guest network, and the VMID, SSH port and firewall group conventions of this lab. It is not a general cluster manager.
- The template, bridge, firewall group and gateway services in the profile must exist first.

## For AI agents

Facts for coding agents and LLM tools. The rules for changing the code are in [AGENTS.md](AGENTS.md).

- **Summary**: Plugin with 16 MCP tools for a single-node Proxmox host and its gateway: guests, forwards, dnsmasq records and Caddy sites.
- **Type**: plugin
- **Interfaces**: MCP `pve` (stdio, `dist/server.js`). `scripts/pve.py` also runs as a CLI under uv.
- **Install**: `claude plugin install pve@zyx1121`, after `claude plugin marketplace add zyx1121/marketplace`
- **Run**: the host starts the MCP server
- **Verify**: call `pve_list_guests`, or `pve_list_dns` and expect `served: true`
- **Config**: `~/.config/pve/config.json`, `PVE_CONFIG_PATH`, and `PVE_<KEY>` for each profile key
- **Secrets**: none in the plugin. SSH keys stay in SSH config, and gateway secrets stay on the gateway.
- **Limits**: one node and one /24 guest network. Stop and destroy act at once after confirmation.

## Development

```sh
bun install --frozen-lockfile
bun run check
```

The tests use a fake SSH and temporary files, so they never touch a real host. `plugin.json` and `mcp.json` are the manifest sources. CI fails when the generated files are stale.

## License

[MIT](LICENSE)
