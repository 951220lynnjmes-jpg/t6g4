import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from VMTranslator import (
    CodeWriter,
    Command,
    Parser,
    VMError,
    base_name,
    translate,
    translate_file,
)

from programs import MAIN_UTILS, SCOPE_FILES, SIMPLE_ADD


def code(source, bootstrap=None):
    """Translate to assembly, keeping only real Hack instructions."""
    files = [("Test.vm", source)] if isinstance(source, str) else source
    lines = translate(files, bootstrap=bootstrap).splitlines()
    return [line for line in lines if line and not line.lstrip().startswith("//")]


class ParserTests(unittest.TestCase):
    def test_comments_and_whitespace(self):
        commands = Parser("\n  // only a comment\n\tpush   constant  7  // value\n").commands
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].type, "push")
        self.assertEqual(commands[0].arg1, "constant")
        self.assertEqual(commands[0].arg2, 7)

    def test_base_name_sanitizes_symbols(self):
        self.assertEqual(base_name("dir/Foo.vm"), "Foo")
        self.assertEqual(base_name("foo.bar.vm"), "foo.bar")
        self.assertEqual(base_name("my class.vm"), "my_class")


class TranslatorTests(unittest.TestCase):
    def test_simple_add(self):
        self.assertEqual(
            code(SIMPLE_ADD),
            [
                "@7", "D=A", "@SP", "A=M", "M=D", "@SP", "M=M+1",
                "@8", "D=A", "@SP", "A=M", "M=D", "@SP", "M=M+1",
                "@SP", "AM=M-1", "D=M", "A=A-1", "M=D+M",
            ],
        )

    def test_binary_unary_arithmetic(self):
        self.assertEqual(code("add"), ["@SP", "AM=M-1", "D=M", "A=A-1", "M=D+M"])
        self.assertEqual(code("sub"), ["@SP", "AM=M-1", "D=M", "A=A-1", "M=M-D"])
        self.assertEqual(code("and"), ["@SP", "AM=M-1", "D=M", "A=A-1", "M=D&M"])
        self.assertEqual(code("or"), ["@SP", "AM=M-1", "D=M", "A=A-1", "M=D|M"])
        self.assertEqual(code("neg"), ["@SP", "A=M-1", "M=-M"])
        self.assertEqual(code("not"), ["@SP", "A=M-1", "M=!M"])

    def test_comparison_uses_unique_labels(self):
        output = code("eq\ngt\nlt")
        self.assertIn("@TRUE_0", output)
        self.assertIn("D;JEQ", output)
        self.assertIn("@TRUE_1", output)
        self.assertIn("D;JGT", output)
        self.assertIn("@TRUE_2", output)
        self.assertIn("D;JLT", output)
        self.assertEqual(output.count("(TRUE_0)"), 1)
        self.assertEqual(output.count("(TRUE_1)"), 1)
        self.assertEqual(output.count("(TRUE_2)"), 1)
        self.assertEqual(output[0:10], [
            "@SP", "AM=M-1", "D=M", "A=A-1", "D=M-D",
            "@TRUE_0", "D;JEQ", "@SP", "A=M-1", "M=0",
        ])

    def test_push_indirect_and_temp_pointer_static(self):
        self.assertEqual(
            code("push local 2"),
            ["@2", "D=A", "@LCL", "A=D+M", "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1"],
        )
        self.assertEqual(
            code("push temp 7"),
            ["@12", "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1"],
        )
        self.assertEqual(
            code("push pointer 1"),
            ["@THAT", "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1"],
        )
        self.assertEqual(
            code([("Foo.vm", "push static 3")]),
            ["@Foo.3", "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1"],
        )

    def test_pop_uses_r13_for_address(self):
        self.assertEqual(
            code("pop argument 4"),
            [
                "@4", "D=A", "@ARG", "D=D+M", "@R13", "M=D",
                "@SP", "AM=M-1", "D=M", "@R13", "A=M", "M=D",
            ],
        )
        self.assertEqual(
            code("pop temp 5"),
            ["@SP", "AM=M-1", "D=M", "@10", "M=D"],
        )
        self.assertEqual(
            code("pop pointer 0"),
            ["@SP", "AM=M-1", "D=M", "@THIS", "M=D"],
        )

    def test_program_flow(self):
        self.assertEqual(code("label LOOP"), ["(LOOP)"])
        self.assertEqual(code("goto LOOP"), ["@LOOP", "0;JMP"])
        self.assertEqual(
            code("if-goto LOOP"), ["@SP", "AM=M-1", "D=M", "@LOOP", "D;JNE"]
        )

    def test_function_call_return(self):
        expected = [
            "(Foo.f)",
            "@SP", "A=M", "M=0", "@SP", "M=M+1",
            "@SP", "A=M", "M=0", "@SP", "M=M+1",
            "@Bar.g$ret.0", "D=A", "@SP", "A=M", "M=D", "@SP", "M=M+1",
            "@LCL", "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1",
            "@ARG", "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1",
            "@THIS", "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1",
            "@THAT", "D=M", "@SP", "A=M", "M=D", "@SP", "M=M+1",
            "@SP", "D=M", "@5", "D=D-A", "@1", "D=D-A", "@ARG", "M=D",
            "@SP", "D=M", "@LCL", "M=D",
            "@Bar.g", "0;JMP", "(Bar.g$ret.0)",
            "@LCL", "D=M", "@R13", "M=D",
            "@5", "A=D-A", "D=M", "@R14", "M=D",
            "@SP", "AM=M-1", "D=M", "@ARG", "A=M", "M=D",
            "@ARG", "D=M+1", "@SP", "M=D",
            "@R13", "AM=M-1", "D=M", "@THAT", "M=D",
            "@R13", "AM=M-1", "D=M", "@THIS", "M=D",
            "@R13", "AM=M-1", "D=M", "@ARG", "M=D",
            "@R13", "AM=M-1", "D=M", "@LCL", "M=D",
            "@R14", "A=M", "0;JMP",
        ]
        self.assertEqual(code("function Foo.f 2\ncall Bar.g 1\nreturn"), expected)

    def test_bootstrap_and_unique_return_labels(self):
        output = code(MAIN_UTILS)
        self.assertEqual(
            output[:4], ["@256", "D=A", "@SP", "M=D"]
        )
        self.assertIn("@Sys.init$ret.0", output)
        self.assertIn("(Sys.init$ret.0)", output)
        self.assertIn("(Utils.twice$ret.1)", output)
        self.assertIn("(Utils.twice$ret.2)", output)
        self.assertIn("(Main.main$ret.3)", output)

    def test_labels_are_scoped_across_files(self):
        output = code(SCOPE_FILES)
        self.assertIn("(A.run$LOOP)", output)
        self.assertIn("(B.run$LOOP)", output)
        self.assertNotIn("(LOOP)", output)

    def test_static_symbols_are_per_file(self):
        output = code([("A.vm", "push static 0"), ("B.vm", "push static 0")])
        self.assertIn("@A.0", output)
        self.assertIn("@B.0", output)

    def test_translate_file_single_and_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            single = root / "Single.vm"
            single.write_text(SIMPLE_ADD, encoding="utf-8")
            output, count = translate_file(single)
            self.assertEqual(output, root / "Single.asm")
            self.assertNotIn("@256", output.read_text(encoding="utf-8"))
            self.assertEqual(count, 19)

            multi = root / "project"
            multi.mkdir()
            (multi / "Main.vm").write_text("push constant 1", encoding="utf-8")
            (multi / "Sys.vm").write_text("return", encoding="utf-8")
            output, _ = translate_file(multi)
            self.assertEqual(output, multi / "project.asm")
            self.assertIn("@256", output.read_text(encoding="utf-8"))

    def test_invalid_source(self):
        bad_sources = [
            "nop",
            "push constant",
            "push foo 1",
            "push constant x",
            "pop constant 1",
            "push temp 8",
            "pop pointer 2",
            "push local 32768",
            "label 1LOOP",
            "goto",
            "function f",
            "call f x",
            "add 1",
            "return 1",
        ]
        for source in bad_sources:
            with self.subTest(source=source):
                with self.assertRaises(VMError):
                    translate([("Bad.vm", source)])

    def test_writer_rejects_unknown_command(self):
        with self.assertRaises(VMError):
            CodeWriter().write(Command(1, "bogus", "bogus"))


if __name__ == "__main__":
    unittest.main()
