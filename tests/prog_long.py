from pirml.protocol import call, send_final


def main():
    try:
        r1 = call("readfile", {"path": "tests/fixtures/long_payload.txt"})
        results = [
            {"id": r1["id"], "tool": "readfile", "ok": r1["ok"]},
        ]
        send_final(ok=True, result={"ok": True, "results": results})
    except Exception as exc:
        send_final(ok=False, result={"ok": False, "error": str(exc), "results": []})


if __name__ == "__main__":
    main()
