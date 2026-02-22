import extension from "../.pi/extensions/pirml/index";
import { evaluateToolCallPolicy } from "../.pi/extensions/pirml/policy_call";
import { applyToolResultPolicy } from "../.pi/extensions/pirml/policy_result";
import { runtime } from "../.pi/extensions/pirml/spawn";

type CommandHandler = (args: string, ctx: any) => Promise<void>;
type ToolHandler = (event: any, ctx: any) => Promise<any>;

function buildExtensionHarness(): {
  commands: Record<string, CommandHandler>;
  handlers: Record<string, ToolHandler>;
} {
  const commands: Record<string, CommandHandler> = {};
  const handlers: Record<string, ToolHandler> = {};
  extension({
    registerCommand(name: string, config: { handler: CommandHandler }) {
      commands[name] = config.handler;
    },
    registerTool() {},
    on(event: string, handler: ToolHandler) {
      handlers[event] = handler;
    },
  } as any);
  return { commands, handlers };
}

function test_block_dangerous_bash(): void {
  const decision = evaluateToolCallPolicy({ toolName: "bash", input: { command: "rm -rf /" } });
  if (decision.action !== "block") throw new Error("dangerous root bash should block");
}

function test_block_protected_write(): void {
  const decision = evaluateToolCallPolicy({ toolName: "write", input: { path: ".env" } });
  if (decision.action !== "block") throw new Error("protected write should block");
}

function test_confirm_high_blast_radius(): void {
  const decision = evaluateToolCallPolicy({ toolName: "bash", input: { command: "rm -rf ./tmp/work" } });
  if (decision.action !== "confirm") throw new Error("high blast radius bash should require confirm");
}

async function test_tool_call_policy_block(): Promise<void> {
  const { handlers } = buildExtensionHarness();
  const policy = handlers["tool_call"];
  if (!policy) throw new Error("tool_call handler not registered");
  const result = await policy({ toolName: "curl", input: { url: "https://example.com" } }, {});
  if (!result?.block) throw new Error("unknown tool must be blocked by allowlist");
}

function test_truncate_large_result(): void {
  const huge = "X".repeat(9000);
  const patch = applyToolResultPolicy({ result: { content: [{ type: "text", text: huge }] } });
  if (!patch?.result?.content?.[0]?.text.includes("truncated")) {
    throw new Error("expected truncation patch");
  }
  if (patch.result.content[0].text.length > 120) {
    throw new Error("truncation message exceeded cap");
  }
}

function test_no_payload_in_custom_message(): void {
  const secret = "token=topsecret";
  const patch = applyToolResultPolicy({
    result: { content: [{ type: "text", text: `dump:${secret}` }], details: { artifacts: "art/run-1" } },
  });
  if (!patch) throw new Error("expected redaction patch");
  const text = patch.result.content[0].text;
  if (text.includes(secret)) throw new Error("redaction leaked payload into context text");
}

function test_result_payload_redaction_fail_closed(): void {
  const cyc: any = {};
  cyc.self = cyc;
  const patch = applyToolResultPolicy({ result: cyc });
  if (!patch) throw new Error("cyclic payload must fail-closed");
  if (!patch.result.content[0].text.includes("redacted")) {
    throw new Error("expected redacted fallback");
  }
}

async function test_reload_runtime_command_registered(): Promise<void> {
  const { commands } = buildExtensionHarness();
  const cmd = commands["pirml"];
  if (!cmd) throw new Error("pirml command not registered");
  let reloaded = false;
  const notices: string[] = [];
  await cmd("reload-runtime", {
    ui: {
      notify(msg: string) {
        notices.push(msg);
      },
      setStatus() {},
      clearStatus() {},
    },
    session: {},
    reload: async () => {
      reloaded = true;
    },
  });
  if (!reloaded) throw new Error("reload-runtime did not invoke ctx.reload");
  if (!notices.some((msg) => msg.includes("runtime reloaded"))) {
    throw new Error("reload-runtime success notice missing");
  }
}

async function test_doctor_command_routed(): Promise<void> {
  const { commands } = buildExtensionHarness();
  const cmd = commands["pirml"];
  if (!cmd) throw new Error("pirml command not registered");
  const notices: string[] = [];
  const originalDoctor = runtime.doctor;
  runtime.doctor = async () => ({ ok: true, code: 0, stdout: "", stderr: "" });
  try {
    await cmd("doctor", {
      ui: {
        notify(msg: string) {
          notices.push(msg);
        },
        setStatus() {},
        clearStatus() {},
      },
      session: {},
      reload: async () => {},
    });
  } finally {
    runtime.doctor = originalDoctor;
  }
  if (!notices.some((msg) => msg.includes("doctor: OK"))) {
    throw new Error("doctor command did not route to runtime doctor");
  }
}

async function test_reload_runtime_unknown_command_fails(): Promise<void> {
  const { commands } = buildExtensionHarness();
  const cmd = commands["pirml"];
  if (!cmd) throw new Error("pirml command not registered");
  let reloaded = false;
  const notices: string[] = [];
  await cmd("reload-runtime now", {
    ui: {
      notify(msg: string) {
        notices.push(msg);
      },
      setStatus() {},
      clearStatus() {},
    },
    session: {},
    reload: async () => {
      reloaded = true;
    },
  });
  if (reloaded) throw new Error("invalid reload-runtime invocation should not reload");
  if (!notices.some((msg) => msg.includes("usage: /pirml reload-runtime"))) {
    throw new Error("invalid reload-runtime usage should be reported");
  }
}

async function runTest(): Promise<void> {
  test_block_dangerous_bash();
  test_block_protected_write();
  test_confirm_high_blast_radius();
  await test_tool_call_policy_block();
  test_truncate_large_result();
  test_no_payload_in_custom_message();
  test_result_payload_redaction_fail_closed();
  await test_reload_runtime_command_registered();
  await test_doctor_command_routed();
  await test_reload_runtime_unknown_command_fails();
}

runTest().catch((err) => {
  console.error("TEST FAILED:", err);
  process.exit(1);
});
