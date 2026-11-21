import unittest
from core import led_matrix as M

class AdjustmentNumberTests(unittest.TestCase):
    def test_brake_bias_excluded(self):
        self.assertNotIn('bb', M.ADJUSTMENTS)
        self.assertNotIn('bb', M.normalized({'adjustment_enabled': {'bb': True}})['adjustment_enabled'])
        self.assertNotIn('bb', M.adjustment_values({'live': True, 'valid': True, 't': {'brake_bias': 55.8}}))

    def test_numeric_display(self):
        for key in M.ADJUSTMENTS:
            for n in (0, 4, 9, 10, 55, 99):
                rows = M.adjustment_image(key, n)
                self.assertEqual(len(rows), 8)
                self.assertTrue(any(rows))
                self.assertTrue(all(0 <= r <= 255 for r in rows))
        self.assertEqual(M.adjustment_image('tc', 4), M.glyph('4'))
        self.assertEqual(M.adjustment_image('abs', 55), M.adjustment_image('map', 55))

    def test_bb_cannot_render(self):
        with self.assertRaises(ValueError):
            M.adjustment_image('bb', 55.8)
