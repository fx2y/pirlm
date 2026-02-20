import asyncio

from pirml.runtime.rpc import AsyncRpcClient, send_final


async def main() -> None:
    client = AsyncRpcClient()
    await client.start()
    try:
        # Fan-out: call 3 echoes in parallel
        tasks = [client.call("echo", {"text": f"msg-{i}"}) for i in range(3)]
        results = await asyncio.gather(*tasks)

        # Aggregate
        output = [r["output"] for r in results]
        ok = all(r["ok"] for r in results)

        send_final(ok=ok, result={"ok": ok, "output": output, "count": len(results)})
    except Exception as exc:
        send_final(ok=False, result={"ok": False, "error": str(exc)})
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
