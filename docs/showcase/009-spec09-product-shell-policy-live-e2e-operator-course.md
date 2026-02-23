# 009: Spec-09 Product Shell+Policy Live E2E Operator Course

Date baseline: `2026-02-23`.
Mode: ultra-opinionated, ultra-terse, proof-first, artifact-first.

## 0) Doctrine (break one => stop)
1. Status truth: `spec-0/09-tasks.jsonl` (`C0..C7=done` as-of `2026-02-22`).
2. `L0` frozen: runtime tools stay `{echo,readfile,bash}`.
3. One owner path: `scripts.pirml_run -> pirml.ux.runtime_bridge -> python -m pirml`.
4. Protocol law fixed: `op in {call,result,final,custom}`; one `final` last.
5. Boundary law fixed: `final.json` root stays `{ok,results,output?,meta?}`.
6. Parse law: CLI parse failures are typed stderr JSON, `rc=2`, no `usage:` leakage.
7. Fail-closed: unknown cmd/flag/schema/path/policy => typed `{type,msg,retryable}`.
8. Determinism: canonical JSON, strict ordering/counters, no wall-clock scoring semantics.
9. Replay outranks live: parity drift invalidates live claims.
10. Helper tasks additive-only; release authority is still `mise run ci`.
11. Gate order immutable: `fmt>lint>types>unit>proto>trace>schemas>replay`.
12. Done claim requires post-edit proof rerun, not pre-edit green.

## 1) Reality Snapshot (current implementation)
1. Product CLI (live): `doctor`, `install-pi-ext`, `uninstall-pi-ext`, `replay`, `tool init|lint|pack`.
2. Parse-fail lanes verified for legacy + product + tool subparsers (`I22`,`I23`).
3. `pirml tool lint` emits structured validation payload on failure (`code,msg,path` rows).
4. `pirml tool lint` bootstrap lane supports fresh `tool init` catalogs (single-tool onboarding).
5. `pirml tool pack` writes canonical JSON with `catalog_hash`.
6. Extension policy chokepoint is shipped and tested via TS suite (`tool_call`, `tool_result`, command routing).
7. Runtime policy adapters shipped: artifact-write guard, idempotent-gated retry, payload cap.
8. Spec09 smoke harness shipped: `tool init -> lint -> live -> replay`, parity checked.
9. Chaos/report smoke shipped: typed timeout/invalid/replay_mismatch/resume lanes + report integrity lane.
10. Additive tasks shipped: `spec09-golden`, `spec09-chaos`, `spec09-report`.

## 2) 12-Min Canonical Value Proof (copy/paste)
```bash
set -euo pipefail
BASE=out/showcase/009/demo
HOME_SANDBOX="$BASE/home"
TOOLS="$BASE/tools"
rm -rf "$BASE"
mkdir -p "$BASE" "$HOME_SANDBOX" "$TOOLS"

# 0) authority preflight
mise run fast
mise run ci

# 1) parse-law smoke (must be typed config rc2; no usage leak)
ERR="$BASE/parse.err"
if python -m pirml replay tests/prog_ok.py out/ci/trace.ndjson --timeout nope 2>"$ERR"; then exit 1; fi
rg -q '"type": "config"' "$ERR"
! rg -q '^usage:' "$ERR"

# 2) doctor + safe install/uninstall demo (sandboxed home)
python -m pirml doctor --home "$HOME_SANDBOX" > "$BASE/doctor.ndjson" || true
python -m pirml install-pi-ext --target global --home "$HOME_SANDBOX" --project-root "$PWD" > "$BASE/install-global.json"
python -m pirml uninstall-pi-ext --target global --home "$HOME_SANDBOX" --project-root "$PWD" > "$BASE/uninstall-global.json"

# 3) authoring flow
python -m pirml tool init demo.spec09 --tools-dir "$TOOLS"
python -m pirml tool lint --tools-dir "$TOOLS"
python -m pirml tool pack --tools-dir "$TOOLS" --out "$BASE/toolpack.json"

# 4) shipped e2e harnesses
python -m scripts.spec09_tool_smoke > "$BASE/smoke.json"
python -m scripts.spec09_eval_chaos > "$BASE/chaos.json"
python -m scripts.spec09_report_smoke > "$BASE/report-smoke.json"

# 5) additive helper tasks
mise run spec09-golden
mise run spec09-chaos
mise run spec09-report

# 6) parity + artifacts + cycle suites
python -m scripts.replay_check > "$BASE/replay-check.log"
python -m scripts.artifact_rebuild --check
python -m unittest discover -s tests -p 'test_spec09*.py' -q
npx tsx tests/test_spec09_c4_extension_policy.ts
```

