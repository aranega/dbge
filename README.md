# DbgE: Debugger with granularity of (sub-)expression

This repository provides an extension to IPdb to enable sub-expression stepping, bytecode stepping and some stack manipulation.

DISCLAMER: This project is still in an experimental status and there is probably many gotchas that are not yet tackled.

## Extra commands

* `stepe`, steps until the next sub-expression
* `stepi`, steps until the next bytecode
* `until_expr`, let you interactively select an expression in the current debugged frame and run the execution until before the execution of this expression
* `capturetopstack [arg]`, let you capture the top of the evaluation stack and place it in `arg` (`_topstack` if `arg` is not set) in the global context attached to the debugged frame.
* `forcetopstack arg`, forces the top of the evaluation stack to `arg` (experimental!)

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

https://github.com/aranega/dbge/assets/2317394/a8031a3a-f336-44ee-b3e6-335b5ee1b2ec
