from contextlib import contextmanager
from multiprocessing import Process
from typing import Any, Generator, Optional
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch

from dgol.process import GolProcess


class TestGolProcess(IsolatedAsyncioTestCase):
    @contextmanager
    def create_process(self, cells: Optional[Any] = None) -> Generator[GolProcess, None, None]:
        process = GolProcess(cells)
        try:
            yield process

        finally:
            process.terminate()

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

        class GolCellsStub:
            iteration_counter = 0

            def iterate(self) -> None:
                self.iteration_counter += 1

            @property
            def as_serializable(self) -> list[list[int]]:
                return [[self.iteration_counter]]

        gol_cells_ctor.return_value = GolCellsStub()

        with self.create_process(cells) as process:
            self.assertEqual(
                await process.cells(iteration=iteration),
                [[iteration]]
            )
            gol_cells_ctor.assert_called_once_with(cells)

    def test_gol_processes_can_be_connected(self):
        other_process = Mock(spec=GolProcess, border_port=123)

        with self.create_process([[0]]) as process, patch.object(process, "_add_neighbour") as add_neighbour:
            process.connect(other_process, GolProcess.Direction.UP)

            add_neighbour.assert_called_once_with(GolProcess.Direction.UP, other_process.border_port)
            other_process._add_neighbour.assert_called_once_with(GolProcess.Direction.DOWN, process.border_port)

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
