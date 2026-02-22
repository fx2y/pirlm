import { Type } from "@sinclair/typebox";
import { runtime } from "./spawn";

export const PirmlRunParams = Type.Object({
  task: Type.String({ description: "The python program to run" }),
  mode: Type.Optional(Type.String({ description: "Execution mode" })),
  timeout: Type.Optional(Type.Number({ description: "Timeout in seconds" })),
});

export async function handlePirmlRunTool(
  id: string,
  params: any,
  signal: AbortSignal,
  onUpdate: (update: any) => void,
  ctx: any
) {
  const { task, timeout } = params;
  const timeoutMs = timeout ? timeout * 1000 : 60000;
  
  const ts = Date.now();
  const runId = `r${ts}`;
  const outDir = `out/${runId}`;
  const artDir = "art";

  try {
    const res = await runtime.spawn(task, outDir, artDir, timeoutMs);
    
    // B2: return ToolResult content small + details big pointers
    return {
      content: [
        {
          type: "text",
          text: res.ok ? `PIRML run ${res.runId} completed successfully.` : `PIRML run ${res.runId} failed: ${res.error?.msg}`,
        },
      ],
      details: {
        runId: res.runId,
        trace: res.trace,
        final: res.final,
        artifacts: res.artifacts,
        ok: res.ok,
      },
    };
  } catch (err: any) {
    return {
      content: [
        {
          type: "text",
          text: `PIRML run failed with exception: ${err.message}`,
        },
      ],
      details: {
        error: err.message,
        ok: false,
      },
    };
  }
}
