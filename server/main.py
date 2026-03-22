import argparse
import asyncio

from src.bridge_client import BridgeClient
from src.bridge_process import BridgeProcess, find_free_port
import src.mcp_server as mcp_module
from src.mcp_server import mcp


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Konva MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default="stdio",
        help="MCP transport to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for sse/http transports (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port for sse/http transports (default: 8000)",
    )
    return parser.parse_args()


async def run(transport: str, host: str, port: int) -> None:
    bridge_port = find_free_port()
    bridge_proc = BridgeProcess(bridge_port)

    await bridge_proc.start()
    mcp_module._bridge = BridgeClient(bridge_port)

    try:
        if transport == "stdio":
            await mcp.run_async(transport="stdio")
        else:
            await mcp.run_async(transport=transport, host=host, port=port)
    finally:
        await mcp_module._bridge.close()
        await bridge_proc.stop()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(run(args.transport, args.host, args.port))
