import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { ToolAnnotations } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import { runScript } from "./exec.ts";
import { mcpResult, type ToolRunResult } from "./result.ts";
import { envelopeOutput } from "./schema.ts";

export interface ToolboxTool {
  name: string;
  description: string;
  inputSchema: z.ZodRawShape;
  outputSchema: z.ZodRawShape;
  annotations: ToolAnnotations;
  run(args: Record<string, unknown>): Promise<ToolRunResult>;
}
interface Definition<Shape extends z.ZodRawShape> {
  name: string;
  description: string;
  inputSchema: Shape;
  outputSchema?: z.ZodRawShape;
  annotations: ToolAnnotations;
  script: string;
  envelope: boolean;
  timeoutMs: number;
  truncationHint?: string;
  buildArgs(input: z.infer<z.ZodObject<Shape>>): string[];
}
export function scriptTool<const Shape extends z.ZodRawShape>(definition: Definition<Shape>): ToolboxTool {
  const schema = z.object(definition.inputSchema);
  return {
    name:definition.name, description:definition.description,
    inputSchema:definition.inputSchema,
    outputSchema:definition.outputSchema ?? envelopeOutput(),
    annotations:definition.annotations,
    async run(args) {
      const input = schema.parse(args);
      return runScript({
        script:definition.script, args:definition.buildArgs(input),
        envelope:definition.envelope, timeoutMs:definition.timeoutMs,
        truncationHint:definition.truncationHint,
      });
    },
  };
}
export function registerTools(server: McpServer, tools: ToolboxTool[]): void {
  const names = new Set<string>();
  for (const tool of tools) {
    if (names.has(tool.name)) throw new Error("duplicate MCP tool name: " + tool.name);
    names.add(tool.name);
    server.registerTool(tool.name, {
      description:tool.description, inputSchema:tool.inputSchema,
      outputSchema:tool.outputSchema, annotations:tool.annotations,
    }, async args => mcpResult(await tool.run(args as Record<string, unknown>)));
  }
}
