import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import {
  buildEvalTaskCustomEntry,
  buildEvalTaskCustomMessage,
  validateEvalTaskPointerPayload,
} from "../.pi/extensions/pirml/eval_pointers";

function samplePayload(tmp: string) {
  const trace = path.join(tmp, "runs", "golden50", "shard-00000.ndjson");
  const report = path.join(tmp, "report.json");
  fs.mkdirSync(path.dirname(trace), { recursive: true });
  fs.writeFileSync(trace, "{}\n", "utf8");
  fs.writeFileSync(report, "{}", "utf8");
  return {
    suite: "golden50",
    task_id: "q001",
    run_id: "golden50-s00000",
    trace_ptr: trace,
    artifact_ids: ["aid_b", "aid_a"],
    report_ptr: report,
    fail_tag: "",
  } as const;
}

function test_custom_payload_non_context(): void {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "pirml-c6-"));
  const payload = samplePayload(tmp);
  const entry = buildEvalTaskCustomEntry(payload, "parent-1");
  const msg = buildEvalTaskCustomMessage(payload, "ok one-line summary");
  if (entry.customType !== "pirml.eval_task") throw new Error("wrong customType");
  if (entry.parentId !== "parent-1") throw new Error("parentId mismatch");
  if (entry.data.artifact_ids.join(",") !== "aid_a,aid_b") throw new Error("artifact sort drift");
  const msgStr = JSON.stringify(msg.message);
  if (msgStr.includes(payload.trace_ptr) || msgStr.includes(payload.report_ptr) || msgStr.includes("artifact_ids")) {
    throw new Error("custom_message leaked pointer payload");
  }
}

function test_pointer_resolves(): void {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "pirml-c6-"));
  const payload = samplePayload(tmp);
  const errs = validateEvalTaskPointerPayload(payload, {
    pathExists: (p) => fs.existsSync(p),
    artifactExists: (id) => id === "aid_a" || id === "aid_b",
  });
  if (errs.length !== 0) throw new Error(`expected no errors, got ${errs.join(";")}`);
}

function test_payload_not_in_context(): void {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "pirml-c6-"));
  const payload = samplePayload(tmp);
  const msg = buildEvalTaskCustomMessage(payload, `${"x".repeat(400)}\n  multiline`);
  if (msg.message.content.includes("\n")) throw new Error("message must be one-line");
  if (msg.message.content.length > 120) throw new Error("message unexpectedly large");
  const details = JSON.stringify(msg.message.details);
  if (details.includes(payload.trace_ptr) || details.includes(payload.report_ptr)) {
    throw new Error("details leaked heavy pointers");
  }
}

async function runTest(): Promise<void> {
  test_custom_payload_non_context();
  test_pointer_resolves();
  test_payload_not_in_context();
  console.log("Spec08 C6 tests passed.");
}

runTest().catch((err) => {
  console.error("TEST FAILED:", err);
  process.exit(1);
});
