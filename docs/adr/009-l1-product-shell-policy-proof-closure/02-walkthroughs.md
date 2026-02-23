# Walkthroughs

## W1: Parse-Law Failure Contract
```bash
python -m pirml tool lint --tools-dir
echo $?   # 2
# stderr: {"type":"config","msg":"...","retryable":false}
# stderr must NOT contain: usage:
```

## W2: Bootstrap Authoring Lane
```bash
python -m pirml tool init demo.foo --tools-dir .tmp/w2/tools
python -m pirml tool lint --tools-dir .tmp/w2/tools   # allowed with enforce_hot_count=false
python -m pirml tool pack --tools-dir .tmp/w2/tools --out .tmp/w2/pack.json   # strict catalog checks apply
```

## W3: L1 Safety Without L0 Drift
```text
operator cmd
 -> product wrapper
 -> owner path (scripts.pirml_run/runtime_bridge/python -m pirml)
 -> frozen runtime tools
 -> trace/final
 -> replay parity
```

## W4: Authority Closure
```bash
mise run fast && mise run ci
python -m scripts.replay_check
python -m scripts.artifact_rebuild --check
python -m unittest discover -s tests -p 'test_spec09*.py' -q
npx tsx tests/test_spec09_c4_extension_policy.ts
```
