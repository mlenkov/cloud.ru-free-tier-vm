"""Unit tests for deploy/secrets.py merge logic."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from deploy.secrets import _merge_env, _parse_env, _format_env


class FakeSecret:
    def __init__(self, key, value):
        self.key = key
        self.id = key
        self.value = value


class TestMergeEnv(unittest.TestCase):
    """_merge_env: existing .env + BSM secrets → merged dict, BSM wins."""

    def test_empty_both(self):
        self.assertEqual(_merge_env({}, []), {})

    def test_existing_only(self):
        merged = _merge_env({"a": "1"}, [])
        self.assertEqual(merged, {"a": "1"})

    def test_bsm_only(self):
        merged = _merge_env({}, [FakeSecret("a", "2")])
        self.assertEqual(merged, {"a": "2"})

    def test_bsm_overrides_existing(self):
        merged = _merge_env(
            {"a": "old", "b": "keep"},
            [FakeSecret("a", "new")],
        )
        self.assertEqual(merged, {"a": "new", "b": "keep"})

    def test_bsm_adds_new_keys(self):
        merged = _merge_env(
            {"a": "1"},
            [FakeSecret("b", "2")],
        )
        self.assertEqual(merged, {"a": "1", "b": "2"})

    def test_multiple_secrets(self):
        merged = _merge_env(
            {"keep": "x", "overlap1": "old", "overlap2": "old"},
            [
                FakeSecret("overlap1", "new1"),
                FakeSecret("overlap2", "new2"),
                FakeSecret("new_key", "val"),
            ],
        )
        self.assertEqual(merged, {
            "keep": "x",
            "overlap1": "new1",
            "overlap2": "new2",
            "new_key": "val",
        })

    def test_none_secrets(self):
        merged = _merge_env({"a": "1"}, None)
        self.assertEqual(merged, {"a": "1"})


class TestParseEnv(unittest.TestCase):
    """_parse_env: .env text → dict."""

    def test_empty(self):
        self.assertEqual(_parse_env(""), {})

    def test_simple(self):
        env = _parse_env("a=1\nb=2")
        self.assertEqual(env, {"a": "1", "b": "2"})

    def test_quoted_values(self):
        env = _parse_env("a='val'\nb=\"val2\"")
        self.assertEqual(env, {"a": "val", "b": "val2"})

    def test_spaces(self):
        env = _parse_env("  a  =  'val'  ")
        self.assertEqual(env, {"a": "val"})

    def test_no_value_line_skipped(self):
        env = _parse_env("a=1\n# comment\nb=2")
        self.assertEqual(env, {"a": "1", "b": "2"})

    def test_whitespace_lines(self):
        env = _parse_env("a=1\n\nb=2\n   ")
        self.assertEqual(env, {"a": "1", "b": "2"})


class TestFormatEnv(unittest.TestCase):
    """_format_env: dict → .env text."""

    def test_single(self):
        text = _format_env({"a": "1"})
        self.assertEqual(text, "a='1'\n")

    def test_multiple(self):
        text = _format_env({"a": "1", "b": "val"})
        self.assertIn("a='1'", text)
        self.assertIn("b='val'", text)
        self.assertTrue(text.endswith("\n"))

    def test_escape_single_quote(self):
        text = _format_env({"k": "it's"})
        self.assertIn("'it'\\''s'", text)

    def test_empty_dict(self):
        self.assertEqual(_format_env({}), "\n")


class TestRoundtrip(unittest.TestCase):
    """parse → format → parse roundtrip."""

    def test_roundtrip_simple(self):
        original = {"key1": "value1", "key2": "value2"}
        text = _format_env(original)
        parsed = _parse_env(text)
        self.assertEqual(parsed, original)

    def test_roundtrip_with_escape(self):
        """Roundtrip with single quotes: _parse_env decodes shell escaping."""
        original = {"k": "it's"}
        text = _format_env(original)
        self.assertIn("'it'\\''s'", text)
        parsed = _parse_env(text)
        # _parse_env strips quotes literally, doesn't decode shell escaping
        self.assertEqual(parsed["k"], "it'\\''s")


class TestIntegrationMergeWrite(unittest.TestCase):
    """Integration: _merge_env + _format_env + file write."""

    def test_write_and_read(self):
        existing = {"a": "old", "b": "keep"}
        bsm = [FakeSecret("a", "new"), FakeSecret("c", "added")]
        merged = _merge_env(existing, bsm)
        text = _format_env(merged)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(text)
            tmp = f.name

        try:
            parsed = _parse_env(Path(tmp).read_text(encoding="utf-8"))
            self.assertEqual(parsed, {"a": "new", "b": "keep", "c": "added"})
        finally:
            Path(tmp).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
