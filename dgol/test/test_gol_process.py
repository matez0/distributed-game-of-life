import asyncio
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from multiprocessing import Process
from typing import Any, AsyncGenerator, Generator, Optional
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from dgol.cells import Direction
from dgol.process import GolProcess
from dgol.connection import Connection


class GolCellsStubToGetIteration:
    iteration_counter = 0

    def iterate(self, neighbor_borders=None) -> None:
        self.iteration_counter += 1

    def border_at(self, direction: Direction) -> list[int]:
        return [0]

    @property
    def as_serializable(self) -> list[list[int]]:
        return [[self.iteration_counter]]


class TestGolProcess(IsolatedAsyncioTestCase):
    @staticmethod
    @contextmanager
    def create_process(cells: Optional[Any] = None) -> Generator[GolProcess, None, None]:
        process = GolProcess(cells)
        try:
            yield process

        finally:
            process.terminate()

    @staticmethod
    @asynccontextmanager
    async def create_neighbor() -> AsyncGenerator[AsyncMock, None]:
        def receive_border_cb(callback):
            @wraps(callback)
            async def _receive_border_cb(connection):
                await callback(connection)

                async with neighbor._receive_border_called:
                    neighbor._receive_border_called.notify_all()

            return _receive_border_cb

        @receive_border_cb
        async def ignore(connection):
            pass

        async def receive_border_called():
            async with neighbor._receive_border_called:
                await neighbor._receive_border_called.wait()

        neighbor = AsyncMock(
            spec=GolProcess,
            receive_border=AsyncMock(side_effect=ignore),
            host="127.0.0.1",
            _receive_border_called=asyncio.Condition(),
            receive_border_called_coro_factory=receive_border_called,
            receive_border_called=asyncio.create_task(receive_border_called()),
            receive_border_cb=receive_border_cb,
        )

        async with await Connection.start_server(neighbor.receive_border, neighbor.host) as border_server:
            neighbor.border_port = Connection.port_of(border_server)

            yield neighbor

    @staticmethod
    async def wait_for_receive_border_called(neighbor: AsyncMock, timeout=2):
        await asyncio.wait_for(asyncio.shield(neighbor.receive_border_called), timeout=timeout)

        neighbor.receive_border_called = asyncio.create_task(neighbor.receive_border_called_coro_factory())

    @staticmethod
    async def send_border_to(process: GolProcess, border: dict[str, Any]) -> None:
        async with Connection.connect(process.host, process.border_port) as connection:
            await connection.send(border)

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
            process.connect(other_process, Direction.UP)

            add_neighbor.assert_called_once_with(Direction.UP, other_process.border_port)
            other_process._add_neighbor.assert_called_once_with(Direction.DOWN, process.border_port)

    def test_opposite_directions(self):
        for direction, opposite in [
            (Direction.UP, Direction.DOWN),
            (Direction.UPRIGHT, Direction.DOWNLEFT),
            (Direction.RIGHT, Direction.LEFT),
            (Direction.DOWNRIGHT, Direction.UPLEFT),
        ]:
            with self.subTest(directions=(direction.name, opposite.name)):
                self.assertEqual(direction.opposite, opposite)
                self.assertEqual(opposite.opposite, direction)

    @patch("dgol.process.GolCells", spec=True)
    async def test_receiving_border_info_triggers_sending_border_once(self, gol_cells_ctor: Mock):
        direction_1 = Direction.UP
        border_1 = "upper-border"
        direction_2 = Direction.RIGHT
        border_2 = "right-border"

        def border_at(direction: Direction) -> Any:
            return {direction_1: border_1, direction_2: border_2}[direction]

        gol_cells_ctor.return_value.border_at.side_effect = border_at

        def save_received_border(neighbor):
            @neighbor.receive_border_cb
            async def _save_received_border(connection):
                # We cannot do assertion here because the callback handler of StreamReaderProtocol
                # does not let the assertion to propagate to the test framework.
                neighbor.received_border = await connection.recv()

            neighbor.receive_border.side_effect = _save_received_border

        async with self.create_neighbor() as neighbor_1, self.create_neighbor() as neighbor_2:
            save_received_border(neighbor_1)
            save_received_border(neighbor_2)

            with self.create_process([[0]]) as process:
                process.connect(neighbor_1, direction_1)
                process.connect(neighbor_2, direction_2)

                await self.send_border_to(process, {"LEFT": "border"})
                await self.send_border_to(process, {"RIGHT": "border"})

                await self.wait_for_receive_border_called(neighbor_1)
                await self.wait_for_receive_border_called(neighbor_2)

            self.assertEqual(neighbor_1.received_border, {direction_1.opposite.name: border_at(direction_1)})
            self.assertEqual(neighbor_2.received_border, {direction_2.opposite.name: border_at(direction_2)})
            neighbor_1.receive_border.assert_awaited_once()
            neighbor_2.receive_border.assert_awaited_once()

    @patch("dgol.process.GolCells", new=Mock(return_value=GolCellsStubToGetIteration()))
    async def test_receiving_border_info_from_all_neighbor_triggers_iteration(self):
        direction_1 = Direction.UP
        direction_2 = Direction.RIGHT

        async with self.create_neighbor() as neighbor_1, self.create_neighbor() as neighbor_2:
            with self.create_process([[8, 9]]) as process:
                process.connect(neighbor_1, direction_1)
                process.connect(neighbor_2, direction_2)

                await self.send_border_to(process, {direction_1.name: "border"})

                wait_for_iteration = asyncio.create_task(process.wait_for_cells(iteration=1))

                with self.assertRaises(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(wait_for_iteration), timeout=.1)

                await self.send_border_to(process, {direction_2.name: "border"})

                self.assertEqual(await wait_for_iteration, [[1]])

    @patch("dgol.process.GolCells", new=Mock(return_value=GolCellsStubToGetIteration()))
    async def test_sending_border_can_be_triggered_again_after_iteration(self):
        direction = Direction.UP

        async with self.create_neighbor() as neighbor:
            with self.create_process([[8, 9]]) as process:
                process.connect(neighbor, direction)

                await self.send_border_to(process, {direction.name: "border"})

                self.assertEqual(await process.wait_for_cells(iteration=1), [[1]])

                await self.send_border_to(process, {direction.name: "border"})

                self.assertEqual(await process.wait_for_cells(iteration=2), [[2]])

            self.assertEqual(neighbor.receive_border.await_count, 2)

    @patch("dgol.process.GolCells", new=Mock(return_value=GolCellsStubToGetIteration()))
    async def test_wait_for_iteration_before_setting_again_the_same_border_info(self):
        direction_1 = Direction.UP
        direction_2 = Direction.RIGHT

        async with self.create_neighbor() as neighbor_1, self.create_neighbor() as neighbor_2:
            with self.create_process([[8, 9]]) as process:
                process.connect(neighbor_1, direction_1)
                process.connect(neighbor_2, direction_2)

                await self.send_border_to(process, {direction_1.name: "border"})

                await self.wait_for_receive_border_called(neighbor_1)

                await self.send_border_to(process, {direction_1.name: "border"})

                with self.assertRaises(TimeoutError):
                    # Border is sent to neighbors after receiving and storing any border info.
                    await self.wait_for_receive_border_called(neighbor_1, timeout=.1)

                await self.send_border_to(process, {direction_2.name: "border"})  # Trigger iteration.

                self.assertEqual(await process.wait_for_cells(iteration=1), [[1]])

                await self.wait_for_receive_border_called(neighbor_1)

                self.assertEqual(neighbor_1.receive_border.await_count, 2)
                self.assertEqual(neighbor_2.receive_border.await_count, 2)

    @patch("dgol.process.GolCells", new=Mock(return_value=GolCellsStubToGetIteration()))
    async def test_iteration_of_connected_gol_processes_is_initiated_by_sending_border(self):
        direction = Direction.UP

        async with self.create_neighbor() as neighbor:
            with self.create_process([[8, 9]]) as process:
                process.connect(neighbor, direction)

                async def receive_border(connection) -> None:
                    await connection.recv()

                    await self.send_border_to(process, {direction.name: "border"})  # Trigger iteration.

                neighbor.receive_border.side_effect = receive_border

                self.assertEqual(await process.cells(iteration=1), [[1]])  # Shall send border to neighbor.

                neighbor.receive_border.assert_awaited_once()

    async def test_cells_of_connected_gol_processes_can_be_iterated(self):
        cells_up = [
            [0, 0, 0],
            [0, 0, 0],
            [1, 0, 1],
        ]
        cells = [
            [0, 1, 0],
            [0, 0, 0],
            [0, 0, 1],
        ]
        cells_right = [
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 0],
        ]

        with (
            self.create_process(cells) as process,
            self.create_process(cells_up) as process_up,
            self.create_process(cells_right) as process_right
        ):
            process.connect(process_up, Direction.UP)
            process.connect(process_right, Direction.RIGHT)
            process_right.connect(process_up, Direction.UPLEFT)

            self.assertEqual(
                await process.cells(iteration=1),
                [
                    [0, 1, 1],
                    [0, 0, 1],
                    [0, 0, 0],
                ],
            )
            self.assertEqual(
                await process_up.wait_for_cells(iteration=1),
                [
                    [0, 0, 0],
                    [0, 0, 0],
                    [0, 1, 1],
                ],
            )
            self.assertEqual(
                await process_right.wait_for_cells(iteration=1),
                [
                    [1, 0, 0],
                    [1, 0, 0],
                    [0, 0, 0],
                ],
            )