Pass bar:
1. `toolpack.json` exists with `catalog_hash`.
2. `smoke.json` shows `ok:true` and live/replay final hashes equal.
3. `chaos.json` contains timeout/invalid/replay_mismatch/resume evidence.
4. `report-smoke.json` contains `ok:true` + deterministic KPI tuple.
5. `replay_check`, `artifact_rebuild --check`, spec09 suites, TS suite all green.
6. `fast` and `ci` already green in same run.

## 3) Live Integration Lanes
### Lane A: Safe operator install/uninstall (no real home mutation)
```bash
BASE=out/showcase/009/laneA
HOME_SANDBOX="$BASE/home"
PROOT="$BASE/project"
mkdir -p "$BASE" "$HOME_SANDBOX" "$PROOT"
python -m pirml doctor --home "$HOME_SANDBOX" > "$BASE/doctor.ndjson" || true
python -m pirml install-pi-ext --target global --home "$HOME_SANDBOX" --project-root "$PWD" > "$BASE/install-global.json"
python -m pirml uninstall-pi-ext --target global --home "$HOME_SANDBOX" --project-root "$PWD" > "$BASE/uninstall-global.json"
python -m pirml install-pi-ext --target project --source-dir .pi/extensions/pirml --project-root "$PROOT" --home "$HOME_SANDBOX" > "$BASE/install-project.json"
python -m pirml uninstall-pi-ext --target project --project-root "$PROOT" --home "$HOME_SANDBOX" > "$BASE/uninstall-project.json"
```

### Lane B: Tool authoring product flow (real value lane)
```bash
BASE=out/showcase/009/laneB
TOOLS="$BASE/tools"
rm -rf "$BASE"; mkdir -p "$TOOLS"
python -m pirml tool init acme.lookup --tools-dir "$TOOLS"
python -m pirml tool lint --tools-dir "$TOOLS"
python -m pirml tool pack --tools-dir "$TOOLS" --out "$BASE/toolpack.json"
python - <<'PY'
import json; from pathlib import Path
d=json.loads(Path("out/showcase/009/laneB/toolpack.json").read_text())
print({"catalog_hash":d["catalog_hash"],"docs":len(d["docs"]),"rankings":len(d["rankings"])})
PY
```

### Lane C: Runtime/replay trust lane (owner-path + parity)
```bash
python -m scripts.spec09_tool_smoke
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
```

### Lane D: Extension policy lane (live integration tests)
```bash
npx tsx tests/test_spec09_c4_extension_policy.ts
python -m unittest -q tests.test_spec09_c7_hardening_sync
```

### Lane E: Authority close lane (release claim bar)
```bash
mise run fast
mise run ci
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
python -m unittest discover -s tests -p 'test_spec09*.py' -q
npx tsx tests/test_spec09_c4_extension_policy.ts
```

## 4) Walkthrough Tracks
### Product Owner (10m, value + constraint honesty)
```bash
python -m pirml --help
python -m pirml doctor || true
python -m scripts.spec09_tool_smoke
python -m scripts.spec09_eval_chaos
python -m scripts.spec09_report_smoke
mise run ci
```
Say: usability grew (doctor/install/tool/replay) without runtime/protocol drift.
Do not say: new runtime tools, expanded final root, silent optional-lane enablement.

