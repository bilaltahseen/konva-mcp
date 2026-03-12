import asyncio

from src.bridge_client import BridgeClient
from src.bridge_process import BridgeProcess, find_free_port
import src.mcp_server as mcp_module
from src.mcp_server import mcp


async def run() -> None:
    port = find_free_port()
    bridge_proc = BridgeProcess(port)

    await bridge_proc.start()
    mcp_module._bridge = BridgeClient(port)

    try:
        await mcp.run_async(transport="stdio")
    finally:
        await mcp_module._bridge.close()
        await bridge_proc.stop()


if __name__ == "__main__":
    asyncio.run(run())
