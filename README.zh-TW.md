<!-- 翻譯自 README.md @ docs/readme-template-v2。只翻 "For AI agents" 以上的章節，英文版更新時一起改。 -->

<div align="center">

<h1>PVE</h1>

<p><strong>把 Proxmox guest、port forwarding、內部 DNS 和 Caddy 站點變成 MCP 工具。</strong></p>

[![CI](https://img.shields.io/github/actions/workflow/status/zyx1121/pve/check.yml?branch=main&style=flat-square&label=CI)](https://github.com/zyx1121/pve/actions)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-D97757?style=flat-square)](https://github.com/zyx1121/marketplace)
[![License](https://img.shields.io/github/license/zyx1121/pve?style=flat-square)](LICENSE)

[English](README.md) | **繁體中文** | [简体中文](README.zh-CN.md)

</div>

```console
$ pve_add_dns { "host": "dnscheck.internal", "ip": "10.10.10.250", "yes": true }
{"host": "dnscheck.internal", "ip": "10.10.10.250", "action": "added", "verified": true}
```

單節點的 Proxmox 實驗環境加上一台 gateway，日常有很多小事：開 guest、設 port forwarding、加內部 DNS、設反向代理。這個 plugin 透過 SSH 給 Codex 和 Claude Code 16 個工具，所有會改東西的工具都要明確確認。

## 功能

- **管理 guest**：列出、查看、啟動、停止、複製和刪除 VM 與容器。刪除時會一起清掉該 guest 的 forwarding、DNS 記錄、Caddy 站點和 SSH alias。
- **轉發 port**：在主機上新增和移除 iptables DNAT 規則，重開機後仍然有效。
- **編輯內部 DNS**：在 gateway 的 dnsmasq 新增和移除 `*.internal` 記錄，並向 dnsmasq 驗證每一次修改。
- **編輯 Caddy 站點**：預覽差異、執行 `caddy validate`、重新載入 Caddy，載入失敗時自動還原。

## 快速開始

```sh
claude plugin marketplace add zyx1121/marketplace
claude plugin install pve@zyx1121
```

Codex：先 `codex plugin marketplace add zyx1121/marketplace`，再 `codex plugin add pve@zyx1121`。

把 [examples/pve.config.example.json](examples/pve.config.example.json) 複製成 `~/.config/pve/config.json`(權限 600)，填入你的主機 alias、gateway 路徑和 template ID。開新的對話，請它「列出我的 VM」。

需要 Bun 1.3.13 以上、uv、SSH 和 Python 3.11 以上。MCP server 已經打包好。

## 使用方式

| 範圍 | 工具 |
|------|------|
| Guest | `pve_list_guests`、`pve_get_status`、`pve_start_guest`、`pve_stop_guest`、`pve_destroy_guest`、`pve_clone_vm`、`pve_create_ct` |
| Port forwarding | `pve_list_forwards`、`pve_add_forward`、`pve_remove_forward` |
| 內部 DNS | `pve_list_dns`、`pve_add_dns`、`pve_remove_dns` |
| Caddy | `pve_list_caddy`、`pve_add_caddy`、`pve_remove_caddy` |

- 會改東西的工具需要 `yes` 或 `confirm`。`pve_stop_guest` 會直接斷電，`pve_destroy_guest` 無法復原。
- DNS 工具只管內部 dnsmasq，不管公網 DNS。
- 每次呼叫最多 120 秒。逾時不代表已經回滾，重試前先看遠端的狀態。

## 設定

設定檔是 `~/.config/pve/config.json`，可以用 `PVE_CONFIG_PATH` 或 `XDG_CONFIG_HOME` 改位置。

| 欄位 | 作用 |
|------|------|
| `host`、`gateway` | Proxmox 主機和 gateway 的 SSH alias |
| `gateway_ip` | gateway 在 guest 網橋上的位址，決定網段 |
| `gateway_dns`、`gateway_caddy`、`gateway_env` | gateway 上的 dnsmasq hosts 檔、Caddyfile 和環境變數檔 |
| `caddy_reload` | 重新載入 Caddy 的指令 |
| `template`、`ct_template`、`bridge`、`fw_group`、`debian_mirror` | 新 guest 的預設值 |

每個欄位也會讀 `PVE_<KEY>`，它優先於舊的 `UTILS_PVE_<KEY>`，再優先於設定檔。使用者和金鑰由 SSH config 管理，機密留在 gateway 上。沒有設定檔時，工具會回傳設定錯誤，不會自己猜網段。

## 運作方式

Bun 的 MCP server 把每次呼叫交給 uv 執行一支 Python 腳本，腳本再透過 SSH 在主機或 gateway 上操作。

- 如果 dnsmasq 沒有讀設定的 hosts 檔，DNS 修改會在寫入前就失敗。重新載入後，工具會用 `dig` 問 dnsmasq，回報 `verified`。
- 工具直接寫入 hosts 檔本身，所以 symlink 會維持是 symlink。
- port forwarding 會寫進 `/etc/iptables/rules.v4`，但不包含 SDN 自己會加的規則。

## 限制

- 只支援一個 Proxmox 節點、一個 IPv4 /24 的 guest 網段，以及這個實驗環境的 VMID、SSH port 和防火牆群組慣例。它不是通用的 cluster 管理工具。
- 設定檔裡的 template、網橋、防火牆群組和 gateway 服務都要先存在。

## 其他

給 AI agent 的結構化資訊與開發說明在[英文版](README.md#for-ai-agents)。

## 授權

[MIT](LICENSE)
