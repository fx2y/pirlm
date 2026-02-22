export interface EvalTaskPointerPayload {
  suite: string;
  task_id: string;
  run_id: string;
  trace_ptr: string;
  artifact_ids: string[];
  report_ptr: string;
  fail_tag: string;
}

export interface EvalTaskCustomEntry {
  type: "custom";
  customType: "pirml.eval_task";
  data: EvalTaskPointerPayload;
  parentId: string | null;
}

export interface EvalTaskCustomMessage {
  type: "custom_message";
  message: {
    role: "custom";
    customType: "pirml.eval_task";
    content: string;
    display: boolean;
    details: { suite: string; task_id: string; run_id: string };
  };
}

export function buildEvalTaskCustomEntry(
  payload: EvalTaskPointerPayload,
  parentId: string | null = null
): EvalTaskCustomEntry {
  return {
    type: "custom",
    customType: "pirml.eval_task",
    data: {
      ...payload,
      artifact_ids: [...payload.artifact_ids].sort(),
    },
    parentId,
  };
}

export function buildEvalTaskCustomMessage(
  payload: EvalTaskPointerPayload,
  summary?: string
): EvalTaskCustomMessage {
  const base = `EVAL ${payload.suite}/${payload.task_id} ${payload.fail_tag || "OK"}`;
  const oneLine = (summary ?? "").replace(/\s+/g, " ").trim();
  const budget = Math.max(0, 120 - base.length - 2);
  const capped = oneLine.slice(0, budget);
  return {
    type: "custom_message",
    message: {
      role: "custom",
      customType: "pirml.eval_task",
      content: capped ? `${base}: ${capped}` : base.slice(0, 120),
      display: true,
      details: {
        suite: payload.suite,
        task_id: payload.task_id,
        run_id: payload.run_id,
      },
    },
  };
}

export function validateEvalTaskPointerPayload(
  payload: EvalTaskPointerPayload,
  deps: {
    pathExists: (path: string) => boolean;
    artifactExists: (id: string) => boolean;
  }
): string[] {
  const errs: string[] = [];
  if (!deps.pathExists(payload.trace_ptr)) errs.push(`missing trace_ptr:${payload.trace_ptr}`);
  if (!deps.pathExists(payload.report_ptr)) errs.push(`missing report_ptr:${payload.report_ptr}`);
  for (const aid of payload.artifact_ids) {
    if (!deps.artifactExists(aid)) errs.push(`missing artifact_id:${aid}`);
  }
  return errs;
}
