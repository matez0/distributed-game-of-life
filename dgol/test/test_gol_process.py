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
            self.assertEqual(await process.cells(), cells)
