import asyncio
from pirml.runtime.rpc import send_final

async def main() -> None:
    send_final(True, {"ok": True, "results": []})


if __name__ == "__main__":
    asyncio.run(main())