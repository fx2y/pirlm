import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { handlePirmlCommand } from "./command";
import { createUIAdapter } from "./ui";

export default function(pi: ExtensionAPI) {
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
}
