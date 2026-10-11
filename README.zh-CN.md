<!-- 翻译自 README.md @ docs/readme-template-v2。只翻译 "For AI agents" 之前的章节，英文版更新时一起改。 -->

<div align="center">

<h1>PVE</h1>

<p><strong>把 Proxmox guest、端口转发、内部 DNS 和 Caddy 站点变成 MCP 工具。</strong></p>

[![CI](https://img.shields.io/github/actions/workflow/status/zyx1121/pve/check.yml?branch=main&style=flat-square&label=CI)](https://github.com/zyx1121/pve/actions)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-D97757?style=flat-square)](https://github.com/zyx1121/marketplace)
[![License](https://img.shields.io/github/license/zyx1121/pve?style=flat-square)](LICENSE)

[English](README.md) | [繁體中文](README.zh-TW.md) | **简体中文**

</div>

```console
$ pve_add_dns { "host": "dnscheck.internal", "ip": "10.10.10.250", "yes": true }
{"host": "dnscheck.internal", "ip": "10.10.10.250", "action": "added", "verified": true}
```

单节点的 Proxmox 实验环境加上一台 gateway，日常有很多小事：开 guest、设端口转发、加内部 DNS、配反向代理。这个插件通过 SSH 给 Codex 和 Claude Code 16 个工具，所有会改动东西的工具都要明确确认。

## 功能

- **管理 guest**：列出、查看、启动、停止、克隆和删除虚拟机与容器。删除时会一起清理该 guest 的端口转发、DNS 记录、Caddy 站点和 SSH alias。
- **转发端口**：在主机上添加和删除 iptables DNAT 规则，重启后仍然有效。
- **编辑内部 DNS**：在 gateway 的 dnsmasq 添加和删除 `*.internal` 记录，并向 dnsmasq 校验每一次修改。
- **编辑 Caddy 站点**：预览差异、运行 `caddy validate`、重新加载 Caddy，加载失败时自动回滚。

## 快速开始

```sh
claude plugin marketplace add zyx1121/marketplace
claude plugin install pve@zyx1121
```

Codex：先 `codex plugin marketplace add zyx1121/marketplace`，再 `codex plugin add pve@zyx1121`。

把 [examples/pve.config.example.json](examples/pve.config.example.json) 复制为 `~/.config/pve/config.json`(权限 600)，填入你的主机 alias、gateway 路径和 template ID。开新的对话，请它“列出我的虚拟机”。

需要 Bun 1.3.13 以上、uv、SSH 和 Python 3.11 以上。MCP server 已经打包好。

## 使用方法

| 范围 | 工具 |
|------|------|
| Guest | `pve_list_guests`、`pve_get_status`、`pve_start_guest`、`pve_stop_guest`、`pve_destroy_guest`、`pve_clone_vm`、`pve_create_ct` |
| 端口转发 | `pve_list_forwards`、`pve_add_forward`、`pve_remove_forward` |
| 内部 DNS | `pve_list_dns`、`pve_add_dns`、`pve_remove_dns` |
| Caddy | `pve_list_caddy`、`pve_add_caddy`、`pve_remove_caddy` |

- 会改动东西的工具需要 `yes` 或 `confirm`。`pve_stop_guest` 会直接断电，`pve_destroy_guest` 无法恢复。
- DNS 工具只管理内部 dnsmasq，不管公网 DNS。
- 每次调用最多 120 秒。超时不代表已经回滚，重试前先查看远端的状态。

## 配置

配置文件是 `~/.config/pve/config.json`，可以用 `PVE_CONFIG_PATH` 或 `XDG_CONFIG_HOME` 改变位置。

| 字段 | 作用 |
|------|------|
| `host`、`gateway` | Proxmox 主机和 gateway 的 SSH alias |
| `gateway_ip` | gateway 在 guest 网桥上的地址，决定网段 |
| `gateway_dns`、`gateway_caddy`、`gateway_env` | gateway 上的 dnsmasq hosts 文件、Caddyfile 和环境变量文件 |
| `caddy_reload` | 重新加载 Caddy 的命令 |
| `template`、`ct_template`、`bridge`、`fw_group`、`debian_mirror` | 新 guest 的默认值 |

每个字段也会读取 `PVE_<KEY>`，它优先于旧的 `UTILS_PVE_<KEY>`，再优先于配置文件。用户和密钥由 SSH config 管理，机密留在 gateway 上。没有配置文件时，工具会返回配置错误，不会自己猜网段。

## 工作原理

Bun 的 MCP server 把每次调用交给 uv 运行一个 Python 脚本，脚本再通过 SSH 在主机或 gateway 上操作。

- 如果 dnsmasq 没有读取配置的 hosts 文件，DNS 修改会在写入前就失败。重新加载后，工具会用 `dig` 询问 dnsmasq，报告 `verified`。
- 工具直接写入 hosts 文件本身，所以 symlink 会保持是 symlink。
- 端口转发会写入 `/etc/iptables/rules.v4`，但不包含 SDN 自己会加的规则。

## 限制

- 只支持一个 Proxmox 节点、一个 IPv4 /24 的 guest 网段，以及这个实验环境的 VMID、SSH 端口和防火墙组约定。它不是通用的集群管理工具。
- 配置文件里的 template、网桥、防火墙组和 gateway 服务都要先存在。

## 其他

给 AI agent 的结构化信息与开发说明见[英文版](README.md#for-ai-agents)。

## 许可证

[MIT](LICENSE)
