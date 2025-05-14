import asyncio
from multiprocessing import Event, Manager, Process, Value
from typing import Any, Self

from dgol.cells import Direction, GolCells
from dgol.connection import Connection


class GolProcess(Process):
    def __init__(self, cells: list[list[int]] | None = None):
        super().__init__()

        self.host = "127.0.0.1"
        self.cells_server_port = Value("i", 0)
        self.wait_for_cells_server_port = Value("i", 0)
        self._border_port = Value("i", 0)
        self.neighbors = Manager().dict()
        self.neighbor_borders: dict[Direction, list[int]] = {}

        self.iteration = 0
        self._cells = GolCells(cells or [[]])
        self.cells_server_started = Event()

        self.has_iterated = asyncio.Condition()
        self.is_border_sent = False

        self.start()
        self.cells_server_started.wait()

        self.border_port = self._border_port.value

    def connect(self, other: Self, direction: Direction):
        self._add_neighbor(direction, other.border_port)
        other._add_neighbor(direction.opposite, self.border_port)

    def _add_neighbor(self, direction: Direction, border_port: int) -> None:
        self.neighbors[direction] = border_port

    def run(self) -> None:
        asyncio.run(self.arun())

    async def arun(self) -> None:
        border_server = await Connection.start_server(self._receive_border, self.host)
        self._border_port.value = Connection.port_of(border_server)

        wait_for_cells_server = await Connection.start_server(self._wait_for_cells, self.host)
        self.wait_for_cells_server_port.value = Connection.port_of(wait_for_cells_server)

        cells_server = await Connection.start_server(self._send_cells, self.host)
        self.cells_server_port.value = Connection.port_of(cells_server)
        self.cells_server_started.set()

        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(border_server.serve_forever())
            task_group.create_task(wait_for_cells_server.serve_forever())
            task_group.create_task(cells_server.serve_forever())

    async def _receive_border(self, connection: Connection) -> None:
        (direction, border_cells), *_ = (await connection.recv()).items()

        async with self.has_iterated:
            if Direction[direction] in self.neighbor_borders:
                await self.has_iterated.wait()

        self.neighbor_borders[Direction[direction]] = border_cells

        if not self.is_border_sent:
            self.is_border_sent = True

            await self._send_border()

        if set(self.neighbor_borders.keys()) == set(self.neighbors.keys()):
            self._cells.iterate(self.neighbor_borders)
            self.iteration += 1

            async with self.has_iterated:
                self.is_border_sent = False
                self.neighbor_borders = {}
                self.has_iterated.notify_all()

    async def _send_border(self) -> None:
        async with asyncio.TaskGroup() as task_group:
            for direction, border_port in self.neighbors.items():
                task_group.create_task(self._send_border_to(direction, border_port))

    async def _send_border_to(self, direction: Direction, border_port: int) -> None:
        async with Connection.connect(self.host, border_port) as connection:

            await connection.send({direction.opposite.name: self._cells.border_at(direction)})

    async def _wait_for_cells(self, connection: Connection) -> None:
        iteration = await connection.recv()

        async with self.has_iterated:
            while self.iteration < iteration:
                await self.has_iterated.wait()

        await connection.send(self._cells.as_serializable)

    async def _send_cells(self, connection: Connection) -> None:
        iteration = await connection.recv()

        if iteration:
            while self.iteration < iteration:
                if self.neighbors:
                    if not self.is_border_sent:
                        self.is_border_sent = True

                        await self._send_border()

                    async with self.has_iterated:
                        if self.is_border_sent:
                            await self.has_iterated.wait()
                else:
                    self._cells.iterate()
                    self.iteration += 1

        await connection.send(self._cells.as_serializable)

    async def cells(self, iteration: int | None = None) -> Any:
        return await self._request_cells(self.cells_server_port.value, iteration)

    async def _request_cells(self, server_port: int, iteration: int | None) -> Any:
        async with Connection.connect(self.host, server_port) as connection:
            await connection.send(iteration)

            return await connection.recv()

    async def wait_for_cells(self, iteration: int) -> Any:
        return await self._request_cells(self.wait_for_cells_server_port.value, iteration)