### QA (invariants first, demos second)
```bash
python -m unittest -q tests.test_tool_surface_freeze tests.test_spec09_c0_reconcile tests.test_spec09_c0_declared_failures
python -m unittest -q tests.test_spec09_c1_product_shell
python -m unittest -q tests.test_spec09_c2_manifest_contract tests.test_toolsearch_lint
python -m unittest -q tests.test_spec09_c3_tool_cli
npx tsx tests/test_spec09_c4_extension_policy.ts
python -m unittest -q tests.test_spec09_c5_runtime_policy tests.test_compile_verify tests.test_replay
python -m unittest -q tests.test_spec09_c6_harness tests.test_spec09_c6_chaos tests.test_spec09_c6_gate_contract
python -m unittest -q tests.test_spec09_c7_hardening_sync
```

### FDE (incident loop, no guesswork)
```bash
python -m pirml replay tests/prog_ok.py out/ci/trace.ndjson --timeout nope ; echo rc=$?
python -m pirml tool init ; echo rc=$?
python -m scripts.spec09_tool_smoke
python -m scripts.spec09_eval_chaos
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
```
Priority on incident:
1. typed stderr envelope,
2. replay parity,
3. artifact parity,
4. gate-contract tests,
5. full authority lane.

## 5) Scenario Bank (dense drills)
S01 fast reject:
```bash
mise run fast
```

S02 authority gate:
```bash
mise run ci
```

S03 CLI surface:
```bash
python -m pirml --help
python -m pirml tool --help
```

S04 product command help:
```bash
python -m pirml doctor --help
python -m pirml install-pi-ext --help
python -m pirml uninstall-pi-ext --help
python -m pirml replay --help
python -m pirml tool init --help
python -m pirml tool lint --help
python -m pirml tool pack --help
```

S05 parse fail (`replay --timeout nope`):
```bash
python -m pirml replay tests/prog_ok.py out/ci/trace.ndjson --timeout nope ; echo rc=$?
```

S06 parse fail (`doctor --home` missing value):
```bash
python -m pirml doctor --home ; echo rc=$?
```

S07 parse fail (`install-pi-ext --target` missing value):
```bash
python -m pirml install-pi-ext --target ; echo rc=$?
```

S08 parse fail (`uninstall-pi-ext --target` missing value):
```bash
python -m pirml uninstall-pi-ext --target ; echo rc=$?
```

S09 parse fail (legacy scalar):
```bash
python -m pirml --timeout nope --prog tests/prog_ok.py ; echo rc=$?
```

S10 parse fail (`tool init` missing name):
```bash
python -m pirml tool init ; echo rc=$?
```

S11 parse fail (`tool lint --tools-dir` missing value):
```bash
python -m pirml tool lint --tools-dir ; echo rc=$?
```

S12 parse fail (`tool pack --out` missing value):
```bash
python -m pirml tool pack --out ; echo rc=$?
```

S13 no-usage-leak assertion:
```bash
ERR=$(mktemp)
python -m pirml tool init 2>"$ERR" || true
rg -q '"type": "config"' "$ERR"
! rg -q '^usage:' "$ERR"
```

S14 doctor NDJSON lane:
```bash
python -m pirml doctor || true
```

S15 doctor deterministic sandbox:
```bash
BASE=out/showcase/009/s15; HOME_SANDBOX="$BASE/home"; mkdir -p "$BASE" "$HOME_SANDBOX"
python -m pirml doctor --home "$HOME_SANDBOX" > "$BASE/a.ndjson" || true
python -m pirml doctor --home "$HOME_SANDBOX" > "$BASE/b.ndjson" || true
cmp "$BASE/a.ndjson" "$BASE/b.ndjson" && echo OK
```

