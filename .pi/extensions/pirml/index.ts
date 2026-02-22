import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { handlePirmlCommand } from "./command";
import { createUIAdapter } from "./ui";
import { handlePirmlRunTool, PirmlRunParams } from "./tool_run";
import { evaluateToolCallPolicy } from "./policy_call";
import { applyToolResultPolicy } from "./policy_result";

export default function(pi: ExtensionAPI) {
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
        reload: ctx.reload ? async () => { await ctx.reload(); } : undefined,
      });
    },
  });

  if (isHybridEnabled) {
    pi.registerTool({
      name: "pirml_run",
      label: "PIRML Run",
      description: "run python with pirml",
      parameters: PirmlRunParams as any,
      execute: handlePirmlRunTool as any,
    });
  }

  if ((pi as any).on) {
    (pi as any).on("tool_call", async (e: any, ctx: any) => {
      const decision = evaluateToolCallPolicy(e ?? {});
      if (decision.action === "block") {
        return { block: true, reason: decision.reason ?? "blocked_by_policy" };
      }
      if (decision.action === "confirm") {
        const ok = await ctx?.ui?.confirm?.(
          "PIRML policy confirm",
          decision.message ?? "Tool call requires confirmation."
        );
        if (!ok) {
          return { block: true, reason: decision.reason ?? "confirm_denied" };
        }
      }
      return undefined;
    });

    (pi as any).on("tool_result", async (e: any) => {
      const patch = applyToolResultPolicy({ result: e?.result });
      return patch;
    });
  }
}
