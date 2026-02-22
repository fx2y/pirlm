import { UI } from "./ui";
import { runtime } from "./spawn";
import { buildCustomEntry, buildCustomMessage } from "./pointers";

export interface CommandContext {
  ui: UI;
  session: any;
  appendEntry: (entry: any) => Promise<void>;
  reload?: () => Promise<void>;
}

export async function handlePirmlCommand(
  args: string,
  ctx: CommandContext
): Promise<void> {
  const [cmd, task, ...rest] = (args ?? "").trim().split(/\s+/).filter(Boolean);

  if (!cmd) {
    ctx.ui.notify("usage: /pirml <run|doctor|reload-runtime> ...", "info");
    return;
  }

  if (cmd === "reload-runtime") {
    if (task || rest.length > 0) {
      ctx.ui.notify("usage: /pirml reload-runtime", "error");
      return;
    }
    if (!ctx.reload) {
      ctx.ui.notify("reload-runtime unsupported in this context", "error");
      return;
    }
    await ctx.reload();
    ctx.ui.notify("pirml: runtime reloaded", "info");
    return;
  }

  if (cmd === "doctor") {
    if (task || rest.length > 0) {
      ctx.ui.notify("usage: /pirml doctor", "error");
      return;
    }
    const doctor = await runtime.doctor();
    if (doctor.ok) {
      ctx.ui.notify("pirml doctor: OK", "info");
    } else {
      ctx.ui.notify(`pirml doctor: FAIL (rc=${doctor.code})`, "warn");
    }
    return;
  }

  if (cmd !== "run") {
    ctx.ui.notify("usage: /pirml <run|doctor|reload-runtime> ...", "error");
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
    
    const res = await runtime.spawn(task, outDir, artDir);
    
    // C2.T04: Append CustomEntry pointer row
    const entry = buildCustomEntry(
      res.runId,
      res.trace,
      res.final,
      res.artifacts,
      res.runSha,
      ts,
      (ctx.session as any)?.entry?.id ?? null
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
