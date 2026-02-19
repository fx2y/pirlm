from pirml.protocol import call, send_final


def main():
    # Call bash to produce large output.
    # The CALL itself is small, but the RESULT will be large.
    r1 = call("bash", {"command": 'python3 -c \'print("A"*10000, end="")\''})

    send_final(
        ok=True, result={"ok": True, "results": [{"id": r1["id"], "ok": r1["ok"], "tool": "bash"}]}
    )


if __name__ == "__main__":
    main()
