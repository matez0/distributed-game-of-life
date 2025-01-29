class GolCells:
    def __init__(self, cells: list[list[int]]):
        self._cells = cells

    @property
    def as_serializable(self) -> list[list[int]]:
        return self._cells

    def iterate(self) -> None:
        self._cells = [
            [
                0 if (neighbors := self._neighbors(row, column)) < 2 or neighbors > 3 else
                1 if neighbors == 3 else cell
                for column, cell in enumerate(cell_row)
            ]
            for row, cell_row in enumerate(self._cells)
        ]

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
