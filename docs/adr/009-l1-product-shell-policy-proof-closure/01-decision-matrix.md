# Decision Matrix (Ultra-Terse)

| Axis | Winner | Loser | Kill Condition |
|---|---|---|---|
| CLI composition | router + command modules | monolith mutation of run path | legacy `--prog/--replay` drift |
| Manifest location | extend existing schema/TypedDict | parallel dialect | keyset divergence |
| Tool init layout | loader-compatible deterministic flat layout | nested rewrite | loader/search refactor |
| Policy choke-point | extension interceptors + runtime adapter | runtime-only policy | payload/context leakage |
| Retry/cap source | manifest-driven adapter | hardcoded constants | retry on non-idempotent |
| Pack format | canonical JSON + catalog hash | sqlite pack | nondeterministic ordering |
| Doctor probes | static deterministic checks | live network fuzz | non-reproducible output |
| Gate integration | additive helpers only | mutate `ci/fast` | H2 byte-contract drift |
