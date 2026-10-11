# pve

Claude Code and Codex plugin: a Bun MCP server (`src/`, bundled to `dist/server.js`) that runs `scripts/pve.py` under uv, which works over SSH. Read [README.md](README.md) first.

## Rules

- A tool that changes the host or the gateway needs `yes` or `confirm`. Keep it.
- Pass every value that reaches a remote shell through `_valid_dns_host`, `ipaddress` or `shlex.quote`.
- Write remote files in place (`cat tmp > file`), never with `mv tmp file`. A rename turns a symlinked target into a regular copy.
- A DNS edit must reach a file that dnsmasq reads, then pass the `dig` test. Do not weaken `_require_served` or `_dnsmasq_answer`.
- No private network defaults in code. Every site value comes from the profile.
- `plugin.json` and `mcp.json` are the manifest sources. Do not hand-edit the generated `.claude-plugin/plugin.json`, `.mcp.json` or `dist/server.js`.
- Repository documents and code comments are English.

## Where to run things

In Loki's environment, the MacBook is for editing and git only. Run `bun install`, the build and the tests on `ssh sandbox` in a login shell (`bash -lc`). You can test DNS against the real gateway, but only with a throwaway name such as `dnscheck.internal`. Remove it right after.

## Verify

```sh
bun install --frozen-lockfile
bun run check
```

- Build with the Bun version that CI uses (`bun-version` in `.github/workflows/check.yml`). Another version produces a different `dist/server.js`, and the CI diff step fails.
- Never put a real hostname in a test that removes records. A wrong pattern can empty the hosts file.

## Release

1. Bump `version` in `package.json` and `plugin.json`, run `bun run check`, and commit the regenerated files.
2. Merge the PR. Then pin the new commit in [zyx1121/marketplace](https://github.com/zyx1121/marketplace) (see its AGENTS.md).
