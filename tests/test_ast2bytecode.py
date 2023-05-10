from dbge.ast2bytecode import AST2Bytecode


def example():
    return 4


class X(object):
    def example2(self):
        print(self)


def test_matching1():
    a2b = AST2Bytecode(example.__code__)

    assert len(a2b.bytecodes) == 3
    assert a2b.ast is not None
    assert len(a2b.flat_ast) == 3

    assert a2b.bytecodes[0].ast is None
    assert a2b.bytecodes[1].ast is a2b.flat_ast[2]
    assert a2b.bytecodes[2].ast is a2b.flat_ast[2]

    assert len(a2b.flat_ast[0].insts) == 0
    assert len(a2b.flat_ast[1].insts) == 0
    assert len(a2b.flat_ast[2].insts) == 2


def test_matching2():
    a2b = AST2Bytecode(X.example2.__code__)

    assert len(a2b.bytecodes) == 8
    assert a2b.ast is not None
    assert len(a2b.flat_ast) == 6

    assert a2b.bytecodes[0].ast is None
    assert a2b.bytecodes[1].ast is a2b.flat_ast[4]
    assert a2b.bytecodes[2].ast is a2b.flat_ast[5]
    assert a2b.bytecodes[3].ast is a2b.flat_ast[1]
    assert a2b.bytecodes[4].ast is a2b.flat_ast[1]
    assert a2b.bytecodes[5].ast is a2b.flat_ast[1]
    assert a2b.bytecodes[6].ast is a2b.flat_ast[1]
    assert a2b.bytecodes[7].ast is a2b.flat_ast[1]

    assert len(a2b.flat_ast[0].insts) == 0
    assert len(a2b.flat_ast[1].insts) == 5
    assert len(a2b.flat_ast[2].insts) == 0
    assert len(a2b.flat_ast[3].insts) == 0
    assert len(a2b.flat_ast[4].insts) == 1
    assert len(a2b.flat_ast[5].insts) == 1


def test_get_expr():
    a2b = AST2Bytecode(X.example2.__code__)

    assert a2b.get_bytecode(0) is a2b.bytecodes[0]
    assert a2b.get_bytecode(2) is a2b.bytecodes[1]
    assert a2b.get_bytecode(14) is a2b.bytecodes[2]
    assert a2b.get_bytecode(16) is a2b.bytecodes[3]
    assert a2b.get_bytecode(20) is a2b.bytecodes[4]
    assert a2b.get_bytecode(30) is a2b.bytecodes[5]
    assert a2b.get_bytecode(32) is a2b.bytecodes[6]
    assert a2b.get_bytecode(34) is a2b.bytecodes[7]
    assert a2b.get_bytecode(99) is None

    assert a2b.resolve_astnode(0) is None
    assert a2b.resolve_astnode(2) is a2b.flat_ast[4]
    assert a2b.resolve_astnode(34) is a2b.flat_ast[1]


def test_next_bytecode():
    a2b = AST2Bytecode(X.example2.__code__)

    assert a2b.next_bytecode(a2b.bytecodes[0]) is a2b.bytecodes[1]
    assert a2b.next_bytecode(a2b.bytecodes[1]) is a2b.bytecodes[2]
    assert a2b.next_bytecode(a2b.bytecodes[2]) is a2b.bytecodes[3]
    assert a2b.next_bytecode(a2b.bytecodes[3]) is a2b.bytecodes[4]
    assert a2b.next_bytecode(a2b.bytecodes[4]) is a2b.bytecodes[5]
    assert a2b.next_bytecode(a2b.bytecodes[5]) is a2b.bytecodes[6]
    assert a2b.next_bytecode(a2b.bytecodes[6]) is a2b.bytecodes[7]
    assert a2b.next_bytecode(a2b.bytecodes[7]) is None

def test_next_astnode():
    a2b = AST2Bytecode(X.example2.__code__)

    assert a2b.resolve_end_offset(2) == 2
    assert a2b.resolve_end_offset(14) == 14
    assert a2b.resolve_end_offset(16) == 34
