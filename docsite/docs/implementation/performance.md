The additional functionality provided by spec-classes is not free, but effort is
made to keep things as performant as possible. In the following we briefly
investigate the relative performance of spec-classes to raw classes and
data-classes.

Let's define three classes, one using dataclass, one with a trivial
`__setattr__` implementation, and one using spec-classes.

```python
from dataclasses import dataclass
from spec_classes import spec_class

@dataclass
class MyData:
    """
    Basic data class. No `__setattr__` is implemented, so things stay mostly in
    C.
    """
    a: int = 1
    b: int = 2
    c: int = 3

@dataclass
class MyDataRaw:
    """
    Basic data class with trivial `__setattr__` implementation.
    """
    a: int = 1
    b: int = 2
    c: int = 3

    def __setattr__(self, attr, value):
        super().__setattr__(attr, value)

@spec_class(bootstrap=True)
class MySpec:
    """
    Simple spec-class, which enforces types at runtime.
    """
    a: int = 1
    b: int = 2
    c: int = 3
```

Without any attempt to be scientific and exact in the performance comparisons,
here is a simple benchmark for instantiating these classes (on spec-classes
version 1.0.1):

```python
%timeit MyData(a=1, b=2, c=3)
# 330 ns ± 11.9 ns per loop (mean ± std. dev. of 7 runs, 1000000 loops each)
%timeit MyDataRaw(a=1, b=2, c=3)
# 1.02 µs ± 44 ns per loop (mean ± std. dev. of 7 runs, 1000000 loops each)
%timeit MySpec(a=1, b=2, c=3)
# 7.88 µs ± 310 ns per loop (mean ± std. dev. of 7 runs, 100000 loops each)
```

Roughly speaking, then, spec-classes is about 23 times slower than when using
the basic class behavior (implemented in C); or about 8 times slower than when
using the basic class behavior but with a trivial Python `__setattr__` wrapper.
Obviously this overhead will increase when using other more advanced features
of spec-classes, such as the attribute preparers, but you should expect the
overhead to be roughly commensurate with the performance overhead of
implementing it outside of spec-classes.

While this overhead is non-trivial, for the use-case for which it is designed
(where there is a human-sensible number of classes to mutate and configure),
this overhead is acceptable. In the future, we may add support for disabling
type-checking and/or other enforcements, which may allow us to reduce this
overhead further.