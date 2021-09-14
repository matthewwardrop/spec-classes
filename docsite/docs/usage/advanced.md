## Typecasting/preparation

While preparation of attribute values can still be done using custom
constructors or property overrides, spec-classes provides a simpler mechanism
for typecasting/preparing attribute values (as shown in
[one of the examples](../examples/preparation.md)). The [`Attr`](special_types.md#Attr)
object has two optional attributes: `prepare` and `prepare_item`. Both of these
should be `Callable` objects if provided, and are respectively used to prepare
the attribute value and items within an attribute collection. When both are
present, `prepare` is called first. There are two ways to populate these
attributes: by providing a `_prepare_<attr>` and/or a `_prepare_<attr_singular>`
method; or by setting the attribute to an `Attr` instance and using the
`Attr.preparer` and `Attr.item_preparer` decorators. Both are demonstrated
in the aforementioned [example](../examples/preparation.md).

## Init overflow attributes
If you want your spec-class to accept arbitrary arguments in its constructor,
including those that are not registered attributes, you can pass an arbitrary
attribute name to `init_overflow_attr` in the `spec_class` decorator. During
instance construction, spec-classes will then collect all additional keyword
arguments and place them as a dictionary in nominated attribute.

```python
@spec_class(init_overflow_attr='kwargs')
class Spec:
    pass

Spec(a=1, b=2)
# Spec(kwargs={'a': 1, 'b': 2})
```

## Frozen spec classes

By default, instances of spec-classes behave much like any other instance in
that you can mutate attributes in-place. If you would like to prevent in-place mutation, you
can use the `frozen` keyword argument to the constructor. For example:

```python
@spec_class(frozen=True)
class MyClass:
    my_str: str

MyClass().my_str = "hi"  # FrozenInstanceError: Cannot mutate attribute `my_str` of frozen spec class `MySpec`.
```

!!! note
    Frozen spec class instances can still be updated using the copy-on-write
    helper methods (introduced below):

    ```python
    MySpec().with_my_str("hi")  # MyClass(my_str="hi")
    ```

## Avoiding copies of large attributes

Spec-classes adopt a copy-on-write approach when mutating classes via the
helper methods (e.g. `.with_<attr>()`). In some instances, however, that is
undesirable, for example when one or more attributes consumes a lot of memory.
To help with this, spec-classes allows entire spec-classes and/or attributes
thereof to opt-out of being copied. When decorating a spec-class you can pass
`do_not_copy=True` to `spec_class` to disable all copying (effectively making all mutations
in-place), or pass `do_not_copy=['attributes', 'to', 'avoid', 'copying']`, which
will populate the `Attr` attribute `do_not_copy` for the nominated attributes,
and pass these attributes by reference (rather than value) when copying
spec-classes. You can also directly specify attributes to using `Attr`, as
documented [here](special_types.md#Attr).

```python
@spec_class(do_not_copy=['data'])
class DataAnalyzer:
    data: Any # Potentially LARGE data object
    another_obj: Any = Attr(do_not_copy=True)
```

## Immediate bootstrapping

Spec-classes is typically lazy in its "bootstrapping" of classes (it doesn't
actually mutate the class straight away with all of the helper methods). This is
because it is often the case that type-annotated code becomes cyclic very
quickly, and since spec-classes needs type information during the generation of
methods, immediately bootstrapping would cause cyclic import issues.

Instead, spec-classes adds a `__new__` method and a placeholder `__spec_class__`
metadata, and lazily bootstraps until the first instantiation or the first
lookup of the `__spec_class__` attribute. In the vast majority of cases, this
works well, but it is possible that more advanced class introspections require
the class to be bootstrapped immediately. You can achieve this by passing
`bootstrap=True` to the `spec_class` decorator.

```python
@spec_class(bootstrap=True)
class Spec:
    ...
```

## Avoiding cyclic import issues

As mentioned above, cyclic import issues are common in type-annotated code,
especially if the type annotations are required at run-time (as is the case for
spec-classes). Sometimes there is just no way to import the types necessary
at a module level without having all classes in a single file. To avoid this,
spec-classes allows you to lazily import types that are used to annotate
attributes by importing them in a method that is only evaluated immediately
before the types are used. You can also use this mechanism to alias types.

```python
from __future__ import annotations

@spec_class
class Spec:

    data: DataFrame
    value: my_alias

    @classmethod
    def ANNOTATION_TYPES(cls):
        import pandas
        return {
            'DataFrame': pandas.DataFrame,
            'my_alias': str,
        }
```

## Overriding dunder methods

The dunder methods that spec-classes introduces are: `__init__`, `__repr__`,
`__eq__`, `__getattr__`, `__setattr__`, `__delattr__` and `__deepcopy__`.
Overriding `__getattr__`, `__setattr__`, `__delattr__` and `__deepcopy__` is
**not** supported (they are essential for the behavior of spec-classes), and you
will be responsible for making things work properly if you do. `__init__`,
`__repr__` and `__eq__` can be overridden safely, however.

In the rare circumstances that it becomes necessary for you to overwrite these
methods, you can just implement these on the class. Since spec-classes never
overwrites methods that a user has written, these methods will *not* be
overridden by spec-classes. If you want to completely remove these methods, you
can pass `init=False`, `repr=False` and/or `eq=False` to the `spec_class`
decorator. For your convenience, spec-classes will *always* register
spec-classes' implementation of these methods as `__spec_class_init__`,
`__spec_class_repr__` and `__spec_class_eq__` so that you can leverage them in
your overrides (this is necessary because spec-classes does not touch your
classes' MRO, and so no `super()` calls to spec-classes' methods are possible).

## Subclassing

Spec-classes fully supports subclassing, including the honoring of overridden
constructors in super-classes. Spec-classes remembers where spec-class
attributes were defined, and calls the appropriate constructor to initialize
them. For example:
```python
@spec_class
class Base:
    x: int
    y: int

    def __init__(self, x=10, y=10):
        self.x = x + 1
        self.y = y + 1
        self.a = x * y

@spec_class
class Sub(Base):
    x = 100 # Sub provides a new default value but is not the owner of `x`
    y: int = 100  # Sub becomes the owner of `y`
    z: int = 300

Sub()
# Sub(x=101, y=100, z=300)
Sub().a
# 1000  # (x = 100) * (y = 10), since parent constructors are only passed
        # attributes they own.
```
