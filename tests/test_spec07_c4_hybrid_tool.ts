import { handlePirmlRunTool } from "../.pi/extensions/pirml/tool_run";
import { runtime } from "../.pi/extensions/pirml/spawn";
import extension from "../.pi/extensions/pirml/index";

// Manual mock for spawn with dynamic behavior
let mockResult: any = {
  ok: true,
  runId: "r123",
  trace: "trace.ndjson",
  final: "final.json",
  artifacts: "art",
  summary: "Mocked OK",
};

runtime.spawn = async (prog: string, outDir: string, artDir: string) => {
  const runId = outDir.split("/").pop() || "r123";
  return { ...mockResult, runId, trace: `${outDir}/trace.ndjson`, final: `${outDir}/final.json` };
};

async function runTest() {
  console.log("Starting C4 Hybrid Tool Test...");

  // 1. Test feature gating
  console.log("\n--- TEST: GATING (OFF) ---");
  process.env.PIRML_ENABLE_HYBRID_TOOL = "0";
  let toolRegistered = false;
  const mockPiOff = {
    registerCommand: () => {},
    registerTool: () => { toolRegistered = true; },
    on: () => {},
  };
  extension(mockPiOff as any);
  if (toolRegistered) throw new Error("Tool should not be registered when flag is off");
  console.log("PASS: Feature gating (OFF) verified");

  console.log("\n--- TEST: GATING (ON) ---");
  process.env.PIRML_ENABLE_HYBRID_TOOL = "1";
  toolRegistered = false;
  let onCallRegistered = false;
  const mockPiOn = {
    registerCommand: () => {},
    registerTool: (tool: any) => {
      if (tool.name === "pirml_run") toolRegistered = true;
    },
    on: (event: string) => {
      if (event === "tool_call") onCallRegistered = true;
    },
  };
  extension(mockPiOn as any);
  if (!toolRegistered) throw new Error("Tool should be registered when flag is on");
  if (!onCallRegistered) throw new Error("tool_call intercept should be registered");
  console.log("PASS: Feature gating (ON) verified");

  // 2. Test tool execution
  console.log("\n--- TEST: TOOL EXECUTION ---");
  const params = { task: "tests/prog_ok.py" };
  const result: any = await handlePirmlRunTool("call1", params, {} as any, () => {}, {});

  if (!result.details || !result.details.runId) {
    throw new Error("Tool result should contain runId in details");
  }
  if (!result.details.ok) {
    throw new Error("Tool result should be OK");
  }
  if (!result.content[0].text.includes("completed successfully")) {
    throw new Error(`Unexpected tool result content: ${result.content[0].text}`);
  }
  console.log("PASS: Tool execution verified");

  // 3. Test tool failure
  console.log("\n--- TEST: TOOL FAILURE ---");
  mockResult = {
    ok: false,
    artifacts: "art",
    error: { type: "runtime", msg: "Simulated Crash" },
    summary: "Mocked FAIL",
  };

  const failResult: any = await handlePirmlRunTool("call2", params, {} as any, () => {}, {});
  if (failResult.details.ok !== false) {
    throw new Error("Tool result should NOT be OK");
  }
  if (!failResult.content[0].text.includes("failed: Simulated Crash")) {
    throw new Error(`Unexpected tool failure content: ${failResult.content[0].text}`);
  }
  console.log("PASS: Tool failure verified");

  console.log("\nALL C4 HYBRID TOOL TESTS PASSED");
}

runTest().catch(err => {
  console.error("TEST FAILED:", err);
  process.exit(1);
});
