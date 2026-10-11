/**
 * Tier A output schemas parsed against synthetic samples.
 *
 * The samples mirror the key set of real runs captured while writing these
 * schemas, with every value replaced by placeholder data — this repo is public,
 * so no real host, address or calendar name is committed.
 */
import { describe, expect, test } from "bun:test";
import { z } from "zod";
import { mapScriptOutput } from "../src/core/exec.ts";
import { pveTools as allTools } from "../src/tools/pve.ts";

function outputSchemaOf(name: string) {
  const tool = allTools.find((candidate) => candidate.name === name);
  if (!tool) throw new Error(`unknown tool: ${name}`);
  return z.object(tool.outputSchema);
}

const SAMPLES: Record<string, unknown> = {
  pve_list_guests: [
    { vmid: 101, name: "example-vm", status: "running", mem_mb: 8192, type: "qm" },
    { vmid: 200, name: "example-ct", status: "stopped", type: "lxc" },
  ],
  pve_list_forwards: { rules: ["Chain PREROUTING (policy ACCEPT)", "1    DNAT    tcp  --  anywhere  anywhere  tcp dpt:2201"] },
  pve_list_dns: {
    records: [{ ip: "10.0.0.1", host: "example.internal" }],
    hosts_file: "/example/gateway/dns/hosts",
    served: true,
  },
  pve_list_caddy: {
    domains: ["example.test"],
    blocks: [{ domains: ["example.test"], upstreams: ["10.0.0.2:3000"], tls: false, routed: false }],
    caddyfile: "/example/gateway/Caddyfile",
  },

};

describe("Tier A output schemas", () => {
  for (const [name, data] of Object.entries(SAMPLES)) {
    test(`${name} accepts its real-world shape`, () => {
      const result = outputSchemaOf(name).safeParse({ data, metadata: { count: 1 } });
      expect(result.success ? null : result.error.issues).toBeNull();
    });

    test(`${name} tolerates keys added upstream`, () => {
      const widened = Array.isArray(data) ? [...(data as Record<string, unknown>[]).map((item) => ({ ...item, future_key: "x" }))] : { ...(data as Record<string, unknown>), future_key: "x" };
      const result = outputSchemaOf(name).safeParse({ data: widened, metadata: {} });
      expect(result.success).toBe(true);
    });
  }

  test("the truncation report is optional but accepted", () => {
    const schema = outputSchemaOf("pve_list_guests");

    expect(schema.safeParse({ data: [{ name: "Example", vmid: 101, status: "running", type: "qm" }], metadata: {} }).success).toBe(true);
    expect(
      schema.safeParse({
        data: [{ name: "Example", vmid: 101, status: "running", type: "qm" }],
        metadata: {},
        _truncation: { fields: ["data[0].name"], original_chars: 999, limit: 100 },
      }).success,
    ).toBe(true);
  });

  test("Tier B tools still name the envelope shell", () => {
    const schema = outputSchemaOf("pve_get_status");

    expect(schema.safeParse({ data: { anything: true }, metadata: {} }).success).toBe(true);
  });


});

/**
 * Regression guard for the failure path.
 *
 * The MCP client validates structuredContent against the declared schema even
 * when isError is set, and the generated JSON Schema forbids extra properties.
 * A failure shape that the tool's own schema rejects therefore reaches the
 * caller as a protocol error rather than a readable message. Caught by a live
 * smoke run against safari_get_url with no Safari window open.
 */
describe("failure paths satisfy their own output schema", () => {
  const run = (over: Partial<Parameters<typeof mapScriptOutput>[1]> = {}) => ({
    stdout: "",
    stderr: "",
    exitCode: 1,
    timedOut: false,
    timeoutMs: 1000,
    argv0: "example.py",
    ...over,
  });

  const CASES = {
    "script reported failure": run({ stdout: JSON.stringify({ success: false, error: { message: "boom", why: "because", hint: "do x" } }) }),
    "failure with bare message": run({ stdout: JSON.stringify({ success: false, error: { message: "boom" } }) }),
    "failure with no error detail": run({ stdout: JSON.stringify({ success: false }) }),
    "crash before any output": run({ stderr: "Traceback (most recent call last):", exitCode: 2 }),
    "json that is not an envelope": run({ stdout: JSON.stringify({ whatever: true }) }),
    "timeout": run({ timedOut: true, exitCode: -1 }),
  };

  // Every PVE operation uses the same envelope contract.
  const scriptTools = allTools.filter((tool) => "data" in tool.outputSchema || "stdout" in tool.outputSchema);

  for (const tool of scriptTools) {
    const isEnvelope = "data" in tool.outputSchema;
    const schema = z.object(tool.outputSchema);

    for (const [label, scriptRun] of Object.entries(CASES)) {
      test(`${tool.name}: ${label}`, () => {
        const result = mapScriptOutput(isEnvelope, scriptRun);
        const parsed = schema.safeParse(result.structuredContent);

        expect(parsed.success ? null : { issues: parsed.error.issues, got: result.structuredContent }).toBeNull();
        expect(result.isError).toBe(true);
      });
    }
  }


});
