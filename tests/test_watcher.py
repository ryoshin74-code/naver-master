import unittest
from datetime import datetime, timedelta

from naver_master import watcher
from naver_master.db import connect, init_db

FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <title>channel</title>
  <entry>
    <id>yt:video:abc123DEF45</id>
    <yt:videoId>abc123DEF45</yt:videoId>
    <title>공구 1탄! 주방용품 특가</title>
    <published>2026-06-10T12:00:00+00:00</published>
    <media:group>
      <media:title>공구 1탄! 주방용품 특가</media:title>
      <media:description>구매는 여기서!
https://smartstore.naver.com/mystore/products/123
영상 더 보기 https://youtube.com/watch?v=abc123DEF45</media:description>
    </media:group>
  </entry>
  <entry>
    <id>yt:video:xyz999XYZ99</id>
    <yt:videoId>xyz999XYZ99</yt:videoId>
    <title>공구 2탄 예고</title>
    <published>2026-06-11T00:00:00+00:00</published>
    <media:group>
      <media:title>공구 2탄 예고</media:title>
      <media:description>링크는 곧 올라옵니다. https://youtu.be/xyz999XYZ99</media:description>
    </media:group>
  </entry>
</feed>
"""


class ParseFeedTest(unittest.TestCase):
    def test_parses_entries(self):
        entries = watcher.parse_feed(FEED_XML)
        self.assertEqual([e.video_id for e in entries], ["abc123DEF45", "xyz999XYZ99"])
        self.assertEqual(entries[0].title, "공구 1탄! 주방용품 특가")
        self.assertIn("smartstore", entries[0].description)


class ExtractPurchaseUrlTest(unittest.TestCase):
    def test_picks_non_youtube_link(self):
        url = watcher.extract_purchase_url(
            "영상 https://youtu.be/abc 구매 https://smartstore.naver.com/x/1, 감사"
        )
        self.assertEqual(url, "https://smartstore.naver.com/x/1")

    def test_returns_none_when_only_youtube(self):
        self.assertIsNone(
            watcher.extract_purchase_url("https://www.youtube.com/watch?v=abc")
        )

    def test_returns_none_for_empty(self):
        self.assertIsNone(watcher.extract_purchase_url(""))
        self.assertIsNone(watcher.extract_purchase_url(None))


class ProcessEntriesTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        init_db(self.conn)
        self.entries = watcher.parse_feed(FEED_XML)

    def tearDown(self):
        self.conn.close()

    def test_registers_and_holds(self):
        registered, held = watcher.process_entries(self.conn, self.entries, 24)
        self.assertEqual(len(registered), 1)
        self.assertEqual(len(held), 1)
        self.assertEqual(registered[0]["video_id"], "abc123DEF45")
        self.assertEqual(held[0]["video_id"], "xyz999XYZ99")

        row = self.conn.execute(
            "SELECT * FROM videos WHERE video_id = 'abc123DEF45'"
        ).fetchone()
        self.assertEqual(row["status"], "detected")
        # D+1 예약: 송출 +24시간
        published = datetime.fromisoformat(row["published_at"])
        publish_at = datetime.fromisoformat(row["publish_at"])
        self.assertEqual(publish_at - published, timedelta(hours=24))

        held_row = self.conn.execute(
            "SELECT status FROM videos WHERE video_id = 'xyz999XYZ99'"
        ).fetchone()
        self.assertEqual(held_row["status"], "hold_no_link")

    def test_idempotent(self):
        watcher.process_entries(self.conn, self.entries, 24)
        registered, held = watcher.process_entries(self.conn, self.entries, 24)
        self.assertEqual(registered, [])
        self.assertEqual(held, [])
        n = self.conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        self.assertEqual(n, 2)

    def test_retry_held_releases_when_link_appears(self):
        watcher.process_entries(self.conn, self.entries, 24)
        updated_xml = FEED_XML.replace(
            "링크는 곧 올라옵니다. https://youtu.be/xyz999XYZ99",
            "구매: https://smartstore.naver.com/x/2",
        )
        released = watcher.retry_held(self.conn, watcher.parse_feed(updated_xml))
        self.assertEqual(len(released), 1)
        row = self.conn.execute(
            "SELECT status, purchase_url FROM videos WHERE video_id = 'xyz999XYZ99'"
        ).fetchone()
        self.assertEqual(row["status"], "detected")
        self.assertEqual(row["purchase_url"], "https://smartstore.naver.com/x/2")

    def test_due_videos(self):
        old_entry = watcher.FeedEntry(
            "old00000001", "지난 영상", "2026-06-01T00:00:00+00:00",
            "https://smartstore.naver.com/x/9",
        )
        watcher.process_entries(self.conn, [old_entry], 24)
        due = watcher.due_videos(self.conn)
        self.assertEqual([d["video_id"] for d in due], ["old00000001"])


if __name__ == "__main__":
    unittest.main()
