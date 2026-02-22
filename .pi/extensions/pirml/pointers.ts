export interface PointerRow {
  runId: string;
  trace: string;
  final: string;
  artifactsDir: string;
  roots: string[];
  runSha: string;
  ts: number;
}

export interface CustomEntry {
  type: "custom";
  customType: "pirml";
  data: PointerRow;
  parentId: string | null;
}

export interface CustomMessage {
  type: "custom_message";
  message: {
    role: "custom";
    customType: "pirml";
    content: string;
    display: boolean;
    details: { runId: string };
  };
}

export function buildCustomEntry(
  runId: string,
  trace: string,
  final: string,
  artifacts: string,
  runSha: string,
  ts: number,
  parentId: string | null = null
): CustomEntry {
  return {
    type: "custom",
    customType: "pirml",
    data: {
      runId,
      trace,
      final,
      artifactsDir: artifacts,
      roots: [outDirFromTrace(trace), artifacts],
      runSha,
      ts,
    },
    parentId,
  };
}

function outDirFromTrace(trace: string): string {
  const idx = trace.lastIndexOf("/trace.ndjson");
  return idx > 0 ? trace.slice(0, idx) : ".";
}

export function buildCustomMessage(
  runId: string,
  ok: boolean,
  summary?: string
): CustomMessage {
  const status = ok ? "OK" : "FAIL";
  const content = `PIRML ${runId} ${status}`;
  const oneLine = summary ? summary.replace(/\s+/g, " ").trim() : "";
  const capped = oneLine.slice(0, 120);
  // Summary is optional one-liner
  return {
    type: "custom_message",
    message: {
      role: "custom",
      customType: "pirml",
      content: capped ? `${content}: ${capped}` : content,
      display: true,
      details: { runId },
    },
  };
}
