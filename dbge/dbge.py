import ast
import dis
import gc
import inspect
import sys

import ipdb

from .ast2bytecode import AST2Bytecode
from .breakpoints import (AttributeReadBreakpoint, AttributeWriteBreakpoint,
                          ExpressionBreakpoint)
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
        self.forced = {}
        self.codeobj_registry = {}
        self.exprbreakpoints = []

    # Copy/modified from Bdb
    def set_continue(self):
        """Stop only at breakpoints or when finished.

        If there are no breakpoints, set the system trace function to None.
        """
        # Don't stop except at breakpoints or when finished
        self._set_stopinfo(self.botframe, None, -1)
        if not self.breaks and not self.exprbreakpoints and not self.framea2b.get(self.curframe):
            # no breakpoints; run without debugger overhead
            sys.settrace(None)
            frame = sys._getframe().f_back
            while frame and frame is not self.botframe:
                del frame.f_trace
                frame = frame.f_back

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

    # Copy/modified from IPdb
    def _Pdb__format_line(self, tpl_line, filename, lineno, line, arrow=False):
        node = self.curbytecode.ast if self.curbytecode.ast else None
        if node and lineno == node.lineno:
            start = node.col_offset
            end = node.end_col_offset
            line = f"{line[:start]}<{line[start: end]}>{line[end:]}"
        return super()._Pdb__format_line(tpl_line, filename, lineno, line, arrow)

    # Extends trace function to listen to opcode events
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
            tos = frame_access.peek_topstack(frame)
            forced = self.forced.setdefault(frame, [])
            if tos and tos not in forced :
                forced.append(tos)
            print(f"Current stack top:       {tos}")
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
            if breakpoint.should_break(frame):
                return True
        return False

    def user_call(self, frame, arg):
        frame.f_trace_opcodes = True  # Activate trace opcode in new frame
        # frame.f_trace = self.trace_dispatch
        self.setup_frame_ast2bytecode(frame)
        super().user_call(frame, arg)

    def dispatch_return(self, frame, arg):
        # The frame exeuction is finished we clear forced values and frames
        del self.framea2b[frame]
        forced = self.forced.get(frame, [])
        # self._get_frame_locals(frame).clear()
        forced.clear() # The frame execution is finished, we clear all forced values
        return super().dispatch_return(frame, arg)

    def _set_stopinfo_bytecode(self, stopframe, returnframe, offset_stop=0):
        self.stopframe = stopframe
        self.returnframe = returnframe
        self.quitting = False
        self.stopbytecodeno = offset_stop
        self.stoplineno = -1

    def do_stepi(self, arg):
        frame = self.curframe
        index = 0
        if arg:
            index = int(arg) + frame.f_lasti
        self._set_stopinfo_bytecode(frame, None, offset_stop=index)
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
        frame = self.curframe
        print(f"Replace top stack:    {frame_access.peek_topstack(frame)}")
        obj = eval(arg, frame.f_globals, self._get_frame_locals(frame))
        frame.f_locals.setdefault("__dbge_forced", []).append(obj)  # We force a ref to avoid obj to be garbaged collected
        frame_access.change_topstack(frame, obj)
        print(f"New top stack:        {frame_access.peek_topstack(frame)}")
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
            for m in a2b.all_a2b():
                self.codeobj_registry[m.codeobj] = m
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
        node, bc, _ = select_astnode(a2b)
        if not node:
            return 0
        print("!! Will stop before", ast.unparse(node))
        self._set_stopinfo_bytecode(frame, None, offset_stop=bc.offset)
        return 1

    def _attribute_bp(self, frame, str_expr, bpoint_class):
        # refactor me
        if not str_expr:
            print("!! an expression with the form <expr>.attr is expected")
            return (None, None, None, None)
        if "." not in str_expr:
            print("!! an expression with the form <expr>.attr is expected")
            return None
        if ":" in str_expr:
            args = [s.strip() for s in str_expr.split(":") if s]
            if len(args) != 2:
                print("!! mode or expression is missing.\n"
                      "The argument must have the form <mode>:<expr>.attr\n"
                      "Were <mode> is 'both' or 'b', 'internal' or 'i', 'external' or 'e'")
                return (None, None, None, None)
            mode, str_expr = args
        else:
            mode = "both"
        frame = self.curframe
        obj, attr = str_expr.rsplit(".", maxsplit=1)
        resolved = eval(obj, frame.f_globals, self._get_frame_locals(frame))

        return resolved, attr, bpoint_class(resolved, attr, mode=mode), mode

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

        from_a2b = self.setup_ast2bytecode(codeobj)
        node, bc, mapper = select_astnode(from_a2b)
        instance = obj if not isinstance(obj, type) else None
        expb = ExpressionBreakpoint(mapper, node, bc, instance=instance)
        self.exprbreakpoints.append(expb)
        print(f"Breakpoint [{len(self.exprbreakpoints) - 1}] '{ast.unparse(node)}'")
        return 0

    def do_breakattributewrite(self, arg):
        resolved, attr, breakpoint, mode = self._attribute_bp(self.curframe, arg, AttributeWriteBreakpoint)
        if breakpoint:
            self.exprbreakpoints.append(breakpoint)
            print(f"Breakpoint [{len(self.exprbreakpoints) - 1}] breaks on attribute write for {resolved}.{attr} <mode={mode}>")
        return 0

    def do_breakattributeread(self, arg):
        resolved, attr, breakpoint, mode = self._attribute_bp(self.curframe, arg, AttributeReadBreakpoint)
        if breakpoint:
            self.exprbreakpoints.append(breakpoint)
            print(f"Breakpoint [{len(self.exprbreakpoints) - 1}] breaks on attribute read for {resolved}.{attr} <mode={mode}>")
        return 0