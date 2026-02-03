import unittest
from datetime import datetime, timedelta, timezone

from src.db.models import Item
from src.db.session import get_session, init_engine
from src.selection.policy import select_items


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_engine("sqlite:///:memory:")
        with get_session() as session:
            now = datetime.now(timezone.utc)
            session.add_all(
                [
                    Item(source_id="s1", title="A", content_text="x", ingested_at=now, fingerprint="f1"),
                    Item(source_id="s1", title="B", content_text="x", ingested_at=now, fingerprint="f2"),
                    Item(source_id="s2", title="C", content_text="x", ingested_at=now, fingerprint="f3"),
                ]
            )
            session.commit()

    def test_select_items(self):
        with get_session() as session:
            items = select_items(
                session,
                source_ids=["s1", "s2"],
                window_days=1,
                max_items_total=2,
                per_source_limit=1,
                source_type_map={"s1": "rss", "s2": "rss"},
                weights={},
            )
            self.assertEqual(len(items), 2)


if __name__ == "__main__":
    unittest.main()
