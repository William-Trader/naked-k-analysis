import unittest

from nakedk.structure import label, structure, zigzag


class TestStructure(unittest.TestCase):
    def test_zigzag_alternates(self):
        highs = [10, 12, 11, 9, 8, 10, 13, 12, 14]
        lows = [9, 11, 10, 8, 7, 9, 12, 11, 13]
        piv = zigzag(highs, lows, atr=1.0, mult=0.5)
        self.assertGreaterEqual(len(piv), 2)
        kinds = [p["kind"] for p in piv]
        for a, b in zip(kinds, kinds[1:]):
            self.assertNotEqual(a, b)

    def test_labels(self):
        piv = [{"i": 0, "p": 10, "kind": "H"}, {"i": 1, "p": 8, "kind": "L"},
               {"i": 2, "p": 12, "kind": "H"}, {"i": 3, "p": 9, "kind": "L"}]
        out = label(piv)
        self.assertEqual(out[2]["label"], "HH")
        self.assertEqual(out[3]["label"], "HL")

    def test_structure_keys(self):
        ks = []
        price = 100.0
        for i in range(60):
            price += 1.0 if (i // 10) % 2 == 0 else -0.8
            ks.append([i, str(price), str(price + 1.5), str(price - 1.5), str(price), "100"])
        s = structure(ks)
        self.assertIn(s["state"], ("up", "down", "range", "transition"))
        self.assertIn("levels", s)
        self.assertGreaterEqual(len(s["swings"]), 1)


if __name__ == "__main__":
    unittest.main()
