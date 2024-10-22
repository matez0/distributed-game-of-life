import asyncio
import json
from asyncio import StreamReader, StreamWriter
from multiprocessing import Event, Process, Value
from typing import Any, Optional

from dgol.stream import StreamSerializer


class GolProcess(Process):
    def __init__(self, cells: Optional[Any] = None):
        super().__init__()

        self.host = "127.0.0.1"
        self.cells_server_port = Value("i", 0)

        self._cells = cells
        self.cells_server_started = Event()

        self.start()
        self.cells_server_started.wait()

    def run(self) -> None:
        asyncio.run(self.arun())

    async def arun(self) -> None:
        cells_server = await asyncio.start_server(self._send_cells, self.host, 0)
        self.cells_server_port.value = cells_server.sockets[0].getsockname()[1]
        self.cells_server_started.set()

        await cells_server.serve_forever()

    async def _send_cells(self, reader: StreamReader, writer: StreamWriter) -> None:
        await StreamSerializer.send(writer, self._cells)

        writer.close()
        await writer.wait_closed()

    async def cells(self) -> Any:
        reader, writer = await asyncio.open_connection(self.host, self.cells_server_port.value)

        result = await StreamSerializer.recv(reader)

        writer.close()
        await writer.wait_closed()

        return result
