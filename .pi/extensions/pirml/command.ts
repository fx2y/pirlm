import { UI } from "./ui";
import { runtime } from "./spawn";
import { buildCustomEntry, buildCustomMessage } from "./pointers";

export interface CommandContext {
  ui: UI;
  session: any;
  appendEntry: (entry: any) => Promise<void>;
}

export async function handlePirmlCommand(
  args: string,
  ctx: CommandContext
): Promise<void> {
  const [cmd, task, ...rest] = (args ?? "").trim().split(/\s+/);
  
  if (!cmd || cmd !== "run") {
    ctx.ui.notify("usage: /pirml run <task>", "info");
    return;
  }

  if (!task) {
    ctx.ui.notify("missing task for /pirml run", "error");
    return;
  }

  ctx.ui.setStatus("pirml", "running…");
  ctx.ui.notify(`pirml: starting ${task}`, "info");

  try {
    const ts = Date.now();
    const runId = `r${ts}`;
    const outDir = `out/${runId}`;
    const artDir = "art";
    
    // In a real environment, we'd probably have a way to generate a script
    // Or we expect the user to provide a path. Let's assume task is a path or name.
    const res = await runtime.spawn(task, outDir, artDir);
    
    // C2.T04: Append CustomEntry pointer row
    const entry = buildCustomEntry(
      res.runId,
      res.trace,
      res.final,
      res.artifacts,
      "", // hash would be read from final.json
      ts,
      null // parentId from session
    );
    await ctx.appendEntry(entry);

    // C2.T05: Optional CustomMessage one-liner
    const msg = buildCustomMessage(res.runId, res.ok, res.summary);
    await ctx.appendEntry(msg);

    if (res.ok) {
      ctx.ui.notify(`pirml: ${res.runId} completed`, "info");
    } else {
      ctx.ui.notify(`pirml: ${res.runId} failed: ${res.error?.msg}`, "error");
    }

  } catch (err: any) {
    ctx.ui.notify(`pirml: exception: ${err.message}`, "error");
  } finally {
    ctx.ui.clearStatus("pirml");
  }
}
