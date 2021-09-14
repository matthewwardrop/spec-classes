

## The `spec_class` decorator

The primary entry-point into `spec_classes` is the `spec_class` decorator, which
takes your standard class and converts it into a "spec-class" (🌟 ooh... shiny!
🌟). In practice, this just means that it adds some dunder magic methods like
`__init__` and `__setattr__`, along with a few [helper
methods](#helper-methods)... and nothing else. This is intentionally very
similar to the standard library's
[dataclass](https://docs.python.org/3/library/dataclasses.html), and indeed you
can largely consider spec-classes to be a generalization of it.

Using spec-classes is as simple as decorating your annotated class with
`spec_class`. For example:

```python
from spec_classes import spec_class

@spec_class
class MySpec:
    my_str: str
```

The result is a class that:

- Thoroughly type-checks class attributes whenever and however they are mutated.
- Has helper methods that assist with the mutation of annotated attributes,
  allowing one to adopt copy-on-write workflows (see [below](#helper-methods)
  for more details).
- Knows how to output a human-friendly representation of the spec class when
  printed.
- Knows how to compare itself with other instances of the spec class.

As such, and with a huge amount of simplification, the above spec-class
declaration would be roughly similar to writing something like:

```python
import copy
from spec_classes import MISSING

class MySpec:

    def __init__(self, my_str=MISSING)
        if my_str is not MISSING:
            self.my_str = my_str

    def __repr__(self):
        return f"MySpec(my_str={getattr(self, 'my_str', MISSING)}")

    def __eq__(self, other):
        return isinstance(other, MySpec) and getattr(self, 'my_str') == getattr(other, 'my_str')

    def __setattr__(self, attr, value):
        if attr == 'my_str' and not isinstance(my_str, str):
            raise TypeError("`MySpec.my_str` should be a string.")
        super().__setattr__(attr, value)

    def update(self, my_str=MISSING):
        obj = copy.deepcopy(self)
        obj.my_str = my_str
        return obj

    def transform(self, transform=MISSING, *, my_str_transform=MISSING):
        obj = copy.deepcopy(obj)
        obj = transform(self)
        obj.my_str = my_str_transform(obj.my_str)
        return obj

    def with_my_str(self, value):
        obj = copy.deepcopy(self)
        obj.my_str = value
        return obj

    def transform_my_str(self, transform):
        obj = copy.deepcopy(self)
        obj.my_str = transform(self.my_str)
        return obj

    def reset_my_str(self):
        obj = copy.deepcopy(self)
        del obj.my_str
        return obj
```

The remainder of this documentation is dedicated to exploring exactly which
attributes get managed by spec-classes, which methods get generated when, and
how it all fits together.

## Managed attributes

By default, all annotated attributes in the class decorated with `@spec_class`
are managed by spec-classes. This means that the constructor and representation
of the spec class will consider all annotated attributes, and nothing else. For
example:

```python
@spec_class
class MySpec:
    my_str: str = "Hello"
    my_int = 1

MySpec(my_str="Hi")  # All good.
MySpec(my_int=2)  # Raises a TypeError (`my_int` is not annotated, and therefore not managed)
```

You can override, if necessary, the attributes that are considered by spec-classes
using the keyword arguments to the `@spec_class` decorator:

  - **attrs**: An iterable of strings indicating the names of attributes to be
    included. If not already annotated on the class, these will be given an
    annotation of `typing.Any`.
  - **attrs_typed**: A mapping from the string name of the attribute to the type
    of the attribute to use (can override class annotations).
  - **attrs_skip**: An iterable of attributes names to skip during determination
    of which fields to manage.

Note that unless `attrs_skip` is provided, if `attrs` and/or `attrs_typed` are
provided, then spec-classes **will not** automatically manage other annotated
attributes on the class.

Extending our above example, you could do:

```python
@spec_class(attrs_typed={'my_int': int}, attrs_skip=[])
class MySpec:
    my_str: str = "Hello"
    my_int = 1

MySpec(my_str="Hi")  # All good.
MySpec(my_int=2)  # All good.
```

## Constructor

Using the `@spec_class` decorator will by default add a constructor to the class
(unless one is already defined on the class). You can disable the addition of a
constructor by passing `init=False` to the decorator.

All arguments to the generated constructor must be passed by name (except for
the `key` attribute; see [below](#keyed-spec-classes)). Also, instances of
spec-classes are permitted to have missing values. If the class does not provide
a default value for an attribute, instances will not have the attribute present,
and representations of the class will render it as `MISSING`. For example:

```python
@spec_class
class MySpec:
    my_str: str

MySpec()  # MySpec(my_str=MISSING)
MySpec().my_str  # AttributeError: `MySpec.my_str` has not yet been assigned a value.
```

!!! tip
    It is always safe to use mutable default values when using the default
    constructor with your managed attributes. They will be deep-copied in the
    constructor before being assigned to instances of your class. For example:
    ```python
    @spec_class
    class MySpec:
        my_list: ['a']

    assert MySpec().my_list is not MySpec.my_list
    ```

## Keyed Spec Classes

Most attributes on a spec-class are treated identically and without privilege.
The one exception to that is an optional `key` attribute. Semantically, a key is
intended to uniquely identify an instance of a spec-class within some context,
and if configured *must* be assigned a value at instantiation time. To indicate
that a spec-class should be "keyed", pass the `key` argument to the `spec_class`
constructor. For example:

```python
@spec_class(key='key')
class KeyedSpec:
    key: str
    value: str

KeyedSpec('my_key')  # KeyedSpec(key='my_key', value=MISSING)
KeyedSpec()  # TypeError: __init__() missing 1 required positional argument: 'key'
```

!!! note
    The `key` attribute is the only attribute that does not need to be passed in
    by name to the constructor. Also: if the class has a default for the key
    attribute, it will be lifted up as the value in the instance (just like
    other attributes).

## Type checking

All attributes managed by spec-classes are type-checked during initialization
and any mutation. Attempts to set attributes to an invalid type will result in a
`TypeError`. For example, from the above `MySpec`:

```python
MySpec(my_str=1)  # TypeError: Attempt to set `MySpec.my_str` with an invalid type [got `1`; expecting `str`].
```

## Helper methods

To simplify the adoption of copy-on-write workflows, and to make mutation of
instances more convenient and chainable, `spec_class` generates helper methods
for the base class and every managed attribute. The number and types of methods
added depends on type annotations, but in every case mutations performed by
these methods are (by default) done on copies of the original instance, and so
can be used safely on instances that are shared between multiple objects.
Refer to the [Helper Methods](methods/index.md) documentation for more details.