S16 install/uninstall global idempotent (sandboxed):
```bash
BASE=out/showcase/009/s16; HOME_SANDBOX="$BASE/home"; mkdir -p "$BASE" "$HOME_SANDBOX"
python -m pirml install-pi-ext --target global --home "$HOME_SANDBOX" --project-root "$PWD"
python -m pirml install-pi-ext --target global --home "$HOME_SANDBOX" --project-root "$PWD"
python -m pirml uninstall-pi-ext --target global --home "$HOME_SANDBOX" --project-root "$PWD"
python -m pirml uninstall-pi-ext --target global --home "$HOME_SANDBOX" --project-root "$PWD"
```

S17 install/uninstall project idempotent:
```bash
BASE=out/showcase/009/s17; HOME_SANDBOX="$BASE/home"; PROOT="$BASE/project"
mkdir -p "$BASE" "$HOME_SANDBOX" "$PROOT"
python -m pirml install-pi-ext --target project --source-dir .pi/extensions/pirml --home "$HOME_SANDBOX" --project-root "$PROOT"
python -m pirml uninstall-pi-ext --target project --home "$HOME_SANDBOX" --project-root "$PROOT"
python -m pirml uninstall-pi-ext --target project --home "$HOME_SANDBOX" --project-root "$PROOT"
```

S18 init deterministic bytes:
```bash
BASE=out/showcase/009/s18; rm -rf "$BASE"; mkdir -p "$BASE/a/tools" "$BASE/b/tools"
python -m pirml tool init demo.det --tools-dir "$BASE/a/tools"
python -m pirml tool init demo.det --tools-dir "$BASE/b/tools"
cmp "$BASE/a/tools/demo.det.json" "$BASE/b/tools/demo.det.json" && echo OK
```

S19 init invalid name fail lane:
```bash
python -m pirml tool init demo --tools-dir out/showcase/009/s19/tools ; echo rc=$?
```

S20 lint pass lane:
```bash
python -m pirml tool lint --tools-dir tools ; echo rc=$?
```

S21 lint failure payload detail lane:
```bash
TMP=$(mktemp -d); mkdir -p "$TMP/tools"
cat > "$TMP/tools/bad.json" <<'EOF'
{"name":"demo.bad","description":"bad","input_schema":{"type":"object","properties":{"id":{"type":"string"}}},"input_examples":[{}],"allowed_callers":["direct","code_exec"],"idempotent":true,"cacheable":true,"max_payload_bytes":0}
EOF
python -m pirml tool lint --tools-dir "$TMP/tools" ; echo rc=$?
```

S22 pack pass lane:
```bash
mkdir -p out/showcase/009/s22
python -m pirml tool pack --tools-dir tools --out out/showcase/009/s22/toolpack.json ; echo rc=$?
```

S23 pack deterministic bytes:
```bash
BASE=out/showcase/009/s23; mkdir -p "$BASE"
python -m pirml tool pack --tools-dir tools --out "$BASE/a.json"
python -m pirml tool pack --tools-dir tools --out "$BASE/b.json"
cmp "$BASE/a.json" "$BASE/b.json" && echo OK
```

S24 pack fail (missing catalog):
```bash
mkdir -p out/showcase/009/s24/empty
python -m pirml tool pack --tools-dir out/showcase/009/s24/empty --out out/showcase/009/s24/pack.json ; echo rc=$?
```

S25 pack schema quick view:
```bash
python - <<'PY'
import json; from pathlib import Path
d=json.loads(Path("out/showcase/009/s22/toolpack.json").read_text())
print({"keys":sorted(d.keys()),"catalog_hash":d["catalog_hash"],"docs":len(d["docs"]),"rankings":len(d["rankings"])})
PY
```

S26 smoke harness pass:
```bash
python -m scripts.spec09_tool_smoke
```

S27 smoke determinism x3:
```bash
for i in 0 1 2; do python -m scripts.spec09_tool_smoke --project-root .; done
```

