from pirml.protocol import call, send_final


def main():
    try:
        r1 = call("echo", {"text": "alpha"})
        r2 = call("readfile", {"path": "tests/fixtures/sample.txt"})
        r3 = call("bash", {"command": "printf shell_ok"})

        results = [
            {"id": r1["id"], "tool": "echo", "ok": r1["ok"]},
            {"id": r2["id"], "tool": "readfile", "ok": r2["ok"]},
            {"id": r3["id"], "tool": "bash", "ok": r3["ok"]},
        ]
        send_final(ok=True, result={"ok": True, "results": results})
    except Exception as exc:
        send_final(ok=False, result={"ok": False, "error": str(exc), "results": []})


if __name__ == "__main__":
    main()
