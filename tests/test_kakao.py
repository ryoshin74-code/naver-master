import unittest

from naver_master.kakao import parse_code, split_text


class SplitTextTest(unittest.TestCase):
    def test_short_text_single_chunk(self):
        self.assertEqual(split_text("안녕하세요"), ["안녕하세요"])

    def test_splits_on_line_boundaries(self):
        lines = [f"{i}번째 줄 " + "가" * 30 for i in range(12)]
        chunks = split_text("\n".join(lines), limit=100)
        self.assertTrue(all(len(c) <= 100 for c in chunks))
        # 내용 보존 (줄 단위)
        rejoined = "\n".join(chunks).splitlines()
        self.assertEqual([l for l in rejoined if l], lines)

    def test_hard_splits_long_single_line(self):
        chunks = split_text("가" * 450, limit=200)
        self.assertEqual([len(c) for c in chunks], [200, 200, 50])

    def test_empty(self):
        self.assertEqual(split_text(""), [""])


class ParseCodeTest(unittest.TestCase):
    def test_parses_full_redirect_url(self):
        code = parse_code("http://localhost:8889/?code=AbC123&state=x")
        self.assertEqual(code, "AbC123")

    def test_accepts_bare_code(self):
        self.assertEqual(parse_code("  AbC123  "), "AbC123")


if __name__ == "__main__":
    unittest.main()
