from pirml.protocol import call, send_final


def main():
    try:
        r1 = call("echo", {"text": "fail_test"})
        # This should fail with ErrorType.FILE_NOT_FOUND
        r2 = call("readfile", {"path": "non_existent_file.txt"})

        results = [
            {"id": r1["id"], "tool": "echo", "ok": r1["ok"]},
            {"id": r2["id"], "tool": "readfile", "ok": r2["ok"], "error": r2.get("error")},
        ]
        send_final(ok=False, result={"ok": False, "results": results})
    except Exception as exc:
        send_final(
            ok=False,
            result={"ok": False, "error": {"type": "exception", "msg": str(exc)}, "results": []},
        )


if __name__ == "__main__":
    main()
