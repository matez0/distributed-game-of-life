import asyncio
from contextlib import contextmanager
from multiprocessing import Process
from typing import Any, Generator, Optional
from unittest import IsolatedAsyncioTestCase

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
            self.assertEqual(await process.cells(iteration=0), cells)

    async def test_cells_with_less_than_2_alive_neighbours_shall_die(self):
        cells = [
            [1, 0, 0, 1],
            [1, 0, 0, 0],
            [0, 0, 0, 0],
        ]

        with self.create_process(cells) as process:
            self.assertEqual(await process.cells(iteration=1), [[0] * 4] * 3)

    async def test_alive_cells_with_2_or_3_alive_neighbours_shall_stay_alive(self):
        cells = [
            [0, 1, 1],
            [1, 0, 1],
            [0, 1, 0],
        ]

        with self.create_process(cells) as process:
            self.assertEqual(await process.cells(iteration=1), cells)

    async def test_alive_cells_with_more_than_3_alive_neighbours_shall_die(self):
        cells = [
            [1, 1, 1],
            [1, 0, 1],
            [1, 1, 1],
        ]

        with self.create_process(cells) as process:
            self.assertEqual(
                await process.cells(iteration=1),
                [
                    [1, 0, 1],
                    [0, 0, 0],
                    [1, 0, 1],
                ],
            )

    async def test_dead_cells_with_3_alive_neighbours_shall_be_alive(self):
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