S28 chaos smoke:
```bash
python -m scripts.spec09_eval_chaos
```

S29 report smoke:
```bash
python -m scripts.spec09_report_smoke
```

S30 helper golden:
```bash
mise run spec09-golden
```

S31 helper chaos:
```bash
mise run spec09-chaos
```

S32 helper report:
```bash
mise run spec09-report
```

S33 helper tasks listed:
```bash
mise tasks | rg -n "spec09|^fast\\s|^ci\\s"
```

S34 replay parity authority:
```bash
python -m scripts.replay_check
```

S35 artifact parity authority:
```bash
python -m scripts.artifact_rebuild --check
```

S36 C1 shell suite:
```bash
python -m unittest -q tests.test_spec09_c1_product_shell
```

S37 C2 manifest contract suite:
```bash
python -m unittest -q tests.test_spec09_c2_manifest_contract tests.test_toolsearch_lint
```

S38 C3 tool CLI suite:
```bash
python -m unittest -q tests.test_spec09_c3_tool_cli
```

S39 C4 extension policy TS suite:
```bash
npx tsx tests/test_spec09_c4_extension_policy.ts
```

S40 C5 runtime policy suites:
```bash
python -m unittest -q tests.test_spec09_c5_runtime_policy tests.test_compile_verify tests.test_replay
```

S41 C6 harness/chaos/gate suites:
```bash
python -m unittest -q tests.test_spec09_c6_harness tests.test_spec09_c6_chaos tests.test_spec09_c6_gate_contract
```

S42 C7 hardening suite:
```bash
python -m unittest -q tests.test_spec09_c7_hardening_sync
```

S43 tool surface freeze:
```bash
python -m unittest -q tests.test_tool_surface_freeze
```

S44 declared-failure matrix closure:
```bash
python -m unittest -q tests.test_spec09_c0_declared_failures
```

S45 full spec09 discover:
```bash
python -m unittest discover -s tests -p 'test_spec09*.py' -q
```

S46 fail-lane reopen trigger demo:
```bash
python -m pirml replay tests/prog_ok.py out/ci/trace.ndjson --timeout nope ; echo rc=$?
# if this is not typed config rc2, reopen affected cycle immediately.
```

S47 authority close bundle:
```bash
mise run fast
mise run ci
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
python -m unittest discover -s tests -p 'test_spec09*.py' -q
npx tsx tests/test_spec09_c4_extension_policy.ts
```

S48 compact daily confidence loop:
```bash
python -m scripts.spec09_tool_smoke
python -m scripts.spec09_eval_chaos
python -m scripts.spec09_report_smoke
python -m scripts.replay_check
```

## 6) Anti-Patterns (ban list)
1. Claiming new runtime tools were added.
2. Expanding `final.json` root for convenience.
3. Accepting argparse `usage:` on parse failures.
4. Treating green happy-path as release proof.
5. Editing docs/snippets without `tests.test_spec09_c7_hardening_sync`.
6. Mutating `ci`/`fast` command strings.
7. Re-adding deleted loser commands/flags without new invariant+tests+ledger sync.
8. Ignoring replay/artifact parity because unit tests passed.

## 7) Triage Shortcuts
1. Parse/config issue: reproduce with failing CLI and inspect typed stderr JSON first.
2. Tool authoring issue: run `tests.test_spec09_c3_tool_cli` + `tool lint` fail lane.
3. Policy issue: run `tests.test_spec09_c5_runtime_policy` + TS extension suite.
4. Gate drift suspicion: run `tests.test_spec08_c5_gate_contract` and `tests.test_spec09_c6_gate_contract`.
5. Docs drift suspicion: run `tests.test_spec09_c7_hardening_sync` immediately.
6. Trust issue: rerun `replay_check` then `artifact_rebuild --check`.

## 8) Exit-Code Contract
1. `0`: success.
2. `1`: business/validation/tool/unsupported.
3. `2`: integrity/config/internal.
