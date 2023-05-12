class A(object):
    def __init__(self, name, x):
        self.name = name
        self.x = x

    def compute(self, other):
        c = other.x + self.x
        return c

    def foo(self):
        self.x = 55
        self.name = 44
        print(self.name)


def example(ainst):
    def inner():
        print("rffff")
    b = ainst.x + 6
    c = 4 + b + ainst.x
    print("Val", ainst.name)
    x = [z + ainst.x for z in range(5)]
    inner()
    return x[0]
    # if c - 120 == 0:
    #     c = c + 6
    # return c
    # c = c > 0 or c != 0
    # return c



a1 = A("a1", 55)
a2 = A("a2", 100)

import dbge; dbge.set_trace()

a1.foo()

print("Result 1", a1.compute(a2))
print("Result 2", a2.compute(a2))
print("Result 3", example(a1) + 4)
