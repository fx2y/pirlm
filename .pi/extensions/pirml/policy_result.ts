export const MAX_RESULT_BYTES = 8000;
const MAX_HINT_CHARS = 120;

export interface ToolResultEvent {
  result: unknown;
}

export interface ToolResultPatch {
  result: {
    content: Array<{ type: "text"; text: string }>;
    details?: Record<string, unknown>;
  };
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => canonicalize(item));
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      out[key] = canonicalize((value as Record<string, unknown>)[key]);
    }
    return out;
  }
  return value;
}

function hasLikelySensitivePayload(text: string): boolean {
  return /BEGIN [A-Z ]+ KEY|password|secret|token|ssh-rsa/i.test(text);
}

function detectPointerHint(result: Record<string, unknown>): string {
  const details = result.details;
  if (!details || typeof details !== "object") return "see artifacts";
  const data = details as Record<string, unknown>;
  const paths = [data.artifacts, data.trace, data.final, data.trace_ptr, data.report_ptr]
    .map((value) => (typeof value === "string" ? value.trim() : ""))
    .filter((value) => value.length > 0);
  if (paths.length === 0) return "see artifacts";
  return `see ${paths[0]}`;
}

function makeHint(prefix: string, detail: string): string {
  const raw = `${prefix}: ${detail}`.replace(/\s+/g, " ").trim();
  return raw.slice(0, MAX_HINT_CHARS);
}

export function applyToolResultPolicy(event: ToolResultEvent): ToolResultPatch | undefined {
  try {
    const normalized = canonicalize(event.result);
    const text = JSON.stringify(normalized);
    if (text.length <= MAX_RESULT_BYTES && !hasLikelySensitivePayload(text)) {
      return undefined;
    }
    const resultObj = normalized && typeof normalized === "object" ? (normalized as Record<string, unknown>) : {};
    const hint = makeHint("(truncated/redacted)", detectPointerHint(resultObj));
    const details = resultObj.details;
    const reducedDetails = details && typeof details === "object"
      ? {
          ok: (details as Record<string, unknown>).ok,
          runId: (details as Record<string, unknown>).runId,
          fail_tag: (details as Record<string, unknown>).fail_tag,
        }
      : undefined;
    return {
      result: {
        content: [{ type: "text", text: hint }],
        details: reducedDetails,
      },
    };
  } catch {
    return {
      result: {
        content: [{ type: "text", text: "(redacted) see artifacts" }],
        details: { ok: false, error: { type: "validation", msg: "result redaction failed-closed", retryable: false } },
      },
    };
  }
}
