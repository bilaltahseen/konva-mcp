import asyncio
import os
import socket
import sys
from pathlib import Path

BRIDGE_DIR = Path(__file__).parent.parent.parent / "bridge"
STARTUP_TIMEOUT = 30  # seconds


def find_free_port(start: int = 3847) -> int:
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found in range 3847-3946")


class BridgeProcess:
    def __init__(self, port: int):
        self._port = port
        self._process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        env = {**os.environ, "BRIDGE_PORT": str(self._port)}
        kwargs: dict = dict(
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(BRIDGE_DIR),
            env=env,
        )
        # Windows needs CREATE_NEW_PROCESS_GROUP for clean termination
        if sys.platform == "win32":
            import subprocess
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        self._process = await asyncio.create_subprocess_exec(
            "node", str(BRIDGE_DIR / "server.js"), **kwargs
        )
        # Wait until bridge writes BRIDGE_READY to stdout
        await asyncio.wait_for(self._wait_for_ready(), timeout=STARTUP_TIMEOUT)

    async def _wait_for_ready(self) -> None:
        assert self._process and self._process.stdout
        async for line in self._process.stdout:
            if b"BRIDGE_READY" in line:
                return
        raise RuntimeError("Bridge process exited before signaling BRIDGE_READY")

    async def stop(self) -> None:
        if not self._process or self._process.returncode is not None:
            return
        if sys.platform == "win32":
            import subprocess
            self._process.send_signal(subprocess.signal.CTRL_BREAK_EVENT)
        else:
            self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except asyncio.TimeoutError:
            self._process.kill()

    @property
    def port(self) -> int:
        return self._port
