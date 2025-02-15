import asyncio
from asyncio import StreamReader, StreamWriter
from enum import Enum, auto
from multiprocessing import Event, Process, Value
from typing import Any, Self

from dgol.cells import GolCells
from dgol.stream import StreamSerializer


class GolProcess(Process):
    class Direction(Enum):
        UP = auto()
        DOWN = auto()

    def __init__(self, cells: list[list[int]] | None = None):
        super().__init__()

        self.host = "127.0.0.1"
        self.cells_server_port = Value("i", 0)
        self.border_port = Value("i", 0)

        self.iteration = 0
        self._cells = GolCells(cells or [[]])
        self.cells_server_started = Event()

        self.start()
        self.cells_server_started.wait()

    def connect(self, other: Self, direction: Direction):
        self._add_neighbour(direction, other.border_port)
        opposite_direction = self.Direction.DOWN if direction == self.Direction.UP else self.Direction.UP
        other._add_neighbour(opposite_direction, self.border_port)

    def _add_neighbour(self, direction: Direction, border_port: Any) -> None:
        pass

    def run(self) -> None:
        asyncio.run(self.arun())

    async def arun(self) -> None:
        cells_server = await asyncio.start_server(self._send_cells, self.host, 0)
        self.cells_server_port.value = cells_server.sockets[0].getsockname()[1]
        self.cells_server_started.set()

        await cells_server.serve_forever()

    async def _send_cells(self, reader: StreamReader, writer: StreamWriter) -> None:
        iteration = await StreamSerializer.recv(reader)

        if iteration:
            while self.iteration < iteration:
                self._cells.iterate()
                self.iteration += 1

        await StreamSerializer.send(writer, self._cells.as_serializable)

        writer.close()
        await writer.wait_closed()

    async def cells(self, iteration: int | None = None) -> Any:
        reader, writer = await asyncio.open_connection(self.host, self.cells_server_port.value)

        await StreamSerializer.send(writer, iteration)

        result = await StreamSerializer.recv(reader)

        writer.close()
        await writer.wait_closed()

        return result
