class A(object):
    def __init__(self, x):
        self.x = 8

    def compute(self, other):
        c = other.x + self.x
        return c

def example(a):
    b = a + 6
    c = 4 + b + a
    return c

import dbge; dbge.set_trace()

a = A(55)
a2 = A(100)
print("Result 1", a.compute(a2))
print("Result 2", example(5) + 4)
