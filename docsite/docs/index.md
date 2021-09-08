<img alt="Spec Classes Logo" src="https://raw.githubusercontent.com/matthewwardrop/spec-classes/main/docsite/docs/assets/images/logo-with-text.png" style="max-width: 500px"/>

[![PyPI - Version](https://img.shields.io/pypi/v/spec-classes.svg)](https://pypi.org/project/spec-classes/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/spec-classes.svg)
![PyPI - Status](https://img.shields.io/pypi/status/spec-classes.svg)
[![build](https://img.shields.io/github/workflow/status/matthewwardrop/spec-classes/Run%20Tox%20Tests)](https://github.com/matthewwardrop/spec-classes/actions?query=workflow%3A%22Run+Tox+Tests%22)
[![codecov](https://codecov.io/gh/matthewwardrop/spec-classes/branch/main/graph/badge.svg)](https://codecov.io/gh/matthewwardrop/spec-classes)
[![Code Style](https://img.shields.io/badge/code%20style-black-black)](https://github.com/psf/black)


- **Documentation**: <https://matthewwardrop.github.io/spec-classes>
- **Source Code**: <https://github.com/matthewwardrop/spec-classes>
- **Issue tracker**: <https://github.com/matthewwardrop/spec-classes/issues>

# Introduction

**`spec_classes`** is a stand-alone (but largely interoperable) generalization
of the standard library's `dataclass` decorator. It adds, among other things:
type-checking, rich field preparation, and convenient copy-on-write mutation
wrappers. Spec-class definitions are Pythonic, simple, and concise.

This library is especially useful in contexts where run-time validation and
instant feedback is desirable, and/or where correctness is valued over
performance. With that said, we do try to keep spec-classes performant (see
[performance details](https://matthewwardrop.github.io/spec-classes/implementation/performance.md)).

## Philosophy

**It should be hard for users to do the wrong thing.** `spec_classes` is
designed to help end-users interact with, mutate, and assemble (especially in ad
hoc contexts like notebooks) potentially large libraries of data classes without
fear of breaking things. Operations on data classes should be atomic (operations
should never be partially committed), validated (types should match, etc.), and
provide instant helpful feedback when the user makes a mistake.

**We don't own your class.** `spec_classes` **never** overrides local
pre-existing methods, and doesn't add any metaclasses or parents. If you
decorate a class with `@spec_class`, spec classes will add (if you have not
already) some dunder magic methods (like `__init__`,`__setattr__`, etc.), and
some helper methods... but that's it. Spec classes are, at the end of the day,
just regular classes pre-loaded with useful methods that you didn't have to
write yourself.

**Copy-on-write by default.** One of the dangers with using class instances as
specification is that if they are mutated in one context, they are mutated for
all contexts. Spec classes does not prevent (by default) local mutations of
class instances (you can still do `my_spec.foo = 'bar'`); but all helper methods
return a mutated copy (by default). For example, `my_spec.with_foo('bar')` will
not be the same instance as `my_spec`, and so these methods are always safe to
use.

**Be consistent.** All helper methods added by `spec_classes` exist within well
defined namespaces; that is: `with_<attr>`, `transform_<attr>`, etc.; and each
class of methods has the same naming conventions for arguments and provides
complete inline documentation. This makes it easy for users to figure out how to
use the methods, to override these methods and/or to add new methods that do not
collide.

**Minimize Surprise.** The behavior of spec classes almost always matches that
of base Python classes where functionality overlaps, and should always be
intuitive otherwise (e.g. when type-checking is violated).

**Performance is important.** Although performance is not the primary goal of
`spec_classes`, given the targeted feature-set, the overhead introduced should
be as small as possible.

## Example

```python
from spec_classes import spec_class

@spec_class
class Rectangle:
    width: float
    height: float
    color: str

    @property
    def area(self):
        return self.width * self.height

rect = Rectangle()
rect  # Rectangle(width=MISSING, height=MISSING, color=MISSING)
rect.with_color("red")  # Rectangle(width=MISSING, height=MISSING, color='red')

Rectangle(width=10., height=10.).area  # 100.0

rect.with_width('invalid')  # TypeError: Attempt to set `Rectangle.width` with an invalid type [got `'invalid'`; expecting `float`].
```

For more details on usage, refer to the [documentation](https://matthewwardrop.github.io/spec-classes).

## Installation

Spec classes can be installed via `pip` or `conda`.

To install via `pip` you can use:

```shell
pip install spec-classes
```

To install via `conda` you can use:

```shell
conda install spec-classes
```

You can verify that the installation was successful by printing the version of
`spec-classes` that was installed:

```shell
python -c "import spec_classes; print(spec_classes.__version__)"
```

## Related projects and prior art

`spec_classes` takes a more opinionated stance than most libraries in this space
on exactly how data-classes should be built and on copy-on-write patterns.
Nevertheless, there are excellent pre-existing alternatives to spec-classes
for those looking for something lighter-weight. In particular, you could
consider:

- [typeguard](https://github.com/agronholm/typeguard): A utility library for
    run-time type-checking functions, methods and classes.
- [pytypes](https://github.com/Stewori/pytypes): Another utility library for
    run-time type-checking functions, methods and classes.
- [pydantic](https://github.com/samuelcolvin/pydantic/): A light-weight data
    parsing and validation library that also uses type hints.
- [attrs](https://github.com/python-attrs/attrs): A library that provides a
    super-set of the functionality of Python's data-class, but still adds no
    run-time overhead (no type-checking, extra helper-methods, etc).

There are many other libraries in the business of mapping and validating
transformations from JSON to Python classes, but these somewhat orthogonal to
the aims of this project (which is to make Python classes themselves pleasant
to use), and so they are not mentioned here.