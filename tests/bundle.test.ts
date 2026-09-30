import { test, expect } from "bun:test";
import { mkdtemp, cp, writeFile, readFile, rm, chmod } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { z } from "zod";
import { pveTools } from "../src/tools/pve.ts";

test("installed bundle runs without node_modules and preserves read/confirmation contracts", async () => {
  const root = new URL("../", import.meta.url);
  const temp = await mkdtemp(join(tmpdir(), "pve plugin "));
  const client = new Client({ name: "pve-test", version: "1" });
  try {
    for (const dir of ["dist", "scripts", "lib"]) {
      await cp(new URL(dir, root), join(temp, dir), { recursive: true });
    }
    const config = join(temp, "config.json");
    const log = join(temp, "ssh.log");
    const fakeSsh = join(temp, "ssh");
    await writeFile(fakeSsh, `#!/bin/sh
printf '%s\\n' "$*" >> "$PVE_TEST_SSH_LOG"
case "$*" in
  'pve qm list') printf 'VMID NAME STATUS MEM(MB) BOOTDISK(GB) PID\\n101 example running 2048 8 1\\n' ;;
  'pve pct list') printf 'VMID Status Lock Name\\n200 stopped example-ct\\n' ;;
  *) echo 'unexpected SSH operation' >&2; exit 93 ;;
esac
`);
    await chmod(fakeSsh, 0o755);
    const env = Object.fromEntries(Object.entries(process.env).filter(([key,value]) => value !== undefined && !key.startsWith("PVE_") && !key.startsWith("UTILS_PVE_"))) as Record<string,string>;
    Object.assign(env, { PVE_CONFIG_PATH: config, PVE_TEST_SSH_LOG: log, PATH: temp + ":" + process.env.PATH });
    await client.connect(new StdioClientTransport({ command: process.execPath, args: [join(temp, "dist/server.js")], cwd: temp, env, stderr: "pipe" }));
    const listed = await client.listTools();
    expect(listed.tools.map(t => t.name).sort()).toEqual(pveTools.map(t => t.name).sort());
    expect(listed.tools).toHaveLength(16);
    const missing = await client.callTool({ name: "pve_list_guests", arguments: {} });
    expect(missing.isError).toBe(true);
    expect(JSON.stringify(missing)).toContain("Invalid PVE configuration");
    await cp(new URL("examples/pve.config.example.json", root), config);
    const result = await client.callTool({ name: "pve_list_guests", arguments: {} });
    expect(result.isError).not.toBe(true);
    expect(z.object(pveTools.find(t => t.name === "pve_list_guests")!.outputSchema).safeParse(result.structuredContent).success).toBe(true);
    expect((result.structuredContent as { data: unknown[] }).data).toHaveLength(2);
    const before = await readFile(log, "utf8");
    const rejected = await client.callTool({ name: "pve_destroy_guest", arguments: { name: "example" } });
    expect(rejected.isError).toBe(true);
    expect(await readFile(log, "utf8")).toBe(before);
    expect(before.split("\n").filter(Boolean)).toEqual(["pve qm list", "pve pct list"]);
  } finally {
    await client.close();
    await rm(temp, { recursive: true, force: true });
  }
}, 60000);
