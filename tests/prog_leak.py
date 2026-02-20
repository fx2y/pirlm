from pirml.protocol import call, send_final

call("echo", {"text": "alpha"})
# Try to leak something in results
send_final(
    True,
    {"ok": True, "results": [{"id": "c00001", "ok": True, "tool": "echo", "leak": "secret_data"}]},
)
