from enum import Enum, auto
from typing import Self, cast


class Direction(Enum):
    UP = auto()
    UPRIGHT = auto()
    RIGHT = auto()
    DOWNRIGHT = auto()
    DOWN = auto()
    DOWNLEFT = auto()
    LEFT = auto()
    UPLEFT = auto()

    @property
    def opposite(self) -> Self:
        opposites = [
            (self.UP, self.DOWN),
            (self.UPRIGHT, self.DOWNLEFT),
            (self.RIGHT, self.LEFT),
            (self.DOWNRIGHT, self.UPLEFT),
        ]
        return cast(dict[Self, Self], dict(opposites + [(other, one) for one, other in opposites]))[self]


class GolCells:
    def __init__(self, cells: list[list[int]]):
        self._cells = cells

    @property
    def as_serializable(self) -> list[list[int]]:
        return self._cells

    def iterate(self) -> None:
        self._extend_with_neighboring_border_cells()

        self._cells = [
            [
                0 if (neighbors := self._neighbors(row, column)) < 2 or neighbors > 3 else
                1 if neighbors == 3 else cell
                for column, cell in enumerate(cell_row[1:-1], start=1)
            ]
            for row, cell_row in enumerate(self._cells[1:-1], start=1)
        ]

    def _extend_with_neighboring_border_cells(self) -> None:
        for cell_row in self._cells:
            cell_row.insert(0, 0)
            cell_row.append(0)

        border_row = len(self._cells[0]) * [0]

        self._cells.insert(0, border_row)
        self._cells.append(border_row)

    def _neighbors(self, row: int, column: int) -> int:
        """Must only be called for the internal cells of the border extended cell matrix."""

        return sum(
            self._cells[_row][_column]
            for _row in range(row - 1, row + 2)
            for _column in range(column - 1, column + 2) if _column != column or _row != row
        )
