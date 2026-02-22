import { handlePirmlCommand } from "../.pi/extensions/pirml/command";
import { createUIAdapter } from "../.pi/extensions/pirml/ui";
import { runtime } from "../.pi/extensions/pirml/spawn";

// Manual mock for spawn with dynamic behavior
let mockResult: any = {
  ok: true,
  runId: "r123",
  trace: "trace.ndjson",
  final: "final.json",
  artifacts: "art",
  runSha: "abc",
  summary: "Mocked OK",
};

runtime.spawn = async (prog: string, outDir: string, artDir: string) => {
  const runId = outDir.split("/").pop() || "r123";
  return { ...mockResult, runId, trace: `${outDir}/trace.ndjson`, final: `${outDir}/final.json` };
};

async function runTest() {
  console.log("Starting C2 Extension Contract Test (Manual Mocks)...");

  let notifyCount = 0;
  const mockUI = {
    notify: (msg: string, type: string) => {
      console.log(`[UI NOTIFY] ${type}: ${msg}`);
      notifyCount++;
    },
    setStatus: (id: string, label: string) => console.log(`[UI STATUS] ${id}: ${label}`),
    clearStatus: (id: string) => console.log(`[UI CLEAR] ${id}`),
  };

  const appendedEntries: any[] = [];
  const mockCtx = {
    ui: createUIAdapter(mockUI),
    session: { entry: { id: "e123" } },
    appendEntry: async (entry: any) => {
      console.log(`[APPEND ENTRY] ${JSON.stringify(entry, null, 2)}`);
      appendedEntries.push(entry);
    },
  };

  // 1. Test help
  console.log("\n--- TEST: HELP ---");
  await handlePirmlCommand("", mockCtx);
  if (notifyCount === 0) throw new Error("Help should notify");

  // 2. Test run
  console.log("\n--- TEST: RUN ---");
  notifyCount = 0;
  mockResult = {
    ok: true,
    artifacts: "art",
    summary: "Mocked OK",
  };
  await handlePirmlCommand("run tests/prog_ok.py", mockCtx);

  if (appendedEntries.length < 2) {
    throw new Error(`Expected at least 2 entries, got ${appendedEntries.length}`);
  }

  const pointerEntry = appendedEntries[0];
  if (pointerEntry.type !== "custom" || pointerEntry.customType !== "pirml") {
    throw new Error(`Invalid pointer entry type: ${pointerEntry.type}`);
  }
  if (!pointerEntry.data.runId.startsWith("r")) {
    throw new Error(`Invalid runId: ${pointerEntry.data.runId}`);
  }
  if (pointerEntry.parentId !== "e123") {
    throw new Error(`Expected parentId=e123, got ${pointerEntry.parentId}`);
  }
  if (!Array.isArray(pointerEntry.data.roots) || pointerEntry.data.roots.length < 2) {
    throw new Error("Pointer roots missing");
  }
  console.log("PASS: PointerEntry validated");

  const messageEntry = appendedEntries[1];
  if (messageEntry.type !== "custom_message" || messageEntry.message.customType !== "pirml") {
    throw new Error(`Invalid message entry type: ${messageEntry.type}`);
  }
  if (!messageEntry.message.content.includes("OK")) {
    throw new Error(`Invalid message content: ${messageEntry.message.content}`);
  }
  console.log("PASS: MessageEntry validated");

  console.log("\n--- TEST: FAILED RUN ---");
  mockResult = {
    ok: false,
    artifacts: "art",
    error: { type: "runtime", msg: "Simulated Crash" },
    summary: "Mocked FAIL",
  };
  
  appendedEntries.length = 0;
  await handlePirmlCommand("run tests/prog_fail.py", mockCtx);
  
  if (appendedEntries.length < 2) {
    throw new Error(`Expected at least 2 entries for failed run, got ${appendedEntries.length}`);
  }
  if (!appendedEntries[1].message.content.includes("FAIL")) {
    throw new Error(`Expected FAIL in message, got: ${appendedEntries[1].message.content}`);
  }
  console.log("PASS: Failed run correctly reported");

  console.log("\nALL C2 EXTENSION CONTRACT TESTS PASSED");
}

runTest().catch(err => {
  console.error("TEST FAILED:", err);
  process.exit(1);
});
