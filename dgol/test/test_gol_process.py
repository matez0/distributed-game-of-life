import asyncio
from contextlib import asynccontextmanager, closing, contextmanager
from multiprocessing import Process
from typing import Any, AsyncGenerator, Generator, Optional
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from dgol.process import GolProcess
from dgol.stream import StreamSerializer


class GolCellsStubToGetIteration:
    iteration_counter = 0

    def iterate(self) -> None:
        self.iteration_counter += 1

    @property
    def as_serializable(self) -> list[list[int]]:
        return [[self.iteration_counter]]


class TestGolProcess(IsolatedAsyncioTestCase):
    @contextmanager
    def create_process(self, cells: Optional[Any] = None) -> Generator[GolProcess, None, None]:
        process = GolProcess(cells)
        try:
            yield process

        finally:
            process.terminate()

    @asynccontextmanager
    async def create_neighbor(self) -> AsyncGenerator[AsyncMock, None]:
        def close_writer(reader, writer):
            writer.close()

        neighbor = AsyncMock(spec=GolProcess, receive_border=AsyncMock(side_effect=close_writer), host="127.0.0.1")

        async with await asyncio.start_server(neighbor.receive_border, neighbor.host, 0) as border_server:
            neighbor.border_port = border_server.sockets[0].getsockname()[1]

            yield neighbor

    async def send_border_to(self, process: GolProcess, border: dict[str, Any]) -> None:
        reader, writer = await asyncio.open_connection(process.host, process.border_port.value)

        await StreamSerializer.send(writer, border)

        self.assertEqual(await StreamSerializer.recv(reader), "received")

        writer.close()
        await writer.wait_closed()

    def test_shall_be_a_process_instance(self):
        with self.create_process() as process:
            self.assertIsInstance(process, Process)

    async def test_cells_shall_be_able_to_be_retrieved(self):
        cells = [
            [1, 2, 3],
            [4, 5, 6],
            [7, 8, 9],
        ]

        with self.create_process(cells) as process:
            self.assertEqual(await process.cells(), cells)

    async def test_cells_can_iterate(self):
        cells = [
            [0, 1, 0],
            [1, 0, 1],
            [0, 0, 0],
        ]

        with self.create_process(cells) as process:
            self.assertEqual(
                await process.cells(iteration=1),
                [
                    [0, 1, 0],
                    [0, 1, 0],
                    [0, 0, 0],
                ],
            )

    @patch("dgol.process.GolCells", spec=True)
    async def test_cells_shall_iterate_specified_times(self, gol_cells_ctor):
        cells = [[0]]
        iteration = 6

        gol_cells_ctor.return_value = GolCellsStubToGetIteration()

        with self.create_process(cells) as process:
            self.assertEqual(
                await process.cells(iteration=iteration),
                [[iteration]]
            )
            gol_cells_ctor.assert_called_once_with(cells)

    def test_gol_processes_can_be_connected(self):
        other_process = Mock(spec=GolProcess, border_port=123)

        with self.create_process([[0]]) as process, patch.object(process, "_add_neighbor") as add_neighbor:
            process.connect(other_process, GolProcess.Direction.UP)

            add_neighbor.assert_called_once_with(GolProcess.Direction.UP, other_process.border_port)
            other_process._add_neighbor.assert_called_once_with(GolProcess.Direction.DOWN, process.border_port)

    def test_opposite_directions(self):
        for direction, opposite in [
            (GolProcess.Direction.UP, GolProcess.Direction.DOWN),
            (GolProcess.Direction.UPRIGHT, GolProcess.Direction.DOWNLEFT),
            (GolProcess.Direction.RIGHT, GolProcess.Direction.LEFT),
            (GolProcess.Direction.DOWNRIGHT, GolProcess.Direction.UPLEFT),
        ]:
            with self.subTest(directions=(direction.name, opposite.name)):
                self.assertEqual(direction.opposite, opposite)
                self.assertEqual(opposite.opposite, direction)

    async def test_receiving_border_info_triggers_sending_border_once(self):
        direction_1 = GolProcess.Direction.UP
        direction_2 = GolProcess.Direction.RIGHT

        def assert_received_border_from(direction):
            async def assert_received_border(reader, writer):
                with closing(writer):
                    self.assertEqual(await StreamSerializer.recv(reader), {direction.opposite.name: "border"})

            return assert_received_border

        async with self.create_neighbor() as neighbor_1, self.create_neighbor() as neighbor_2:
            neighbor_1.receive_border.side_effect = assert_received_border_from(direction_1)
            neighbor_2.receive_border.side_effect = assert_received_border_from(direction_2)

            with self.create_process([[0]]) as process:
                process.connect(neighbor_1, direction_1)
                process.connect(neighbor_2, direction_2)

                await self.send_border_to(process, {"LEFT": "border"})
                await self.send_border_to(process, {"RIGHT": "border"})

            neighbor_1.receive_border.assert_awaited_once()
            neighbor_2.receive_border.assert_awaited_once()

    @patch("dgol.process.GolCells", spec=True)
    async def test_receiving_border_info_from_all_neighbor_triggers_iteration(self, gol_cells_ctor: Mock):
        gol_cells_ctor.return_value = GolCellsStubToGetIteration()

        direction_1 = GolProcess.Direction.UP
        direction_2 = GolProcess.Direction.RIGHT

        async with self.create_neighbor() as neighbor_1, self.create_neighbor() as neighbor_2:
            with self.create_process([[8, 9]]) as process:
                process.connect(neighbor_1, direction_1)
                process.connect(neighbor_2, direction_2)

                await self.send_border_to(process, {direction_1.name: "border"})

                self.assertEqual(await process.cells(), [[0]])

                await self.send_border_to(process, {direction_2.name: "border"})

                self.assertEqual(await process.cells(), [[1]])

    @patch("dgol.process.GolCells", spec=True)
    async def test_sending_border_can_be_triggered_again_after_iteration(self, gol_cells_ctor: Mock):
        gol_cells_ctor.return_value = GolCellsStubToGetIteration()

        direction = GolProcess.Direction.UP

        async with self.create_neighbor() as neighbor:
            with self.create_process([[8, 9]]) as process:
                process.connect(neighbor, direction)

                await self.send_border_to(process, {direction.name: "border"})

                self.assertEqual(await process.cells(), [[1]])

                await self.send_border_to(process, {direction.name: "border"})

                self.assertEqual(await process.cells(), [[2]])

            self.assertEqual(neighbor.receive_border.await_count, 2)
