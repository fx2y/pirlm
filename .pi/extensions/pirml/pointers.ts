export interface PointerRow {
  runId: string;
  trace: string;
  final: string;
  artifactsDir: string;
  projection: string;
  hash: string;
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
  hash: string,
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
      projection: ".pirml",
      hash,
      ts,
    },
    parentId,
  };
}

export function buildCustomMessage(
  runId: string,
  ok: boolean,
  summary?: string
): CustomMessage {
  const status = ok ? "OK" : "FAIL";
  const content = `PIRML ${runId} ${status}`;
  // Summary is optional one-liner
  return {
    type: "custom_message",
    message: {
      role: "custom",
      customType: "pirml",
      content: summary ? `${content}: ${summary}` : content,
      display: true,
      details: { runId },
    },
  };
}
