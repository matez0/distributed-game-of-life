import asyncio
from asyncio import StreamReader, StreamWriter
from multiprocessing import Event, Manager, Process, Value
from typing import Any, Self, cast

from dgol.cells import Direction, GolCells
from dgol.stream import StreamSerializer


class GolProcess(Process):
    def __init__(self, cells: list[list[int]] | None = None):
        super().__init__()

        self.host = "127.0.0.1"
        self.cells_server_port = Value("i", 0)
        self.border_port = Value("i", 0)
        self.neighbors = Manager().dict()
        self.neighbor_borders: dict[Direction, list[list[int]]] = {}

        self.iteration = 0
        self._cells = GolCells(cells or [[]])
        self.cells_server_started = Event()

        self.has_iterated = asyncio.Condition()
        self.is_border_sent = False

        self.start()
        self.cells_server_started.wait()

    def connect(self, other: Self, direction: Direction):
        self._add_neighbor(direction, other.border_port)
        other._add_neighbor(direction.opposite, self.border_port)

    def _add_neighbor(self, direction: Direction, border_port: Any) -> None:
        self.neighbors[direction] = border_port

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
        (direction, border_cells), *_ = (await StreamSerializer.recv(reader)).items()

        async with self.has_iterated:
            if Direction[direction] in self.neighbor_borders:
                await self.has_iterated.wait()

        self.neighbor_borders[Direction[direction]] = border_cells

        if not self.is_border_sent:
            self.is_border_sent = True

            await self._send_border()

        if set(self.neighbor_borders.keys()) == set(self.neighbors.keys()):
            self._cells.iterate()
            self.iteration += 1
            self.is_border_sent = False

            async with self.has_iterated:
                self.neighbor_borders = {}
                self.has_iterated.notify_all()

        await StreamSerializer.send(writer, "received")

        writer.close()
        await writer.wait_closed()

    async def _send_border(self) -> None:
        for direction, border_port in self.neighbors.items():
            _, writer = await asyncio.open_connection(self.host, border_port)

            await StreamSerializer.send(writer, {direction.opposite.name: self._cells.border_at(direction)})

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
