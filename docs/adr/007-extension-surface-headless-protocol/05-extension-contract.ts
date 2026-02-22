# Extension Contract (TS Seam)

**Policy:** The pi extension (TS) is a thin wrapper over the `scripts.pirml_run` (Python) bridge.

## Core Extension Logic (Bet A/B)
```typescript
import { ExtensionAPI, CustomEntry, ToolResult } from "@mariozechner/pi-coding-agent";
import { spawn } from "node:child_process";

export default function (pi: ExtensionAPI) {
  // Bet A: Command
  pi.registerCommand("pirml", {
    description: "Run PiRLM via Python bridge; record trace+artifacts",
    handler: async (args, ctx) => {
      // 1. Spawn python bridge (single execution owner)
      const p = spawn("python", ["-m", "scripts.pirml_run", "--prog", args.prog, ...]);
      
      // 2. Capture pirml_summary stdout row
      let stdout = "";
      p.stdout.on("data", (d) => stdout += d);
      
      // 3. Exit code gate
      const code = await new Promise<number>((r) => p.on("close", r));
      if (code) throw new Error("PIRML run failed (rc=" + code + ")");

      // 4. Append CustomEntry (Pointer Payload)
      const summary = JSON.parse(stdout);
      pi.appendEntry({
        type: "custom",
        customType: "pirml",
        data: {
          runId: summary.runId,
          trace: summary.trace,
          final: summary.final,
          artifactsDir: "art",
          roots: [summary.final, ".pirml/final.json"],
          runSha: summary.runSha,
          ts: summary.ts
        },
        parentId: ctx.session.activeEntryId // Branch safety
      });

      // 5. Append CustomMessage (Human Hint only)
      pi.appendEntry({
        type: "custom_message",
        message: {
          role: "custom",
          customType: "pirml",
          content: "PIRML " + summary.runId + " OK (" + summary.ms + "ms)",
          display: true,
          details: { runId: summary.runId }
        },
        parentId: ctx.session.activeEntryId
      });
    }
  });

  // Bet B: Tool (Optional)
  pi.registerTool({
    name: "pirml_run",
    description: "Run PiRLM and return pointers in details",
    execute: async (id, params, signal, onUpdate, ctx) => {
      // ... spawn python bridge ...
      // ... capture summary ...
      
      // ToolResult details carry branch-safe state
      return {
        content: [{ type: "text", text: "PIRML OK" }],
        details: { runId: summary.runId, trace: summary.trace, ... }
      } as ToolResult;
    }
  });
}
```

## Branch Lineage (parentId)
-   `parentId` MUST be set to the `activeEntryId`.
-   This ensures that if the operator uses `/tree` or `/fork`, the PiRLM run lineage is preserved and correctly rewound (X2, F7).
