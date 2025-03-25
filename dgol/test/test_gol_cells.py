from unittest import TestCase

from dgol.cells import GolCells


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
