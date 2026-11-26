import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from JackCompiler import (
    JackError,
    SymbolTable,
    VMWriter,
    compile_file,
    compile_path,
    compile_source,
)
from programs import ARRAYS, CALC, CALLS, CONTROL, EMPTY, EXPRESSIONS, POINT


def vm(source):
    return compile_source(source).splitlines()


class SymbolTableTests(unittest.TestCase):
    def test_kinds_segments_and_indices(self):
        table = SymbolTable()
        table.define("count", "int", "static")
        table.define("point", "Point", "field")
        table.define("ax", "int", "arg")
        table.define("i", "int", "var")
        table.define("j", "int", "var")

        self.assertEqual([table.count(kind) for kind in ("static", "field", "arg", "var")], [1, 1, 1, 2])
        self.assertEqual(table.kind_of("point"), "field")
        self.assertEqual(table.type_of("point"), "Point")
        self.assertEqual(table.index_of("j"), 1)
        self.assertEqual(table.segment_of("count"), "static")
        self.assertEqual(table.segment_of("point"), "this")
        self.assertEqual(table.segment_of("ax"), "argument")
        self.assertEqual(table.segment_of("i"), "local")
        self.assertEqual(table.kind_of("missing"), "")

    def test_subroutine_reset_keeps_class_scope(self):
        table = SymbolTable()
        table.define("count", "int", "static")
        table.define("x", "int", "field")
        table.define("arg", "int", "arg")
        table.define("local", "int", "var")
        table.reset_subroutine()
        self.assertEqual((table.count("static"), table.count("field")), (1, 1))
        self.assertEqual((table.count("arg"), table.count("var")), (0, 0))

    def test_duplicate_symbol(self):
        table = SymbolTable()
        table.define("x", "int", "static")
        with self.assertRaises(JackError):
            table.define("x", "int", "static")


class VMWriterTests(unittest.TestCase):
    def test_all_commands(self):
        writer = VMWriter()
        writer.write_function("A.f", 1)
        writer.write_push("constant", 7)
        writer.write_pop("local", 0)
        writer.write_arithmetic("add")
        writer.write_label("LOOP")
        writer.write_goto("LOOP")
        writer.write_if("LOOP")
        writer.write_call("Math.multiply", 2)
        writer.write_return()
        self.assertEqual(
            writer.lines,
            [
                "function A.f 1",
                "push constant 7",
                "pop local 0",
                "add",
                "label LOOP",
                "goto LOOP",
                "if-goto LOOP",
                "call Math.multiply 2",
                "return",
            ],
        )
        self.assertEqual(str(writer), "\n".join(writer.lines) + "\n")


