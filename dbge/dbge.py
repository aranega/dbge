import ast
import dis
import inspect
import sys

import ipdb

from .frame_access import frame_access
from .interactive import select_astnode
from .ast2bytecode import AST2Bytecode


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
        self.exprbreakpoints = []

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
        for breakpoint in self.exprbreakpoints:
            if breakpoint.break_here(frame, bytecode):
                self.interaction(frame, None)

    def break_here(self, frame):
        br = super().break_here(frame)
        if br:
            return True
        return self.exprbreak_here(frame)

    def exprbreak_here(self, frame):
        for breakpoint in self.exprbreakpoints:
            if breakpoint.break_here(frame, self.curbytecode):
                return True
        return False

    def break_anywhere(self, frame):
        res = super().break_anywhere(frame)
        if res:
            return res
        for breakpoint in self.exprbreakpoints:
            if breakpoint.a2b.codeobj is frame.f_code:
                return True
        return False

    def set_continue(self):
        """Stop only at breakpoints or when finished.

        If there are no breakpoints, set the system trace function to None.
        """
        # Don't stop except at breakpoints or when finished
        self._set_stopinfo(self.botframe, None, -1)
        if not self.breaks and not self.exprbreakpoints:
            # no breakpoints; run without debugger overhead
            sys.settrace(None)
            frame = sys._getframe().f_back
            while frame and frame is not self.botframe:
                del frame.f_trace
                frame = frame.f_back

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
            self.codeobj_registry[codeobj] = a2b
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

    def do_be(self, arg):
        if not arg:
            print("!! an expression towards the function or the method to stop to is required")
            return 0

        frame = self.curframe
        if "." in arg:
            obj, attr = arg.rsplit(".", maxsplit=1)
            obj = eval(obj, frame.f_globals, frame.f_locals)
            resolved = getattr(obj, attr)
        else:
            obj = None
            resolved = eval(arg, frame.f_globals, frame.f_locals)
        codeobj = resolved.__code__

        a2b = self.setup_ast2bytecode(codeobj)
        node, bc = select_astnode(a2b)
        instance = obj if not isinstance(obj, type) else None
        expb = ExpressionBreakpoint(a2b, node, bc, instance=instance)
        self.exprbreakpoints.append(expb)
        print(f"Breakpoint [{len(self.exprbreakpoints) - 1}] '{ast.unparse(node)}'")
        return 0

    def _Pdb__format_line(self, tpl_line, filename, lineno, line, arrow=False):
        node = self.curbytecode.ast if self.curbytecode.ast else None
        if node and lineno == node.lineno:
            start = node.col_offset
            end = node.end_col_offset
            line = f"{line[:start]}<{line[start: end]}>{line[end:]}"
        return super()._Pdb__format_line(tpl_line, filename, lineno, line, arrow)


class ExpressionBreakpoint(object):
    def __init__(self, a2b, node, bc, instance=None):
        self.a2b: AST2Bytecode = a2b
        self.node = node
        self.bc = bc
        self.instance = instance

    def break_here(self, frame, bc):
        codeobj = frame.f_code
        if self.instance:
            self_name = codeobj.co_varnames[0] if codeobj.co_argcount > 0 else ""
            current_instance = frame.f_locals.get(self_name, None)
            on_instance = self.instance is current_instance
        else:
            on_instance = True
        return self.a2b.codeobj is codeobj and bc.ast is self.node and on_instance
