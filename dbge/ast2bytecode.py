import ast
import dis
import inspect


class AST2Bytecode(object):
    def __init__(self, codeobj, _ast=None, _flat_ast=None, _indent=None):
        self.codeobj = codeobj
        self.sub_a2bs = []
        if _ast:
            self.ast = _ast
            self.flat_ast = _flat_ast
            self.indent = _indent
        else:
            self.ast, self.flat_ast, self.indent = self._setup_ast()
        self.bytecodes = self._setup_bytecodes()

    @staticmethod
    def match(p, other):
        return (p.lineno == other.lineno
                and p.end_lineno == other.lineno
                and p.col_offset == other.col_offset
                and p.end_col_offset == other.end_col_offset)

    def dedent_string(self, s):
        stripped = s.lstrip()
        indent = len(s) - len(stripped)
        lines = s.split("\n")
        dedented = "\n".join(l[indent:] for l in lines)
        return dedented, indent

    def _setup_ast(self):
        nodes = []
        codeobj = self.codeobj
        code, indent = self.dedent_string(inspect.getsource(codeobj))

        tree = ast.parse(code, inspect.getsourcefile(codeobj), "exec")
        for node in ast.walk(tree):
            if not hasattr(node, 'lineno'):
                continue
            node.col_offset += indent
            node.end_col_offset += indent
            node.insts = []
            nodes.append(node)

        root = tree.body[0]
        ast.increment_lineno(root, inspect.getsourcelines(codeobj)[1] - 1)
        return (root, nodes, indent)

    def _setup_bytecodes(self):
        insts = []
        codeobj = self.codeobj
        for inst in dis.get_instructions(codeobj):
            insts.append(inst)
            argval = inst.argval
            if inst.opname == "LOAD_CONST" and inspect.iscode(argval) and "<locals>" in argval.co_qualname:
                suba2b = AST2Bytecode(argval, self.ast, self.flat_ast, self.indent)
                self.sub_a2bs.append(suba2b)
            for node in self.flat_ast:
                other = dis.Positions(node.lineno, node.end_lineno, node.col_offset, node.end_col_offset)
                if self.match(inst.positions, other):
                    inst.ast = node
                    inst.mapper = self
                    node.insts.append(inst)
                    break
            else:
                inst.ast = None
        return insts

    def get_bytecode(self, offset):
        return next((x for x in self.bytecodes if x.offset == offset), None)

    def next_bytecode(self, bytecode):
        bytecodes = self.bytecodes
        try:
            index = bytecodes.index(bytecode)
            next_bytecode = bytecodes[index + 1]
            return next_bytecode
        except ValueError:
            return None
        except IndexError:
            return None

    def resolve_astnode(self, offset):
        bc = self.get_bytecode(offset)
        return bc.ast if bc else None

    def resolve_end_offset(self, offset):
        bc = self.get_bytecode(offset)
        node = bc.ast
        insts = node.insts if node else [None]
        return insts[-1].offset if insts[-1] else offset

    def all_a2b(self):
        yield self
        for sub in self.sub_a2bs:
            yield from sub.all_a2b()