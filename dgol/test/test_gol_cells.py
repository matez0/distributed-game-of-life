from unittest import TestCase

from dgol.cells import Direction, GolCells


class TestGolCells(TestCase):
    def test_serializable_data_can_be_retrieved(self):
        cells = [
            [1, 2, 3],
            [4, 5, 6],
            [7, 8, 9],
        ]

        self.assertEqual(GolCells(cells).as_serializable, cells)

    def test_cells_with_less_than_2_alive_neighbors_shall_die(self):
        cells = GolCells(
            [
                [1, 0, 0, 1],
                [1, 0, 0, 0],
                [0, 0, 0, 0],
            ]
        )

        cells.iterate()

        self.assertEqual(cells.as_serializable, [[0] * 4] * 3)

    def test_alive_cells_with_2_or_3_alive_neighbors_shall_stay_alive(self):
        cells = GolCells(
            [
                [0, 1, 1],
                [1, 0, 1],
                [0, 1, 0],
            ]
        )

        cells.iterate()

        self.assertEqual(
            cells.as_serializable,
            [
                [0, 1, 1],
                [1, 0, 1],
                [0, 1, 0],
            ],
        )

    def test_alive_cells_with_more_than_3_alive_neighbors_shall_die(self):
        cells = GolCells(
            [
                [1, 1, 1],
                [1, 0, 1],
                [1, 1, 1],
            ]
        )

        cells.iterate()

        self.assertEqual(
            cells.as_serializable,
            [
                [1, 0, 1],
                [0, 0, 0],
                [1, 0, 1],
            ],
        )

    def test_dead_cells_with_3_alive_neighbors_shall_be_alive(self):
        cells = GolCells(
            [
                [0, 1, 0],
                [1, 0, 1],
                [0, 0, 0],
            ]
        )

        cells.iterate()

        self.assertEqual(
            cells.as_serializable,
            [
                [0, 1, 0],
                [0, 1, 0],
                [0, 0, 0],
            ],
        )

    def test_neighboring_borders_are_tanken_into_account(self):
        cases = [
            (
                "alive corners",
                {
                    Direction.UPRIGHT: [1],
                    Direction.DOWNRIGHT: [1],
                    Direction.DOWNLEFT: [1],
                    Direction.UPLEFT: [1],
                },
                [
                    [1, 0, 1],
                    [0, 1, 0],
                    [1, 0, 1],
                ],
                [
                    [1, 1, 1],
                    [1, 0, 1],
                    [1, 1, 1],
                ],
            ),
            (
                "alive sides",
                {
                    Direction.UP: [1, 1, 1],
                    Direction.RIGHT: [1, 1, 1],
                    Direction.DOWN: [1, 1, 1],
                    Direction.LEFT: [1, 1, 1],
                },
                [
                    [0, 0, 0],
                    [0, 0, 0],
                    [0, 0, 0],
                ],
                [
                    [0, 1, 0],
                    [1, 0, 1],
                    [0, 1, 0],
                ],
            ),
            (
                "alive around corners",
                {
                    Direction.UP: [1, 0, 1],
                    Direction.UPRIGHT: [1],
                    Direction.RIGHT: [1, 0, 1],
                    Direction.DOWNRIGHT: [1],
                    Direction.DOWN: [1, 0, 1],
                    Direction.DOWNLEFT: [1],
                    Direction.LEFT: [1, 0, 1],
                    Direction.UPLEFT: [1],
                },
                [
                    [0, 0, 0],
                    [0, 0, 0],
                    [0, 0, 0],
                ],
                [
                    [1, 0, 1],
                    [0, 0, 0],
                    [1, 0, 1],
                ],
            ),
        ]

        for description, neighboring_borders, initial_cells, iterated_cells in cases:
            with self.subTest(case=description):
                cells = GolCells(initial_cells)

                cells.iterate(neighboring_borders=neighboring_borders)

                self.assertEqual(cells.as_serializable, iterated_cells)

    def test_border_cells_can_be_retrieved(self):
        cells = GolCells(
            [
                [1, 2, 3],
                [4, 5, 6],
                [7, 8, 9],
            ]
        )

        for direction, border_cells in {
            Direction.UP: [1, 2, 3],
            Direction.UPRIGHT: [3],
            Direction.RIGHT: [3, 6, 9],
            Direction.DOWNRIGHT: [9],
            Direction.DOWN: [7, 8, 9],
            Direction.DOWNLEFT: [7],
            Direction.LEFT: [1, 4, 7],
            Direction.UPLEFT: [1],
        }.items():
            with self.subTest(direction=direction):
                self.assertEqual(cells.border_at(direction), border_cells)
