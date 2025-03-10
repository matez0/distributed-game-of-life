import asyncio
from asyncio import StreamReader, StreamWriter
from enum import Enum, auto
from multiprocessing import Event, Manager, Process, Value
from typing import Any, Self, cast

from dgol.cells import GolCells
from dgol.stream import StreamSerializer


class GolProcess(Process):
    class Direction(Enum):
        UP = auto()
        UPRIGHT = auto()
        RIGHT = auto()
        DOWNRIGHT = auto()
        DOWN = auto()
        DOWNLEFT = auto()
        LEFT = auto()
        UPLEFT = auto()

        @property
        def opposite(self) -> Self:
            opposites = [
                (self.UP, self.DOWN),
                (self.UPRIGHT, self.DOWNLEFT),
                (self.RIGHT, self.LEFT),
                (self.DOWNRIGHT, self.UPLEFT),
            ]
            return cast(dict[Self, Self], dict(opposites + [(other, one) for one, other in opposites]))[self]

    def __init__(self, cells: list[list[int]] | None = None):
        super().__init__()

        self.host = "127.0.0.1"
        self.cells_server_port = Value("i", 0)
        self.border_port = Value("i", 0)
        self.neighbours = Manager().dict()
        self.neighbour_borders: dict[GolProcess.Direction, list[list[int]]] = {}

        self.iteration = 0
        self._cells = GolCells(cells or [[]])
        self.cells_server_started = Event()

        self.is_border_sent = False

        self.start()
        self.cells_server_started.wait()

    def connect(self, other: Self, direction: Direction):
        self._add_neighbour(direction, other.border_port)
        other._add_neighbour(direction.opposite, self.border_port)

    def _add_neighbour(self, direction: Direction, border_port: Any) -> None:
        self.neighbours[direction] = border_port

    def run(self) -> None:
        asyncio.run(self.arun())

    async def arun(self) -> None:
        border_server = await asyncio.start_server(self._receive_border, self.host, 0)
        self.border_port.value = border_server.sockets[0].getsockname()[1]

        cells_server = await asyncio.start_server(self._send_cells, self.host, 0)
        self.cells_server_port.value = cells_server.sockets[0].getsockname()[1]
        self.cells_server_started.set()

        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(border_server.serve_forever())
            task_group.create_task(cells_server.serve_forever())

    async def _receive_border(self, reader: StreamReader, writer: StreamWriter) -> None:
        self.neighbour_borders.update(
            {
                self.Direction[direction]: border_info
                for direction, border_info in (await StreamSerializer.recv(reader)).items()
            }
        )

        if not self.is_border_sent:
            self.is_border_sent = True

            await self._send_border()

        if set(self.neighbour_borders.keys()) == set(self.neighbours.keys()):
            self._cells.iterate()
            self.iteration += 1
            self.neighbour_borders = {}
            self.is_border_sent = False

        await StreamSerializer.send(writer, "received")

        writer.close()
        await writer.wait_closed()

    async def _send_border(self) -> None:
        for direction, border_port in self.neighbours.items():
            _, writer = await asyncio.open_connection(self.host, border_port)

            await StreamSerializer.send(writer, {direction.opposite.name: "border"})

            writer.close()
            await writer.wait_closed()

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
