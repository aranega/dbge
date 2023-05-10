# DbgE: Debugger with granularity of (sub-)expression

This repository provides an extension to IPdb to enable sub-expression stepping, bytecode stepping and some stack manipulation.

DISCLAMER: This project is still in an experimental status and there is probably many gotchas that are not yet tackled.

## Dependencies

* gcc and python headers for the C extension
* `ipdb` (`pip install ipdb`) for the base debugger

## Extra commands

* `stepe`, steps until the next sub-expression
* `stepi`, steps until the next bytecode
* `until_expr`, let you interactively select an expression in the current debugged frame and run the execution until before the execution of this expression
* `be expr`, let you interactively select an expression in the function pointed by `expr` and sets a breakpoint there. The argument `expr` has to resolve to a function/method.
* `capturetopstack [arg]`, let you capture the top of the evaluation stack and place it in `arg` (`_topstack` if `arg` is not set) in the global context attached to the debugged frame.
* `forcetopstack arg`, forces the top of the evaluation stack to `arg` (experimental!)

### Note about `be`

If the resolution is made against an instance, the breakpoint will be activated only before the execution of the interactively selected node for this exact instance.
For example, let's consider the following code:

```python
class A(object):
    def compute(self):
        print("Here")
        return 42

a1 = A()
a2 = A()

import dbge; dbge.set_trace()

a1.compute()
a2.compute()
```

In the debugger, calling `be A.compute` will let you set a breakpoint on an expression inside of `compute`.
Consequently, the execution will break before the execution of the selected sub-expression when `a1.compute()` and `a2.compute()` will be executed.
However, calling `be a2.compute` will let you set a breakpoint on an expression inside of `compute` that will trigger only when `compute` will be executed for `a2`.
This enables a first object-centric breakpoint type.

## How to test the "example.py"

The project is not yet on pypi (not sure it will be one day) as it's experimental and contains a C extension.

Is there the way of playing with the `example.py`

1. clone the repository somewhere and go inside
```
git clone https://github.com/aranega/dbge
cd dbge
```
2. compile the C extension to gain access to some evaluation stack manipulation
```
make   # requires the cpython dev package installed, as well as gcc
```
3. run the `example.py` or set `import dbge; dgbe.set_trace()` where you want in your code.

## Demo videos

| General use of `stepi`, `stepe`, `until_expr`, `forcetopstack` and `capturetopstack` | Use of expression breakpoint with `be` |
:-------------------------:|:-------------------------:
<video src="https://github.com/aranega/dbge/assets/2317394/9739d0e5-ee7a-4270-a387-f38358b227a2">  | <video src="https://github.com/aranega/dbge/assets/2317394/b127bb9b-3ee7-492b-8054-c7ada6708d59">

