import { describe, expect, test } from "bun:test";
import type { ToolboxTool } from "../src/core/tool.ts";
import { pveTools } from "../src/tools/pve.ts";
function getTool(name: string): ToolboxTool {
  const tool = pveTools.find((candidate) => candidate.name === name);
  if (!tool) throw new Error(`missing test tool ${name}`);
  return tool;
}

async function runCaptured(name: string, input: Record<string, unknown>): Promise<{ argv: string[]; env?: Record<string, string | undefined> }> {
  const tool = getTool(name);
  let captured: string[] | undefined;
  let capturedEnv: Record<string, string | undefined> | undefined;
  const original = Bun.spawn;
  Bun.spawn = ((argv: string[], options?: { env?: Record<string, string | undefined> }) => {
    captured = argv.slice(1);
    capturedEnv = options?.env;
    return {
      stdout: new ReadableStream({ start(controller) { controller.close(); } }),
      stderr: new ReadableStream({ start(controller) { controller.close(); } }),
      exited: Promise.resolve(0),
      kill() {},
    };
  }) as typeof Bun.spawn;

  try {
    await tool.run(input);
    if (!captured) throw new Error("argv was not captured");
    return { argv: captured, env: capturedEnv };
  } finally {
    Bun.spawn = original;
  }
}

async function expectRejected(name: string, input: Record<string, unknown>): Promise<void> {
  const original = Bun.spawn;
  Bun.spawn = (() => {
    throw new Error("spawn should not be reached");
  }) as typeof Bun.spawn;

  try {
    await expect(getTool(name).run(input)).rejects.toThrow();
  } finally {
    Bun.spawn = original;
  }
}

describe("PVE argv compatibility", () => {
  test("pve_create_ct maps unprivileged=false to --privileged", async () => {
    expect((await runCaptured("pve_create_ct", { name: "dev", unprivileged: false, yes: true })).argv).toEqual(["create-ct", "dev", "--privileged", "--yes"]);
  });

  test("pve_add_caddy maps the split add tool without action ambiguity", async () => {
    expect((await runCaptured("pve_add_caddy", { domain: "app.example.com", upstream: "10.0.0.2:3000", dry_run: true, yes: true })).argv).toEqual([
      "caddy",
      "app.example.com",
      "10.0.0.2:3000",
      "--action",
      "add",
      "--dry-run",
      "--yes",
    ]);
  });

  test("pve_add_dns passes confirmation to the confirm-gated add path", async () => {
    expect((await runCaptured("pve_add_dns", { host: "dev.internal", ip: "10.0.0.2", yes: true })).argv).toEqual([
      "dns",
      "dev.internal",
      "10.0.0.2",
      "--action",
      "add",
      "--yes",
    ]);
  });

  test("pve_remove_forward requires MCP-level confirmation but does not invent a CLI flag", async () => {
    expect((await runCaptured("pve_remove_forward", { line: 4, confirm: true })).argv).toEqual(["forward", "--action", "del", "--line", "4"]);
  });

  test("node leads the argv of guest and forward tools", async () => {
    expect((await runCaptured("pve_list_guests", { node: "pve2" })).argv).toEqual(["--node", "pve2", "list"]);
    expect((await runCaptured("pve_clone_vm", { node: "pve2", name: "web", yes: true })).argv).toEqual(["--node", "pve2", "clone", "web", "--yes"]);
    expect((await runCaptured("pve_remove_forward", { node: "pve2", line: 4, confirm: true })).argv).toEqual(["--node", "pve2", "forward", "--action", "del", "--line", "4"]);
    expect((await runCaptured("pve_get_status", {})).argv).toEqual(["status"]);
  });

  test("gateway tools take no node, and a node name cannot carry flags", async () => {
    for (const name of ["pve_list_dns", "pve_add_dns", "pve_remove_dns", "pve_list_caddy", "pve_add_caddy", "pve_remove_caddy"]) {
      expect("node" in getTool(name).inputSchema).toBe(false);
    }
    await expectRejected("pve_list_guests", { node: "--yes" });
    await expectRejected("pve_list_guests", { node: "a b" });
  });

  test("all confirm-gated operations reject missing or false confirmation", async () => {
    for (const tool of pveTools) {
      const gate = "yes" in tool.inputSchema ? "yes" : "confirm" in tool.inputSchema ? "confirm" : undefined;
      if (!gate) continue;
      const input = { name: "example", domain: "example.test", upstream: "192.0.2.2:3000", host: "example.internal", ip: "192.0.2.2", spec: "5001:192.0.2.2:22", line: 1 };
      await expectRejected(tool.name, input);
      await expectRejected(tool.name, { ...input, [gate]: false });
    }
  });
});
