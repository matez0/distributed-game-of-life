import asyncio
import json
from asyncio import StreamReader, StreamWriter
from multiprocessing import Event, Process, Value
from typing import Any

from dgol.stream import StreamSerializer


class GolProcess(Process):
    def __init__(self, cells: list[list[int]] | None = None):
        super().__init__()

        self.host = "127.0.0.1"
        self.cells_server_port = Value("i", 0)

        self.iteration = 0
        self._cells = cells or [[]]
        self.cells_server_started = Event()

        self.start()
        self.cells_server_started.wait()

    def run(self) -> None:
        asyncio.run(self.arun())

    async def arun(self) -> None:
        cells_server = await asyncio.start_server(self._send_cells, self.host, 0)
        self.cells_server_port.value = cells_server.sockets[0].getsockname()[1]
        self.cells_server_started.set()

        await cells_server.serve_forever()

    async def _send_cells(self, reader: StreamReader, writer: StreamWriter) -> None:
        iteration = await StreamSerializer.recv(reader)

        while self.iteration < iteration:
            self._iterate()

        await StreamSerializer.send(writer, self._cells)

        writer.close()
        await writer.wait_closed()

    async def cells(self, iteration: int) -> Any:
        reader, writer = await asyncio.open_connection(self.host, self.cells_server_port.value)

        await StreamSerializer.send(writer, iteration)

        result = await StreamSerializer.recv(reader)

        writer.close()
        await writer.wait_closed()

        return result

    def _iterate(self) -> None:
        self._cells = [
            [
                0 if (neighbors := self._neighbors(row, column)) < 2 or neighbors > 3 else
                1 if neighbors == 3 else cell
                for column, cell in enumerate(cell_row)
            ]
            for row, cell_row in enumerate(self._cells)
        ]
        self.iteration += 1

    def _neighbors(self, row: int, column: int) -> int:
        row_len = len(self._cells[0])
        row_num = len(self._cells)

        return sum(
            self._cells[_row][_column]
            for _row in range(row - 1, row + 2) if 0 <= _row < row_num
            for _column in range(column - 1, column + 2) if 0 <= _column < row_len and (
                _column != column or _row != row
            )
        )
