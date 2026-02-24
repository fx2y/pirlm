# Spec10 Proof-Gating Course

Date: `2026-02-24`.
Scope: C5 persona packaging over C1/C2/C3/C4 shipped surfaces.
Authority source: `spec-0/10/21-command-matrix.jsonl`.

## Operator flow

1. Generate the persona pack:
```bash
python -m scripts.spec10_sales_pack --out out/spec10_sales
```
2. Resolve authority rows for buyer-priority lanes:
```bash
python -m scripts.spec10_matrix --lane W0
python -m scripts.spec10_matrix --lane W1
python -m scripts.spec10_matrix --lane W8
python -m scripts.spec10_matrix --lane W9
```
3. Confirm packaging proof lane:
```bash
python -m unittest -q tests.test_spec10_c5_packaging_sync
```

## Buyer mapping

| Buyer | Hook lane set | Matrix ids to resolve | Verification refs |
|---|---|---|---|
| Head AI Platform | trust gate + parity | `W0`,`W1` | `I18` |
| Security/Policy | typed fail-closed policy | `W8`,`W1` | `I19` |
| QA/RelEng | protocol/compile contracts | `W1`,`W3` | `I18`,`I19` |
| PM/ML lead | KPI economics + evidence | `W7`,`W4` | `I18` |
| FDE | incident-to-class | `W9`,`W5` | `I19` |

## Disqualifier enforcement

- unknown flag/provider/tool fallbacks requested
- dashboard-only narrative without artifact pointers requested
- runtime surface mutation requested without invariant/test/ledger sync
- explicit dataset/path ingress discipline rejected

## Exit

- `out/spec10_sales/persona_pack.jsonl` exists and each persona row has `{proof_cmd,artifact_ptr}`.
- optional lane `W4b` is labeled `{truth: informational, status: unsupported}`.
- all commands shown above resolve from matrix IDs and stay owner-path compliant.
