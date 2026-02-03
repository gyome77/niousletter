import unittest
from src.ingestion.dedupe import dedupe_items
from src.ingestion.normalise import ItemData
from src.utils.time import now_utc


class DedupeTests(unittest.TestCase):
    def test_dedupe_items(self):
        now = now_utc()
        items = [
            ItemData("s1", "A", "text", "url1", None, now, [], "fp1"),
            ItemData("s1", "B", "text", "url1", None, now, [], "fp1"),
            ItemData("s2", "C", "text", "url2", None, now, [], "fp2"),
        ]
        result = dedupe_items(items)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
