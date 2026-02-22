const ALLOWED_TOOL_NAMES = new Set(["bash", "read", "readfile", "write", "edit", "pirml_run", "pirml_doctor"]);

const ROOT_DANGER = /\brm\s+-rf\s+\/(?:\s|$)/;
const HIGH_BLAST = /\brm\s+-rf\b|:?\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\};:|\bmkfs\b|\bdd\s+if=.*\bof=\/dev\//;
const PROTECTED_PATH = /(^|\/)\.env($|\.)|(^|\/)\.pi(\/|$)|(^|\/)\.ssh(\/|$)|^~\/\.ssh(\/|$)/;

export interface ToolCallEvent {
  toolName?: unknown;
  input?: Record<string, unknown>;
}

export interface ToolCallPolicyDecision {
  action: "allow" | "block" | "confirm";
  reason?: string;
  message?: string;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function isProtectedWrite(toolName: string, input: Record<string, unknown> | undefined): boolean {
  if (!(toolName === "write" || toolName === "edit")) return false;
  const path = asString(input?.path);
  if (!path) return false;
  return PROTECTED_PATH.test(path);
}

export function evaluateToolCallPolicy(event: ToolCallEvent): ToolCallPolicyDecision {
  const toolName = asString(event.toolName).trim();
  if (!toolName) {
    return { action: "block", reason: "invalid_tool_name" };
  }
  if (!ALLOWED_TOOL_NAMES.has(toolName)) {
    return { action: "block", reason: "tool_not_allowed" };
  }

  if (isProtectedWrite(toolName, event.input)) {
    return { action: "block", reason: "protected_path" };
  }

  if (toolName === "bash") {
    const command = asString(event.input?.command);
    if (ROOT_DANGER.test(command)) {
      return { action: "block", reason: "dangerous_bash_root_delete" };
    }
    if (HIGH_BLAST.test(command)) {
      return {
        action: "confirm",
        reason: "high_blast_radius",
        message: "High blast-radius bash command detected. Confirm execution?",
      };
    }
  }

  return { action: "allow" };
}
