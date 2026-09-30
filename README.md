# PVE

供 Codex 與 Claude Code 使用的 Proxmox／gateway MCP plugin。
從 zyx1121/plugin 的 utils 拆出，提供原有 16 個 PVE tools：

- 查詢、建立、啟動、停止與刪除 VM／LXC。
- 管理主機 port forwarding。
- 管理 gateway dnsmasq 的**內部 DNS**。
- 管理 Caddy 站點，包含 diff 預覽、驗證與 reload 失敗回復。

透過自然語言要求 agent 操作，例如「列出目前的 VM」或「查看 book-prod 狀態」。
本 plugin 只有 MCP 與底層 scripts；工具 schema 是參數與操作語意的來源，
不另維護一份 skill 工具手冊。FDE 可在部署流程中組合使用這些工具。

## 安裝與設定

請 agent 從 `zyx1121/marketplace` 安裝 `pve@zyx1121`。

```sh
# Claude Code
claude plugin marketplace add zyx1121/marketplace
claude plugin install pve@zyx1121

# Codex
codex plugin marketplace add zyx1121/marketplace
codex plugin add pve@zyx1121
```

需要 Bun 1.3.13+、uv、SSH，以及 Python 3.11+（uv 可管理）。
MCP 已打包，不需在安裝目錄執行 bun install；
uv 在首次操作時依 scripts 的 PEP 723 宣告取得 Python 套件。

請 agent 依 [範例](examples/pve.config.example.json) 建立
`~/.config/pve/config.json`（建議權限 0600），填入現有環境設定。
也支援 XDG_CONFIG_HOME 與 PVE_CONFIG_PATH。SSH 主機、使用者及金鑰仍由
SSH config 管理；gateway 的 secrets 留在 gateway。Plugin 升級不覆寫 profile。

[設定載入器](lib/_config.py) 的 FIELDS 定義環境變數對應；
`PVE_<suffix>` 優先於舊的 `UTILS_PVE_<suffix>`，再優先於 profile。
所有操作都使用同一份設定。缺少設定時回傳 setup 錯誤，不會使用某個私人網段。

## 操作範圍

保留原有 yes／confirm 參數。停止是強制斷電；刪除會連帶清理資源，
工具描述會列出影響。安裝 plugin 不代表授權任意修改基礎設施。

DNS tools 只管理內部 dnsmasq，不會設定 Cloudflare 公網 DNS。
Provisioning 沿用既有單節點、IPv4 /24、VMID／SSH port 與 firewall group
慣例；這不是任意 Proxmox cluster 的通用管理套件。Profile 中的 template、
bridge、firewall group 與 gateway 服務必須先存在。

Caddy 操作沿用既有驗證、備份與 reload／rollback 實作。
MCP 呼叫有 120 秒期限；逾時後先查遠端狀態再決定是否重試，
不代表遠端操作已回滾。正式環境的可用性操作仍依使用者指示執行。

## 從 zyx 遷移

安裝並驗證本 plugin 後，將 zyx 更新到移除 PVE 的版本。
工具短名稱與參數保持相同；完整 MCP namespace 會由
`plugin_zyx_utils` 改為 `plugin_pve_pve`，依 host 顯示為準。
引用完整名稱的權限設定、hooks 或消費端需一併調整。
其餘 utils 工具繼續由 zyx 提供，不要同時另註冊同名 pve server。

## 維護

`bun install --frozen-lockfile`，接著 `bun run check`。
測試在本機假 SSH／暫存檔案上驗證參數、confirmation、錯誤 contract 與
iptables persistence，不會改動真實 PVE。

Root plugin.json 與 mcp.json 是唯一 manifest 來源。Build 產生 Claude
相容格式和 dist；生成檔一起提交，CI 檢查是否過期。
發佈使用獨立版本，marketplace 固定到 release commit。

原始 PVE script、schemas、必要 helper 與 persistence test 來自
[zyx1121/plugin@06270b0](https://github.com/zyx1121/plugin/tree/06270b0)，保留 MIT。
本套件沒有對原 repo 的 runtime 依賴。
