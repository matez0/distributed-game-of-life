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

    def iterate(self, neighboring_borders: dict[Direction, list[int]] | None = None) -> None:
        self._extend_with_neighboring_border_cells(neighboring_borders or {})

        self._cells = [
            [
                0 if (neighbors := self._neighbors(row, column)) < 2 or neighbors > 3 else
                1 if neighbors == 3 else cell
                for column, cell in enumerate(cell_row[1:-1], start=1)
            ]
            for row, cell_row in enumerate(self._cells[1:-1], start=1)
        ]

    def _extend_with_neighboring_border_cells(self, neighboring_borders: dict[Direction, list[int]]) -> None:
        left_border = neighboring_borders.get(Direction.LEFT, [0] * len(self._cells))
        right_border = neighboring_borders.get(Direction.RIGHT, [0] * len(self._cells))
        upper_border_row = (
            neighboring_borders.get(Direction.UPLEFT, [0])
            + neighboring_borders.get(Direction.UP, [0] * len(self._cells[0]))
            + neighboring_borders.get(Direction.UPRIGHT, [0])
        )
        down_border_row = (
            neighboring_borders.get(Direction.DOWNLEFT, [0])
            + neighboring_borders.get(Direction.DOWN, [0] * len(self._cells[0]))
            + neighboring_borders.get(Direction.DOWNRIGHT, [0])
        )

        for cell_row, left_border_cell, right_border_cell in zip(self._cells, left_border, right_border):
            cell_row.insert(0, left_border_cell)
            cell_row.append(right_border_cell)

        self._cells.insert(0, upper_border_row)
        self._cells.append(down_border_row)

    def _neighbors(self, row: int, column: int) -> int:
        """Must only be called for the internal cells of the border extended cell matrix."""

        return sum(
            self._cells[_row][_column]
            for _row in range(row - 1, row + 2)
            for _column in range(column - 1, column + 2) if _column != column or _row != row
        )

    def border_at(self, direction: Direction) -> list[int]:
        match direction:
            case Direction.UP: return self._cells[0]
            case Direction.UPRIGHT: return self._cells[0][-1:]
            case Direction.RIGHT: return [row[-1] for row in self._cells]
            case Direction.DOWNRIGHT: return self._cells[-1][-1:]
            case Direction.DOWN: return self._cells[-1]
            case Direction.DOWNLEFT: return self._cells[-1][:1]
            case Direction.LEFT: return [row[0] for row in self._cells]
            case Direction.UPLEFT: return self._cells[0][:1]
