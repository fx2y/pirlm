import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { handlePirmlCommand } from "./command";
import { createUIAdapter } from "./ui";
import { handlePirmlRunTool, PirmlRunParams } from "./tool_run";

export default function(pi: ExtensionAPI) {
  // C4.T00: Gate feature behind PIRML_ENABLE_HYBRID_TOOL
  const isHybridEnabled = process.env.PIRML_ENABLE_HYBRID_TOOL === "1";

  pi.registerCommand("pirml", {
    description: "run pirml",
    handler: async (args, ctx) => {
      const ui = createUIAdapter(ctx.ui);
      const appendEntry = async (entry: any) => {
        // Use pi.appendEntry if available, otherwise use ctx.session.appendEntry
        if ((pi as any).appendEntry) {
          return (pi as any).appendEntry(entry);
        } else if (ctx.session && (ctx.session as any).appendEntry) {
          return (ctx.session as any).appendEntry(entry);
        }
      };

      await handlePirmlCommand(args, {
        ui,
        session: ctx.session,
        appendEntry,
      });
    },
  });

  if (isHybridEnabled) {
    // C4.T01: Register pirml_run tool
    pi.registerTool({
      name: "pirml_run",
      label: "PIRML Run",
      description: "run python with pirml",
      parameters: PirmlRunParams as any,
      execute: handlePirmlRunTool as any,
    });

    // C4.T04: Add optional tool-call intercept guardrails
    if ((pi as any).on) {
      (pi as any).on("tool_call", async (e: any, ctx: any) => {
        if (e.toolName === "pirml_run") {
          const ok = await ctx.ui.confirm(
            "PIRML Run Verification",
            `PIRML tool call detected for task: ${e.input.task}. Proceed with execution?`
          );
          if (!ok) {
            return { block: true, reason: "user blocked pirml run" };
          }
        }
        return undefined;
      });
    }
  }
}