class CompilerTests(unittest.TestCase):
    def test_fields_statics_and_subroutine_setup(self):
        self.assertEqual(
            vm(POINT),
            [
                "function Point.new 0",
                "push constant 2",
                "call Memory.alloc 1",
                "pop pointer 0",
                "push argument 0",
                "pop this 0",
                "push argument 1",
                "pop this 1",
                "push static 0",
                "push constant 1",
                "add",
                "pop static 0",
                "push pointer 0",
                "return",
                "function Point.sum 0",
                "push argument 0",
                "pop pointer 0",
                "push this 0",
                "push this 1",
                "add",
                "return",
            ],
        )

    def test_expressions_and_string_constants(self):
        self.assertEqual(
            vm(EXPRESSIONS),
            [
                "function Expr.main 1",
                "push constant 2",
                "push constant 3",
                "add",
                "push constant 4",
                "call Math.multiply 2",
                "push constant 2",
                "call Math.divide 2",
                "pop local 0",
                "push constant 3",
                "call String.new 1",
                "push constant 72",
                "call String.appendChar 2",
                "push constant 105",
                "call String.appendChar 2",
                "push constant 33",
                "call String.appendChar 2",
                "call Output.printString 1",
                "pop temp 0",
                "push constant 0",
                "return",
            ],
        )

    def test_control_flow_labels(self):
        self.assertEqual(
            vm(CONTROL),
            [
                "function Flow.main 1",
                "push constant 0",
                "pop local 0",
                "label WHILE_EXP0",
                "push local 0",
                "push constant 3",
                "lt",
                "not",
                "if-goto WHILE_END0",
                "push local 0",
                "push constant 1",
                "eq",
                "if-goto IF_TRUE0",
                "goto IF_FALSE0",
                "label IF_TRUE0",
                "push local 0",
                "push constant 2",
                "add",
                "pop local 0",
                "goto IF_END0",
                "label IF_FALSE0",
                "push local 0",
                "push constant 1",
                "add",
                "pop local 0",
                "label IF_END0",
                "goto WHILE_EXP0",
                "label WHILE_END0",
                "push constant 0",
                "return",
            ],
        )

    def test_array_read_and_write(self):
        self.assertEqual(
            vm(ARRAYS),
            [
                "function Arrays.main 1",
                "push constant 2",
                "call Array.new 1",
                "pop local 0",
                "push constant 0",
                "push local 0",
                "add",
                "push constant 7",
                "pop temp 0",
                "pop pointer 1",
                "push temp 0",
                "pop that 0",
                "push constant 1",
                "push local 0",
                "add",
                "push constant 0",
                "push local 0",
                "add",
                "pop pointer 1",
                "push that 0",
                "push constant 1",
                "add",
                "pop temp 0",
                "pop pointer 1",
                "push temp 0",
                "pop that 0",
                "push constant 0",
                "return",
            ],
        )

    def test_call_arity_and_implicit_this(self):
        lines = vm(CALLS)
        self.assertIn("call Calls.get 1", lines)
        self.assertIn("call Calls.add 2", lines)
        self.assertIn("call Calls.new 1", lines)
        self.assertEqual(
            lines[lines.index("function Calls.twice 0"):lines.index("function Calls.add 0")],
            [
                "function Calls.twice 0",
                "push argument 0",
                "pop pointer 0",
                "push pointer 0",
                "call Calls.get 1",
                "push pointer 0",
                "call Calls.get 1",
                "add",
                "return",
            ],
        )
        self.assertEqual(
            lines[lines.index("function Calls.run 1"):],
            [
                "function Calls.run 1",
                "push constant 4",
                "call Calls.new 1",
                "pop local 0",
                "push local 0",
                "call Calls.get 1",
                "push constant 2",
                "push constant 3",
                "call Calls.add 2",
                "add",
                "return",
            ],
        )

    def test_missing_return_gets_default_zero(self):
        self.assertEqual(vm(EMPTY), ["function Empty.main 0", "push constant 0", "return"])

    def test_invalid_source(self):
        bad_sources = [
            "",
            "class {}",
            "class A { function void f( { return; } }",
            "class A { function void f() { let z = 1; return; } }",
            "class A { function void f() { return } }",
            "class A { function void f() { do Output.printInt(1) return; } }",
            "class A { function void f() { let x = @; return; } }",
            "class A { function void f() { if (1) { return; } }",
        ]
        for source in bad_sources:
            with self.subTest(source=source):
                with self.assertRaises(JackError):
                    compile_source(source)


class FileTests(unittest.TestCase):
    def test_compile_file_default_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Calc.jack"
            source.write_text(CALC, encoding="utf-8")
            output = compile_file(source)
            self.assertEqual(output, root / "Calc.vm")
            self.assertEqual(output.read_text(encoding="utf-8"), compile_source(CALC))

    def test_compile_path_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / "B.jack").write_text(POINT, encoding="utf-8")
            (project / "A.jack").write_text(CALC, encoding="utf-8")
            outputs = compile_path(project, root / "vm")
            self.assertEqual([item.name for item in outputs], ["A.vm", "B.vm"])
            self.assertTrue(all(item.exists() for item in outputs))


if __name__ == "__main__":
    unittest.main()
