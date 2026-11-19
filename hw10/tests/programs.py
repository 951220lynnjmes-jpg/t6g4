"""Small .vm programs shared by the translator / emulator / integration tests."""

SIMPLE_ADD = """\
push constant 7
push constant 8
add
"""

ARITHMETIC = """\
push constant 10
push constant 3
add
push constant 10
push constant 3
sub
push constant 7
neg
push constant 12
not
push constant 6
push constant 4
and
push constant 6
push constant 4
or
push constant 5
push constant 5
eq
push constant 5
push constant 6
eq
push constant 6
push constant 5
gt
push constant 5
push constant 6
lt
"""

MEMORY_ACCESS = """\
push constant 100
pop pointer 0
push constant 200
pop pointer 1
push constant 42
pop this 3
push constant 24
pop that 2
push this 3
push that 2
add
push constant 7
pop temp 5
push temp 5
add
push constant 9
pop static 0
push static 0
add
"""

PROGRAM_FLOW = """\
push constant 0
pop temp 0
label LOOP
push temp 0
push constant 1
add
pop temp 0
push temp 0
push constant 5
lt
if-goto LOOP
goto DONE
label DONE
push temp 0
"""

FACTORIAL = """\
push constant 5
call Fact.compute 1
label END
goto END

function Fact.compute 1
push argument 0
push constant 1
eq
if-goto BASE
push argument 0
push argument 0
push constant 1
sub
call Fact.compute 1
call Math.multiply 2
return
label BASE
push constant 1
return

function Math.multiply 0
push constant 0
pop temp 0
push argument 1
pop temp 1
label LOOP
push temp 1
if-goto BODY
goto DONE
label BODY
push temp 0
push argument 0
add
pop temp 0
push temp 1
push constant 1
sub
pop temp 1
goto LOOP
label DONE
push temp 0
return
"""

# Multi-file programs: the bootstrap calls Sys.init and the sentinel return
# address makes the emulator halt after Sys.init returns.
MAIN_UTILS = [
    (
        "Main.vm",
        """\
function Main.main 0
push constant 5
call Utils.twice 1
push constant 9
call Utils.twice 1
add
return
""",
    ),
    (
        "Utils.vm",
        """\
function Utils.twice 0
push argument 0
push argument 0
add
return
""",
    ),
    (
        "Sys.vm",
        """\
function Sys.init 0
call Main.main 0
label DONE
goto DONE
""",
    ),
]

STATIC_FILES = [
    (
        "Class1.vm",
        """\
function Class1.run 0
push constant 123
pop static 0
push static 0
return
""",
    ),
    (
        "Class2.vm",
        """\
function Class2.run 0
push constant 456
pop static 0
push static 0
return
""",
    ),
    (
        "Sys.vm",
        """\
function Sys.init 0
call Class1.run 0
call Class2.run 0
label DONE
goto DONE
""",
    ),
]

SCOPE_FILES = [
    (
        "A.vm",
        """\
function A.run 1
label LOOP
push local 0
push constant 1
add
pop local 0
push local 0
push constant 3
lt
if-goto LOOP
push local 0
return
""",
    ),
    (
        "B.vm",
        """\
function B.run 1
push constant 0
pop local 0
label LOOP
push local 0
push constant 1
add
pop local 0
push local 0
push constant 2
lt
if-goto LOOP
push local 0
return
""",
    ),
    (
        "Sys.vm",
        """\
function Sys.init 0
call A.run 0
call B.run 0
label DONE
goto DONE
""",
    ),
]

# Sys.init never returns here, so both machines are stepped a fixed number of
# times and compared once the DONE loop has been reached.
INFINITE_BOOTSTRAP = [
    (
        "Loop.vm",
        """\
function Loop.run 2
label LOOP
push local 0
push constant 1
add
pop local 0
push local 0
push constant 4
lt
if-goto LOOP
push local 0
return
""",
    ),
    (
        "Sys.vm",
        """\
function Sys.init 0
call Loop.run 0
label DONE
goto DONE
""",
    ),
]
