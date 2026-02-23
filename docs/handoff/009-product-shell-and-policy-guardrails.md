# Spec-09: Product Shell & Policy Guardrails

## 0. Truth Authority (H20)
- **Source of Truth**: `spec-0/09-tasks.jsonl`. Prose/htn/shards are support only.
- **Done Law**: `C7` status flip requires same-merge sync of learnings+tasks+tutorial + post-edit proof bundle.

## 1. Product CLI & Fail-Closed Law (H11/T12)
- **Subcommand Router**: `pirml {doctor,install-pi-ext,uninstall-pi-ext,replay,tool}`.
- **Legacy Path**: `python -m pirml --prog X` remains for byte-path compatibility.
- **Fail-Closed Parse**: `strict_parse_args` patches `argparse` to emit typed JSON stderr + `rc2`.
  - **Example**: `python -m pirml replay tests/prog_ok.py trace.ndjson --timeout nope` -> `{"type":"config","msg":"...","retryable":false}`.
  - **Rule**: NO `usage:` dump leakage to stderr.

## 2. Tool Authoring (C3)
- **Scaffold**: `pirml tool init <id> --tools-dir <dir>` -> loader-compatible flat manifest.
- **Lint**: `pirml tool lint --tools-dir <dir>` -> detailed `ManifestError` list.
- **Pack**: `pirml tool pack --tools-dir <dir> --out <json>` -> canonical-JSON with `catalog_hash`.
- **Determinism**: Artifacts must be byte-stable for replay parity.

## 3. Runtime Policies (C5)
- **Seam**: `RuntimePolicySet` in `pirml.runtime.policy`.
- **Enforcement**: `execute_with_retry` + `enforce_payload_cap`.
- **Capabilities**:
  - `retry`: Only if `idempotent=true`.
  - `max_payload_bytes`: Truncates with metadata; boundary owns caps.
  - `timeouts`: Min(call, policy, global remaining).
- **Verifiable**: Policy failures map to typed `error` in `result` frames.

## 4. Extension Gates (C4)
- **Choke-point**: `.pi/extensions/pirml/{policy_call,policy_result}.ts`.
- **Logic**: All `tool_call`/`tool_result` interception lives here.
- **Safety**: Blocks/truncates/redacts before context packing.

## 5. Verification Harness (C6)
- **Smoke**: `scripts.spec09_tool_smoke` -> `init->lint->live->replay` e2e parity proof.
- **Chaos**: `scripts.spec09_eval_chaos` -> timeout/invalid/resume-integrity lanes.
- **Report**: `scripts.spec09_report_smoke` -> parser integrity + NDJSON seq checks.
- **Additivity**: `mise run spec09-*` helpers are additive; `ci`/`fast` byte contracts frozen.

## 6. Proof Bundle (Verification)
Verbatim execution of this sequence is the only path to finality:
```bash
mise run boot
python -m unittest discover -s tests -p 'test_spec09*.py' -q
npx tsx tests/test_spec09_c4_extension_policy.ts
python -m scripts.spec09_tool_smoke
python -m scripts.spec09_eval_chaos
python -m scripts.spec09_report_smoke
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
mise run fast
mise run ci
```

## 7. Operational Examples
- **Check Health**: `python -m pirml doctor` (typed NDJSON rows).
- **Install Extension**: `python -m pirml install-pi-ext --target project`.
- **Author Tool**: `pirml tool init demo.foo && pirml tool lint && pirml tool pack`.
- **Replay Parity**: `python -m pirml replay tests/prog_ok.py out/ci/trace.ndjson`.

## 8. Anti-Patterns
- **A0**: Editing CLI/Docs without rerunning `tests.test_spec09_c7_hardening_sync`.
- **A1**: Claiming done if any parser leaks `usage:` text (must be typed JSON).
- **A2**: Bypassing `scripts.pirml_run` for live execution (violates owner-path).
- **A3**: Mutating L0 tools `{echo,readfile,bash}` (registry is frozen).
