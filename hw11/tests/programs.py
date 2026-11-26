"""Small .jack programs shared by the tokenizer / compiler / integration tests."""

POINT = """\
class Point {
    field int x, y;
    static int count;

    constructor Point new(int ax, int ay) {
        let x = ax;
        let y = ay;
        let count = count + 1;
        return this;
    }

    method int sum() {
        return x + y;
    }
}
"""

EXPRESSIONS = """\
class Expr {
    function void main() {
        var int a;
        let a = (2 + 3) * 4 / 2;
        do Output.printString("Hi!");
        return;
    }
}
"""

CONTROL = """\
class Flow {
    function void main() {
        var int i;
        let i = 0;
        while (i < 3) {
            if (i = 1) {
                let i = i + 2;
            } else {
                let i = i + 1;
            }
        }
        return;
    }
}
"""

ARRAYS = """\
class Arrays {
    function void main() {
        var Array a;
        let a = Array.new(2);
        let a[0] = 7;
        let a[1] = a[0] + 1;
        return;
    }
}
"""

CALLS = """\
class Calls {
    field int value;

    constructor Calls new(int v) {
        let value = v;
        return this;
    }

    method int get() {
        return value;
    }

    method int twice() {
        return get() + get();
    }

    function int add(int a, int b) {
        return a + b;
    }

    function int run() {
        var Calls c;
        let c = Calls.new(4);
        return c.get() + Calls.add(2, 3);
    }
}
"""

CALC = """\
class Calc {
    function int main() {
        var int a;
        let a = 7;
        return a + 3;
    }
}
"""

EMPTY = """\
class Empty {
    function void main() {
    }
}
"""

BOOTSTRAP = """\
class Sys {
    function void init() {
        do Sys.run();
        return;
    }

    function int run() {
        var int a;
        let a = 7;
        return a + 3;
    }
}
"""
