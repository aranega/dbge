import ast
import code
import dis
import gc
import inspect
import sys
import weakref

import ipdb

from .ast2bytecode import AST2Bytecode
from .breakpoints import ExpressionBreakpoint, OCAttributeAccessBreakpoint
from .frame_access import frame_access
from .interactive import select_astnode


def set_trace():
    DbgE().set_trace(inspect.currentframe().f_back)


class DbgE(ipdb.__main__._get_debugger_cls()):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.curbytecode = None
        self.stopbytecodeno = -1
        self.code_mapper = weakref.WeakKeyDictionary()
        self.exprbreakpoints = []

    def get_tos(self, frame):
        tos = frame_access.peek_topstack(frame)
        if isinstance(tos, weakref.ReferenceType):
            tos = tos()
        return tos

    # Copy/modified from Bdb
    def set_continue(self):
        """Stop only at breakpoints or when finished.

        If there are no breakpoints, set the system trace function to None.
        """
        # Don't stop except at breakpoints or when finished
        self._set_stopinfo(self.botframe, None, -1)

        # Patch to avoid a change in behavior because of "curframe_locals" (?)
        if not self.breaks and not self.exprbreakpoints: # and not self.curframe_locals:
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

        self.setup_ast2bytecode(frame.f_code)

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

    def setup_ast2bytecode(self, codeobj):
        a2b = self.code_mapper.get(codeobj)
        if not a2b:
            a2b = AST2Bytecode(codeobj)
            for m in a2b.all_a2b():
                self.code_mapper[m.codeobj] = m
        return a2b

    ## dispatch section
    # Extends trace function to listen to opcode events
    def trace_dispatch(self, frame, event, arg):
        if self.quitting:
            return # None
        if event == 'opcode':
            return self.dispatch_opcode(frame)
        return super().trace_dispatch(frame, event, arg)

    def dispatch_opcode(self, frame):
        a2b: AST2Bytecode = self.code_mapper[frame.f_code]
        bytecode = a2b.get_bytecode(offset=frame.f_lasti)
        self.curbytecode = bytecode
        self.user_opcode(frame, bytecode)
        return self.trace_dispatch

    def user_opcode(self, frame, bytecode: dis.Instruction):
        if self.stopbytecodeno >= 0:
            # fcode = frame.f_code
            # ts = frame_access.topstack(frame) - 1
            # size = max(fcode.co_stacksize, ts)
            # for i in range(size, -1, -1):
            #     arrow = "-->" if i == ts else "   "
            #     val = frame_access.stack_at(frame, i)
            #     dealoc = " "
            #     if isinstance(val, weakref.ReferenceType):
            #         val = val()
            #         if val is None:
            #             dealoc = "X"
            #             val = "Value deallocated"
            #     print(f"{arrow} {dealoc} {i}:  {val}")
            tos = frame_access.peek_topstack(frame)
            if isinstance(tos, weakref.ReferenceType):
                tos = tos()
                if tos is None:
                    print("TOS deallocated")
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

    def user_call(self, frame, arg):
        frame.f_trace_opcodes = True  # Activate trace opcode in new frame
        self.setup_ast2bytecode(frame.f_code)
        super().user_call(frame, arg)

    def remove_mapper_entry(self, frame):
        # The frame exeuction is finished we clear forced values and frames
        self.curframe_locals.clear()  # Some locals are held there, not sure yet why

    def dispatch_return(self, frame, arg):
        # self.remove_mapper_entry(frame)
        return super().dispatch_return(frame, arg)

    ## End dispatch section

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
        a2b: AST2Bytecode = self.code_mapper[frame.f_code]
        stop_offset = a2b.resolve_end_offset(frame.f_lasti)
        self._set_stopinfo_bytecode(self.curframe, None, offset_stop=stop_offset)
        return 1

    def do_forcetopstack(self, arg):
        if not arg:
            print("Missing argument")
            return
        frame = self.curframe
        print(f"Replace top stack:    {self.get_tos(frame)}")
        obj = eval(arg, frame.f_globals, self._get_frame_locals(frame))
        frame.f_locals.setdefault("__dbge_forced", []).append(obj)  # We force a ref to avoid obj to be garbaged collected
        frame_access.change_topstack(frame, obj)
        print(f"New top stack:        {self.get_tos(frame)}")
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

    def do_capturetopstack(self, arg):
        if not arg:
            arg = '_topstack'
        frame = self.curframe
        topstack = self.get_tos(frame)
        frame.f_globals[arg] = topstack

    def do_until_expr(self, arg):
        frame = self.curframe
        a2b = self.code_mapper[frame.f_code]
        node, bc, _ = select_astnode(a2b)
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
        locals = self._get_frame_locals(frame)
        if "." in arg:
            obj, attr = arg.rsplit(".", maxsplit=1)
            obj = eval(obj, frame.f_globals, locals)
            resolved = getattr(obj, attr)
        else:
            obj = None
            resolved = eval(arg, frame.f_globals, locals)
        codeobj = resolved.__code__

        from_a2b = self.setup_ast2bytecode(codeobj)
        node, bc, mapper = select_astnode(from_a2b)
        instance = obj if not isinstance(obj, type) else None
        expb = ExpressionBreakpoint(mapper, node, bc, instance=instance)
        self.exprbreakpoints.append(expb)
        print(f"Breakpoint [{len(self.exprbreakpoints) - 1}] '{ast.unparse(node)}'")
        return 0

    def do_breakattributewrite(self, arg):
        # refactor me
        resolved, attr, breakpoint, mode = self._attribute_bp(self.curframe, arg, "write")
        if breakpoint:
            self.exprbreakpoints.append(breakpoint)
            print(f"Breakpoint [{len(self.exprbreakpoints) - 1}] breaks on attribute write for {resolved}.{attr} <mode={mode}>")
        return 0

    def do_breakattributeread(self, arg):
        # refactor me
        resolved, attr, breakpoint, mode = self._attribute_bp(self.curframe, arg, "read")
        if breakpoint:
            self.exprbreakpoints.append(breakpoint)
            print(f"Breakpoint [{len(self.exprbreakpoints) - 1}] breaks on attribute read for {resolved}.{attr} <mode={mode}>")
        return 0

    def _attribute_bp(self, frame, str_expr, bp_type):
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

        return resolved, attr, OCAttributeAccessBreakpoint(bp_type, resolved, attr, mode=mode), mode