import { z } from "zod";
import { pushBoolFlag, pushFlag, pushPos } from "../core/argv.ts";
import { envelopeOutput } from "../core/schema.ts";
import { scriptTool, type ToolboxTool } from "../core/tool.ts";

const script = "pve.py";
const envelope = true;
const timeoutMs = 120000;
const name = z.string().describe("VM/CT name or VMID.");
const yes = z.literal(true).describe("Required explicit confirmation; passed as --yes to confirm-gated CLI commands.");
const confirm = z.literal(true).describe("Required explicit confirmation.");

/** Everything here runs over SSH against the live homelab host. */
const read = { readOnlyHint: true, openWorldHint: true } as const;
const write = { readOnlyHint: false, destructiveHint: false, openWorldHint: true } as const;
const destroy = { readOnlyHint: false, destructiveHint: true, openWorldHint: true } as const;

/** 2026-07 outage: a PVEFW rule in rules.v4 broke boot-time restore and cut external access. */
const rulesV4Trap = "rules.v4 must hold manual rules only; a PVEFW rule mixed in makes boot-time iptables-restore fail wholesale.";

export const pveTools: ToolboxTool[] = [
  scriptTool({
    name: "pve_list_guests",
    description: "List PVE VMs and LXC containers with their run state. Cheapest way to resolve a guest name to a VMID before any other pve call.",
    inputSchema: {},
    outputSchema: envelopeOutput(
      z.array(
        z.looseObject({
          vmid: z.number(),
          name: z.string(),
          status: z.string(),
          type: z.string().describe("qm for QEMU VMs, lxc for containers."),
          mem_mb: z.number().optional().describe("Present for VMs; absent for containers."),
        }),
      ),
    ),
    annotations: read,
    script,
    envelope,
    timeoutMs,
    buildArgs: () => ["list"],
  }),
  scriptTool({
    name: "pve_get_status",
    description: "Overall PVE status (node uptime/mem/disk + all guests) when name omitted; config and status for one guest when name given. Pass name to keep the response small.",
    inputSchema: { name: name.optional() },
    annotations: read,
    script,
    envelope,
    timeoutMs,
    truncationHint: "pass name to scope the status to one guest",
    buildArgs: (input) => (input.name ? ["status", input.name] : ["status"]),
  }),
  scriptTool({
    name: "pve_start_guest",
    description: "Start a stopped VM or LXC container. Starting an already-running guest is a no-op.",
    inputSchema: { name },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => ["start", input.name],
  }),
  scriptTool({
    name: "pve_stop_guest",
    description: "Force-stop a running VM/container. This is a power cut, not a graceful shutdown, so in-flight writes can be lost. Destructive; pass yes=true to confirm.",
    inputSchema: { name, yes },
    annotations: destroy,
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => {
      const argv = ["stop", input.name];
      pushFlag(argv, "--yes", input.yes);
      return argv;
    },
  }),
  scriptTool({
    name: "pve_destroy_guest",
    description: "Permanently destroy a VM/container and cascade cleanup of its disks, forwards and DNS. Irreversible, no snapshot is taken; pass yes=true to confirm.",
    inputSchema: { name, yes },
    annotations: destroy,
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => {
      const argv = ["destroy", input.name];
      pushFlag(argv, "--yes", input.yes);
      return argv;
    },
  }),
  scriptTool({
    name: "pve_clone_vm",
    description: "Clone a new QEMU VM from a template, with optional forward/firewall setup. Confirm-gated. Prefer this over pve_create_ct when the workload runs Docker or needs its own kernel.",
    inputSchema: {
      name: z.string().describe("New VM name."),
      ip: z.string().optional().describe("Internal IP."),
      template: z.number().optional().describe("Source template VMID."),
      vmid: z.number().optional().describe("Target VMID."),
      cores: z.number().optional().describe("CPU core count."),
      ram: z.number().optional().describe("RAM in MB."),
      disk: z.number().optional().describe("Disk size in GB."),
      no_forward: z.boolean().optional().describe("Skip SSH port forward."),
      no_isolate: z.boolean().optional().describe("Skip spoke firewall isolation."),
      yes,
    },
    annotations: write,
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => {
      const argv = ["clone", input.name];
      pushFlag(argv, "--ip", input.ip);
      pushFlag(argv, "--template", input.template);
      pushFlag(argv, "--vmid", input.vmid);
      pushFlag(argv, "--cores", input.cores);
      pushFlag(argv, "--ram", input.ram);
      pushFlag(argv, "--disk", input.disk);
      pushFlag(argv, "--no-forward", input.no_forward);
      pushFlag(argv, "--no-isolate", input.no_isolate);
      pushFlag(argv, "--yes", input.yes);
      return argv;
    },
  }),
  scriptTool({
    name: "pve_create_ct",
    description: "Create a new LXC container, with optional forward/firewall setup. Confirm-gated. Running Docker inside LXC needs nesting=true and stays fragile here, so prefer pve_clone_vm for container workloads.",
    inputSchema: {
      name: z.string().describe("Container hostname."),
      template: z.string().optional().describe("vztmpl volid."),
      vmid: z.number().optional().describe("Target VMID."),
      ip: z.string().optional().describe("Internal IP."),
      cores: z.number().optional().describe("CPU core count."),
      ram: z.number().optional().describe("RAM in MB."),
      disk: z.number().optional().describe("Root filesystem GB."),
      swap: z.number().optional().describe("Swap MB."),
      storage: z.string().optional().describe("Storage pool."),
      unprivileged: z.boolean().optional().describe("true -> --unprivileged; false -> --privileged."),
      nesting: z.boolean().optional().describe("Enable container nesting."),
      no_forward: z.boolean().optional().describe("Skip SSH port forward."),
      no_isolate: z.boolean().optional().describe("Skip spoke firewall isolation."),
      yes,
    },
    annotations: write,
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => {
      const argv = ["create-ct", input.name];
      pushFlag(argv, "--template", input.template);
      pushFlag(argv, "--vmid", input.vmid);
      pushFlag(argv, "--ip", input.ip);
      pushFlag(argv, "--cores", input.cores);
      pushFlag(argv, "--ram", input.ram);
      pushFlag(argv, "--disk", input.disk);
      pushFlag(argv, "--swap", input.swap);
      pushFlag(argv, "--storage", input.storage);
      pushBoolFlag(argv, "--unprivileged", input.unprivileged, "--privileged");
      pushFlag(argv, "--nesting", input.nesting);
      pushFlag(argv, "--no-forward", input.no_forward);
      pushFlag(argv, "--no-isolate", input.no_isolate);
      pushFlag(argv, "--yes", input.yes);
      return argv;
    },
  }),
  scriptTool({
    name: "pve_list_forwards",
    description: "List PVE gateway port-forward rules as raw iptables lines. Read this first: pve_remove_forward addresses rules by line number.",
    inputSchema: {},
    outputSchema: envelopeOutput(z.looseObject({ rules: z.array(z.string()) })),
    annotations: read,
    script,
    envelope,
    timeoutMs,
    buildArgs: () => ["forward", "--action", "list"],
  }),
  scriptTool({
    name: "pve_add_forward",
    description: `Add HOST_PORT:VM_IP:VM_PORT port forward, exposing an internal service to the public internet. Requires confirm=true. ${rulesV4Trap}`,
    inputSchema: { spec: z.string().describe("HOST_PORT:VM_IP:VM_PORT."), confirm },
    annotations: write,
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => ["forward", input.spec, "--action", "add"],
  }),
  scriptTool({
    name: "pve_remove_forward",
    description: `Remove a PVE forward by iptables line number. Line numbers shift after every removal, so re-read pve_list_forwards between deletions. Destructive; requires confirm=true. ${rulesV4Trap}`,
    inputSchema: { line: z.number().describe("Line number from pve_list_forwards."), confirm },
    annotations: destroy,
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => ["forward", "--action", "del", "--line", String(input.line)],
  }),
  scriptTool({
    name: "pve_list_dns",
    description: "List gateway dnsmasq internal DNS records.",
    inputSchema: {},
    outputSchema: envelopeOutput(
      z.looseObject({
        records: z.array(z.looseObject({ ip: z.string(), host: z.string() })),
        hosts_file: z.string().describe("Path of the hosts file on the gateway."),
      }),
    ),
    annotations: read,
    script,
    envelope,
    timeoutMs,
    buildArgs: () => ["dns", "--action", "list"],
  }),
  scriptTool({
    name: "pve_add_dns",
    description: "Add or preview an internal DNS record. Use dry_run=true first to see the diff without writing.",
    inputSchema: { host: z.string().describe("Hostname."), ip: z.string().describe("IP address."), dry_run: z.boolean().optional().describe("Preview without writing."), yes },
    annotations: write,
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => {
      const argv = ["dns", input.host, input.ip, "--action", "add"];
      pushFlag(argv, "--dry-run", input.dry_run);
      pushFlag(argv, "--yes", input.yes);
      return argv;
    },
  }),
  scriptTool({
    name: "pve_remove_dns",
    description: "Remove an internal DNS record. Anything resolving through this name breaks immediately. Destructive; pass yes=true to confirm.",
    inputSchema: { host: z.string().describe("Hostname."), yes },
    annotations: destroy,
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => {
      const argv = ["dns", input.host, "--action", "remove"];
      pushFlag(argv, "--yes", input.yes);
      return argv;
    },
  }),
  scriptTool({
    name: "pve_list_caddy",
    description: "List Caddy reverse-proxy site blocks with their upstreams.",
    inputSchema: {},
    outputSchema: envelopeOutput(
      z.looseObject({
        domains: z.array(z.string()),
        blocks: z.array(
          z.looseObject({
            domains: z.array(z.string()),
            upstreams: z.array(z.string()),
            tls: z.unknown().describe("false when unset, otherwise the configured TLS setting."),
            routed: z.boolean().optional(),
          }),
        ),
        caddyfile: z.string().describe("Path of the Caddyfile on the gateway."),
      }),
    ),
    annotations: read,
    script,
    envelope,
    timeoutMs,
    truncationHint: "the raw Caddyfile is long; read pve_list_caddy blocks instead of the file",
    buildArgs: () => ["caddy", "--action", "list"],
  }),
  scriptTool({
    name: "pve_add_caddy",
    description: "Add or update a Caddy reverse-proxy block with validation and reload-or-rollback. Publishes a service on a public domain; dry_run=true renders the diff without writing.",
    inputSchema: {
      domain: z.string().describe("Public domain head; comma-join for multi-host block."),
      upstream: z.string().optional().describe("Upstream host:port for simple reverse_proxy."),
      tls: z.string().optional().describe("TLS setting: 'internal' or 'CERT KEY'."),
      body: z.string().optional().describe("Verbatim Caddy block body; mutually exclusive with upstream/tls in the CLI."),
      on_exists: z.enum(["update", "skip", "fail"]).optional().describe("Existing block behavior. Default: update."),
      dry_run: z.boolean().optional().describe("Render/validate diff without writing."),
      yes,
    },
    annotations: write,
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => {
      const argv = ["caddy", input.domain];
      pushPos(argv, input.upstream);
      pushFlag(argv, "--action", "add");
      pushFlag(argv, "--tls", input.tls);
      pushFlag(argv, "--body", input.body);
      pushFlag(argv, "--on-exists", input.on_exists);
      pushFlag(argv, "--dry-run", input.dry_run);
      pushFlag(argv, "--yes", input.yes);
      return argv;
    },
  }),
  scriptTool({
    name: "pve_remove_caddy",
    description: "Remove a Caddy site block, taking that public domain offline. Destructive; pass yes=true to confirm.",
    inputSchema: { domain: z.string().describe("Domain block to remove."), yes },
    annotations: destroy,
    script,
    envelope,
    timeoutMs,
    buildArgs: (input) => {
      const argv = ["caddy", input.domain, "--action", "remove"];
      pushFlag(argv, "--yes", input.yes);
      return argv;
    },
  }),
];
