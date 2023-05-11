import dis
from multiprocessing import context

from .ast2bytecode import AST2Bytecode
from .frame_access import frame_access


class ExpressionBreakpoint(object):
    def __init__(self, a2b: AST2Bytecode, node, bc, instance=None):
        self.a2b = a2b
        self.node = node
        self.bc = bc
        self.instance = instance

    def should_break(self, frame):
        return self.a2b.codeobj is frame.f_code

    def break_here(self, frame, bc):
        if self.a2b.codeobj is not frame.f_code:
            return False

        if bc.ast is not self.node:
            return False

        codeobj = frame.f_code
        if self.instance:
            # We get the current object "self"
            self_name = codeobj.co_varnames[0] if codeobj.co_argcount > 0 else ""
            current_instance = frame.f_locals.get(self_name, None)
            on_instance = self.instance is current_instance
        else:
            on_instance = True
        return on_instance


class BytecodeBasedBreakpoint(object):
    def __init__(self, opname, instance):
        self.opname = opname
        self.instance = instance


class AttributeBasedBreakpoint(BytecodeBasedBreakpoint):
    def __init__(self, opname, instance, attribute, mode):
        super().__init__(opname, instance)
        self.attribute = attribute
        self.mode = mode

    def should_break(self, frame):
        for inst in dis.get_instructions(frame.f_code):
            if inst.opname == self.opname:
                return True
        return False

    def break_here(self, frame, bc: dis.Instruction):
        # Check first the bytecode opname
        if bc.opname != self.opname:
            return False

        # Check then the attribute name
        if bc.argval != self.attribute:
            return False

        if self.mode != 'both':
            # If internal or external access only must be considered
            # We get the current object
            # self_name = codeobj.co_varnames[0] if codeobj.co_argcount > 0 else ""
            # context_of = frame.f_locals.get(self_name, None)
            # context_ok = ((self.mode in ('internal', 'i') and context_of is self.instance) or
            #               (self.mode in ('external', 'e') and context_of is not self.instance))

            codeobj = frame.f_code

            # We build the potential full qual name of the current function/method
            type_name = self.instance.__class__.__qualname__
            fun_name = codeobj.co_name
            build_qualname = f"{type_name}.{fun_name}"

            # We take the qual name of the codeobj
            qualname = codeobj.co_qualname

            # We check if they match
            is_inside = qualname == build_qualname or qualname.endswith(f".{build_qualname}")
            context_ok = ((self.mode in ('internal', 'i') and is_inside) or
                          (self.mode in ('external', 'e') and not is_inside))
        else:
            # If the access must be considered in functions that are part of the object
            context_ok = True
        if not context_ok:
            return False

        # Get the TOS
        tos = frame_access.peek_topstack(frame)
        return context_ok and self.instance is tos


class AttributeWriteBreakpoint(AttributeBasedBreakpoint):
    def __init__(self, instance, attribute, mode="both"):
        super().__init__("STORE_ATTR", instance, attribute, mode)


class AttributeReadBreakpoint(AttributeBasedBreakpoint):
    def __init__(self, instance, attribute, mode="both"):
        super().__init__("LOAD_ATTR", instance, attribute, mode)
