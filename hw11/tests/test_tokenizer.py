import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from JackCompiler import JackError, tokenize


def tokens(source):
    return [(token.kind, token.value, token.line) for token in tokenize(source)]


class TokenizerTests(unittest.TestCase):
    def test_comments_and_whitespace(self):
        source = "\n// ignored\n/* block\n   still ignored */  class Foo { }\n"
        self.assertEqual(
            tokens(source),
            [
                ("keyword", "class", 4),
                ("identifier", "Foo", 4),
                ("symbol", "{", 4),
                ("symbol", "}", 4),
            ],
        )

    def test_all_token_kinds(self):
        self.assertEqual(
            tokens("let x = -12 + ~flag;"),
            [
                ("keyword", "let", 1),
                ("identifier", "x", 1),
                ("symbol", "=", 1),
                ("symbol", "-", 1),
                ("integerConstant", "12", 1),
                ("symbol", "+", 1),
                ("symbol", "~", 1),
                ("identifier", "flag", 1),
                ("symbol", ";", 1),
            ],
        )

    def test_string_keeps_comment_markers(self):
        self.assertEqual(
            tokens('"http://a/*b*/";'),
            [("stringConstant", "http://a/*b*/", 1), ("symbol", ";", 1)],
        )

    def test_keywords_and_symbols(self):
        words = (
            "class constructor function method field static var int char boolean "
            "void true false null this let do if else while return"
        )
        self.assertTrue(all(kind == "keyword" for kind, _, _ in tokens(words)))
        symbols = "{}()[].,;+-*/&|<>=~"
        self.assertTrue(all(kind == "symbol" for kind, _, _ in tokens(symbols)))

    def test_line_numbers(self):
        self.assertEqual(
            tokens("class A {\n  var int x;\n}"),
            [
                ("keyword", "class", 1),
                ("identifier", "A", 1),
                ("symbol", "{", 1),
                ("keyword", "var", 2),
                ("keyword", "int", 2),
                ("identifier", "x", 2),
                ("symbol", ";", 2),
                ("symbol", "}", 3),
            ],
        )

    def test_invalid_source(self):
        bad_sources = [
            "@",
            "32768",
            '"unterminated',
            '"line\nbreak"',
            "/* unterminated",
        ]
        for source in bad_sources:
            with self.subTest(source=source):
                with self.assertRaises(JackError):
                    tokenize(source)


if __name__ == "__main__":
    unittest.main()
