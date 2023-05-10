import sys
import dis
import ipdb
import ast
import inspect
from .frame_access import frame_access
from .interactive import select_astnode


def set_trace():
    DbgE().set_trace(inspect.currentframe().f_back)


class DbgE(ipdb.__main__._get_debugger_cls()):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.curbytecode = None
        self.stopbytecodeno = -1
        self.framea2b = {}
        self.forced = None
        self.codeobj_registry = {}

    # Copy/modified from Pdb
    def set_trace(self, frame=None):
        """Start debugging from frame.

        If frame is not specified, debugging starts from caller's frame.
        """
        if frame is None:
            frame = sys._getframe().f_back
        self.reset()

        self.setup_frame_ast2bytecode(frame)

        while frame:
            frame.f_trace = self.trace_dispatch
            frame.f_trace_opcodes = True
            self.botframe = frame
            frame = frame.f_back
        self.set_step()
        sys.settrace(self.trace_dispatch)

    def trace_dispatch(self, frame, event, arg):
        if self.quitting:
            return # None
        if event == 'opcode':
            return self.dispatch_opcode(frame)
        return super().trace_dispatch(frame, event, arg)

    def dispatch_opcode(self, frame):
        a2b: AST2Bytecode = self.framea2b[frame]
        bytecode = a2b.get_bytecode(offset=frame.f_lasti)
        self.curbytecode = bytecode
        self.user_opcode(frame, bytecode)
        return self.trace_dispatch

    def user_opcode(self, frame, bytecode: dis.Instruction):
        if self.stopbytecodeno >= 0:
            print(f"Current stack top:       {frame_access.peek_topstack(frame)}")
            print(f"Next bytecode:           {bytecode.opcode} {bytecode.opname}\t(offset={bytecode.offset})")
            if bytecode.ast:
                print(f"AST representation:      '{ast.unparse(bytecode.ast)}'")
        if self.stop_bytecode_here(frame):
            self.stopbytecodeno = -1
            self.interaction(frame, None)

    def user_call(self, frame, arg):
        frame.f_trace_opcodes = True  # Activate trace opcode in new frame
        self.setup_frame_ast2bytecode(frame)
        super().user_call(frame, arg)

    def _set_stopinfo_bytecode(self, stopframe, returnframe, offset_stop=0):
        self.stopframe = stopframe
        self.returnframe = returnframe
        self.quitting = False
        self.stopbytecodeno = offset_stop
        self.stoplineno = -1

    def do_stepi(self, arg):
        index = 0
        if arg:
            index = int(arg) + self.curframe.f_lasti
        self._set_stopinfo_bytecode(self.curframe, None, offset_stop=index)
        return 1

    def do_stepe(self, arg):
        frame = self.curframe
        a2b: AST2Bytecode = self.framea2b[frame]
        stop_offset = a2b.resolve_end_offset(frame.f_lasti)
        self._set_stopinfo_bytecode(self.curframe, None, offset_stop=stop_offset)
        return 1

    def do_forcetopstack(self, arg):
        if not arg:
            print("Missing argument")
            return
        obj = eval(arg, self.curframe.f_globals, self.curframe.f_locals)
        self.curframe.f_globals['__eval__'] = obj  # Make a strong ref to the object
        self.forced = obj  # Make a strong ref to the object
        print(f"Replace top stack:    {frame_access.peek_topstack(self.curframe)}")
        frame_access.change_topstack(self.curframe, obj)
        print(f"New top stack:        {frame_access.peek_topstack(self.curframe)}")
        return

    def stop_bytecode_here(self, frame):
        if self.skip and \
               self.is_skipped_module(frame.f_globals.get('__name__')):
            return False
        if frame is self.stopframe:
            if self.stopbytecodeno == -1:
                return False
            return frame.f_lasti >= self.stopbytecodeno
        return False

    def setup_ast2bytecode(self, codeobj):
        a2b = self.codeobj_registry.get(codeobj)
        if not a2b:
            a2b = AST2Bytecode(codeobj)
        return a2b

    def setup_frame_ast2bytecode(self, frame):
        self.framea2b[frame] = self.setup_ast2bytecode(frame.f_code)

    def do_capturetopstack(self, arg):
        if not arg:
            arg = '_topstack'
        frame = self.curframe
        topstack = frame_access.peek_topstack(frame)
        frame.f_globals[arg] = topstack

    def do_until_expr(self, arg):
        frame = self.curframe
        a2b = self.framea2b[frame]
        node, bc = select_astnode(a2b)
        if not node:
            return 0
        print("!! Will stop before", ast.unparse(node))
        self._set_stopinfo_bytecode(frame, None, offset_stop=bc.offset)
        return 1

    def _Pdb__format_line(self, tpl_line, filename, lineno, line, arrow=False):
        node = self.curbytecode.ast if self.curbytecode.ast else None
        if node and lineno == node.lineno:
            start = node.col_offset
            end = node.end_col_offset
            line = f"{line[:start]}<{line[start: end]}>{line[end:]}"
        return super()._Pdb__format_line(tpl_line, filename, lineno, line, arrow)


class AST2Bytecode(object):
    def __init__(self, codeobj):
        self.codeobj = codeobj
        self.ast, self.flat_ast = self._setup_ast()
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
        self.indent = indent

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
        return (root, nodes)

    def _setup_bytecodes(self):
        insts = []
        codeobj = self.codeobj
        for inst in dis.get_instructions(codeobj):
            insts.append(inst)
            for node in self.flat_ast:
                other = dis.Positions(node.lineno, node.end_lineno, node.col_offset, node.end_col_offset)
                if self.match(inst.positions, other):
                    inst.ast = node
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