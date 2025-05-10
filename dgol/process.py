import asyncio
from multiprocessing import Event, Manager, Process, Value
from typing import Any, Self, cast

from dgol.cells import Direction, GolCells
from dgol.stream import StreamSerializer


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
        border_server = await asyncio.start_server(self._receive_border, self.host, 0)
        self._border_port.value = border_server.sockets[0].getsockname()[1]

        wait_for_cells_server = await asyncio.start_server(self._wait_for_cells, self.host, 0)
        self.wait_for_cells_server_port.value = wait_for_cells_server.sockets[0].getsockname()[1]

        cells_server = await asyncio.start_server(self._send_cells, self.host, 0)
        self.cells_server_port.value = cells_server.sockets[0].getsockname()[1]
        self.cells_server_started.set()

        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(border_server.serve_forever())
            task_group.create_task(wait_for_cells_server.serve_forever())
            task_group.create_task(cells_server.serve_forever())

    @StreamSerializer.callback
    async def _receive_border(self, stream: StreamSerializer) -> None:
        (direction, border_cells), *_ = (await stream.recv()).items()

        async with self.has_iterated:
            if Direction[direction] in self.neighbor_borders:
                await self.has_iterated.wait()

        iteration = self.iteration
        self.neighbor_borders[Direction[direction]] = border_cells

        await stream.aclose()

        if iteration < self.iteration:
            return  # The iteration already happened with this border during waiting for closed.

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
        async with StreamSerializer.connect(self.host, border_port) as stream:

            await stream.send({direction.opposite.name: self._cells.border_at(direction)})

    @StreamSerializer.callback
    async def _wait_for_cells(self, stream: StreamSerializer) -> None:
        iteration = await stream.recv()

        async with self.has_iterated:
            while self.iteration < iteration:
                await self.has_iterated.wait()

        await stream.send(self._cells.as_serializable)

    @StreamSerializer.callback
    async def _send_cells(self, stream: StreamSerializer) -> None:
        iteration = await stream.recv()

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

        await stream.send(self._cells.as_serializable)

    async def cells(self, iteration: int | None = None) -> Any:
        return await self._request_cells(self.cells_server_port.value, iteration)

    async def _request_cells(self, server_port: int, iteration: int | None) -> Any:
        async with StreamSerializer.connect(self.host, server_port) as stream:
            await stream.send(iteration)

            return await stream.recv()

    async def wait_for_cells(self, iteration: int) -> Any:
        return await self._request_cells(self.wait_for_cells_server_port.value, iteration)
