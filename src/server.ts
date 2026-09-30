import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { fileURLToPath } from "node:url";
import { registerTools } from "./core/tool.ts";
import { setScriptsDirectory } from "./core/exec.ts";
import { pveTools } from "./tools/pve.ts";
import manifest from "../plugin.json";

setScriptsDirectory(fileURLToPath(new URL("../scripts/", import.meta.url)));
const server = new McpServer({name:manifest.name, version:manifest.version});
// Installing this focused provider explicitly selects its 16-tool surface.
// Configuration and dependency failures are returned by calls, not hidden at startup.
registerTools(server,pveTools);
await server.connect(new StdioServerTransport());
