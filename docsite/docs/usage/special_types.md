Spec classes do not require you to use any special types: you can use standard
types from the standard library or any custom type you choose. However, the
`spec_classes` library *does* come with some useful types that you can use to
enrich your spec classes (or indeed any class). These are detailed below, and
are all available by importing from `spec_classes.types`.

## Attribute specification

In most cases, you can simply set spec-class attribute defaults (and or lack
thereof) directly in the class definition. This attribute will then be "managed",
and included in the constructor, equality comparisons, representations, etc.
However, in some cases you need to customize this behavior... and that's where
`field` and `Attr` come in.

### `field`

Spec-classes is compatible with the standard-libraries dataclass
[field specification](https://docs.python.org/3/library/dataclasses.html#dataclasses.field),
so you can use that directly as the attribute values in spec-classes just as you
would in a dataclass. However, in most cases you will want to use `Attr` below.

### `Attr`

`Attr` is to `spec_class` what `field` is to `dataclass`, and it offers a
superset of the API of `field`, making it a drop in replacement. The signature
of `Attr` is:
```python
Attr(
    *,
    default: Any = MISSING,
    default_factory: Callable[[], Any] = MISSING,
    init: bool = True,
    repr: bool = True,
    compare: bool = True,
    hash: Optional[bool] = None,
    metadata: Optional[Any] = None,
    desc: Optional[str] = None,
    do_not_copy: bool = False,
    invalidated_by: Optional[Iterable[str]] = None,
)
```

The default value for the attribute is set by either `default` or `default_factory`,
and `init`, `repr`, `compare` and `hash` control whether the attribute is
considered by `__init__`, `__repr__`, `__eq__` and `__hash__` respectively.
Metadata is an arbitrary object that is not looked at by spec-classes. `desc`
is a docstring for the attribute. `do_not_copy` is an instruction to
spec-classes not to copy the attribute, and so when the parent spec-class is
copied the new spec-class instance will have a reference to the same attribute.
`invalidated_by` is an instruction to spec-classes to reset this attribute
whenever the attributes in this list are mutated.

!!! note
    Hashing is not yet implemented by spec-classes, but is provided here for
    API compatibility. Ordering of spec-classes is also not yet implemented.

For more information, refer to `help(Attr)`.

## Validated Types

Spec-classes type-checks all attributes by default. Sometimes, however, simple
type-checks are insufficient to guarantee a valid value. For example, the `age`
field might require a non-negative integer, and so type-checking against `int`
would not be sufficient. To help with these cases, `spec_classes` offers several
validation types (all of which are implemented in
`spec_classes.types.validated`). These are detailed below.

### `ValidatedType`

This is the base class that powers all validated type checking offered by
`spec_classes`. It translates `isinstance(obj, ValidatedType)` into
`ValidatedType.validate(obj)`, allowing for arbitrary validation logic. To
leverage this you can either subclass this class, or use the `validated` wrapper
below.

An example subclass of `ValidatedType` might look something like:

```python
from abc import classmethod
from spec_classes.types import ValidatedType

class PositiveInt(ValidatedType):

    @classmethod
    def validate(self, obj):
        return isinstance(obj, int) and obj > 0
```

This object could then be used just like any other type annotation:
```python
@spec_class
class MySpec:
    value: PositiveInt
```

### `validated`

`validated` is a wrapper around `ValidatedType` that bypasses the need to
manually subclass. Instead, you  can just call this function to generate a type
and use it inline or via variable. This signature of this function is:

```python
def validated(
    validator: Callable[[Any], bool], name: str = "validated"
): ...
```

An example use-case is:
```python
@spec_class
class MySpec:
    proper_noun: validated(lambda x: x[0] == x[0].upper(), name='ProperNoun')

MySpec(proper_noun="hi")  # TypeError: Attempt to set `MySpec.proper_noun` with an invalid type [got `'hi'`; expecting `ProperNoun`].
```

### `bounded`

`bounded` is a pre-rolled special case of `validated` which allows you to put
upper and lower bounds on numerical types. The signature of `bounded` is:

```python
def bounded(
    numeric_type: Type,
    *,
    ge: numbers.Number = None,
    gt: numbers.Number = None,
    le: numbers.Number = None,
    lt: numbers.Number = None,
): ...
```

and you can refer to `help(bounded)` for more details.

An example use-case might be:

```python
@spec_class
class Person:
    age: bounded(int, ge=0)

Person(age=-1)  # TypeError: Attempt to set `Person.age` with an invalid type [got `-1`; expecting `int∊[0,∞)`].
```

## Keyed Containers

Spec classes are able to optionally set a [`key`
attribute](basic.md#keyed-spec-classes) that is intended to uniquely identify
instances within some context. It is useful to be able to use these keys to
lookup items when they are stored in collections without having to iterate over
all items in the collection to find them. For this purpose, `spec_classes`
offers two special collection types (implemented in `spec_classes.types.keyed`):
`KeyedList` and `KeyedSet` that act respectively like standard lists and sets,
but also allow looking up and mutating elements by key. These are described in
more detail below.

### Key lookups

The `Keyed*` containers in `spec_classes` both subclass from `KeyedBase`, which
implements the default key lookup strategy (among several other things). The
default key lookup strategy is:

1. Check to see if item type is a spec-class, and if so if it has a key
    attribute. If so, that is the key.
2. Attempt to hash the object. If the item is hashable, the object itself is the
    key.

This can be overridden as detailed below.

### `KeyedList`

`KeyedList` is a generic container that behave exactly like a list, but also
layers on the ability to look up items by key. The computational complexity for
list-like operations is the same as the base `list` class, with additional
dict-like operations with complexity as follows:

- O(1) lookups by key
- O(n) replacement by key
- O(n) deletes by key

Under the hood these functionalities are achieved by storing both a `list` and a
`dict` representation of the items stored in the container, and adding dict-like
methods `.keys()`, `.items()`, `.get()` and a special `.index_for_key()` method
that finds the list index for a nominated key.

The constructor to `KeyedList` takes two optional arguments: `sequence` which
takes a sequence of values to pre-fill the list, and `key` a method that takes
an item and returns a key (used to override the default key lookup algorithm).
You can also explicitly indicate the types that the container will store using
regular python typing notation; that is: `KeyedList[<item type>, <key type>]`.

When an object with the same key already exists in side a `KeyedList` a
`ValueError` is raised.

Examples:
```python
l = KeyedList(['a', 'b', 'c'])
l[0]  # 'a'
l['a']  # 'a' ('a' is hashable, and so is its own key)
set(l.keys())  # {'a', 'b', 'c'}
l.append('a')  # ValueError: Item with key `'a'` already in `KeyedList`.

@spec_class(key='key')
class KeyedSpec:
    key: str

l = KeyedList[KeyedSpec, str]()
l.append(KeyedSpec('object_1'))
str(l)  # KeyedList[KeyedSpec, str]([KeyedSpec(key='object_1')])
l[0]  # KeyedSpec(key='object_1')
l['object_1']  # KeyedSpec(key='object_1')
```

### `KeyedSet`

`KeyedSet` behaves almost identically to `KeyedList` except that order is not
preserved, and key collisions are by default acceptable (resulting in existing
objects with the same key being overridden). It behaves exactly like a `set` in
that the **keys** (which are supposed to uniquely identify the objects) are
stored by hash, and mapped to the values of the set. Internally this is just
using a dictionary for storage.

!!! warning
    Care should be taken when using `KeyedSet` where the key of the item
    is of the same type as the item itself. In such cases there is the risk of
    ambiguity about whether an item being referenced in the collection is being
    referenced by key or by value. For example, when `.discard(<item>)` is
    called, `KeyedSet` allows item or keys to be passed. Note that if an item
    is identical to its key there is no ambiguity.

The computational complexity for set-like operations is the same as the base
`set` class, with additional dict-like operations with complexity as
follows:

- O(1) lookups by key
- O(1) deletes by key

If it is important to you that attempts to override objects with the same key
fail unless the objects are equivalent, you can set `enforce_item_equivalence`
to `True` in the constructor.

Examples:
```python
l = KeyedSet(['a', 'b', 'c'])
'a' in l
l['a']  # 'a' ('a' is hashable, and so is its own key)
set(l.keys())  # {'a', 'b', 'c'}
l.add('a')  # This is fine.

@spec_class(key='key')
class KeyedSpec:
    key: str
    value: int = 0

l = KeyedSet[KeyedSpec, str](enforce_item_equivalence=True)
l.add(KeyedSpec('object_1'))
str(l)  # KeyedSet[KeyedSpec, str]([KeyedSpec(key='object_1')])
l['object_1']  # KeyedSpec(key='object_1')
l.add(KeyedSpec('object_1', value=10))  # ValueError: Item for `'object_1'` already exists, and is not equal to the incoming item.
```

## Descriptors

The standard Python library offers various implementations of the [descriptor
protocol](https://docs.python.org/3/howto/descriptor.html), which allows you to
modify the way in which attributes are looked up on object instances. One of the
most common of these is `property`. You can continue to use `property` with
spec-classes, but the down-side of `property` is that it (unless you also
manually supply a `setter`) makes the attribute read-only. Since spec-classes
are often used to store configuration it is often useful to be able treat
`property`s as "default" values, and still override them by default. For this
reason we provide `spec_property`, detailed below, which behaves like a
`property` but has a setter by default, as well as providing support for
caching. We also provide `AttrProxy` which is for even more esoteric cases where
you want two attributes to be linked not only for read operations, but also
write operations. Both are detailed below, and can be used inside of
spec-classes or non-spec-classes alike.

### `spec_property`

`spec_property` is implemented in `spec_classes.types.spec_property`, and
behaves exactly like `property` except that it provides a setter by default
allowing it be overwritten (and reset using deletion), and provides caching. You
can use `spec_property` as follows:

```python
class MyClass:
    @spec_property
    def value(self):
        return 1

m = MyClass()
m.value  # 1
m.value = 10
m.value  # 10
```

The behavior of `spec_property` can also be customized as follows (with defaults
as shown):

```python
class MyClass:
    @spec_property(
        overridable=True,  # Whether to allow overriding by default.
        warn_on_override=False,  # Whether to warn the user when the property getter
            # is overridden. Can be a boolean, string, or `Warning` instance.
            # If non-boolean, then it is treated as the message to present to
            # the user using `warnings.warn`.
        cache=False,  # Whether to cache the result after first evaluation.
        invalidated_by=None,  # An iterable of attributes which when mutated
            # invalidate the cache (only supported when used with spec-classes)
        allow_attribute_error=True,  # Whether to allow properties to raise
            # `AttributeErrors` which are often masked during attribute lookup.
    )
    def method(self):
        ...

    # And of course you can override the setters as you would with regular properties
    @method.setter
    def method(self, value):
        ...
```

As always you can refer to the inline `help(spec_property)` for more details.


### `classproperty`

`classproperty` is implemented in `spec_classes.types.classproperty`, and
behaves exactly like `spec_property` except that it acts on classmethods, and
does not offer inbuilt access to spec-class state. You can use `classproperty`
as follows:

```python
class MyClass:
    @classproperty(
        overridable=False,  # Whether to allow overriding by default.
        warn_on_override=False,  # Whether to warn the user when the property getter
            # is overridden. Can be a boolean, string, or `Warning` instance.
            # If non-boolean, then it is treated as the message to present to
            # the user using `warnings.warn`.
        cache=False,  # Whether to cache the result after first evaluation.
        cache_per_subclass=False,  # Whether cache should be stored per subclass
            # rather than once for all classes.
        allow_attribute_error=True,  # Whether to allow properties to raise
            # `AttributeErrors` which are often masked during attribute lookup.
    )
    def method(cls):
        ...

    # And of course you can override the setters as you would with regular properties
    @method.setter
    def method(cls, value):
        ...
```


### `AttrProxy`

`AttrProxy` is implemented in `spec_classes.types.attr_proxy`, and allows one
attribute to proxy another attribute. This is especially useful if you have
changed the name of an attribute and need to provide backwards compatibility for
an indefinite period; or if one attribute is supposed to mirror another
attribute unless overwritten (e.g. the label of a class might be the "key"
unless overwritten). This functionality could obviously be implemented directly
using `property`, which may be advisable if readability is more important than
concision.

You can construct an `AttrProxy` instance using:

```python
AttrProxy(
    attr="<attribute to proxy on same instance>",  # Required!
    transform=lambda x: x**2,  # Optional transform on attribute value.
    passthrough=False,  # Defaults to `False`, whether to pass on mutations back through to the proxied attribute
    fallback=MISSING,  # Defaults to `MISSING`; the value to return if the proxied attribute is not set.
)
```

Example:
```python
@spec_class(key="key")
class MyObject:
    key: str
    label: str = AttrProxy("key", transform=lambda key: key.replace('_', ' ').title())

m = MyObject("object_1")
m.label  # 'Object 1'
m.label = "My Object"
m.label  # 'My Object'
```

## Sentinels

It is often useful to have at least one value reserved for use as a sentinel.
Depending on the context they can be interpreted as an failure state or trigger
some fallback behavior. In `spec_classes`, we use `MISSING`.

### `MISSING`

In `spec_classes`, `spec_classes.MISSING` is the sentinel used to indicate that
an attribute or argument value has not (yet) been provided. If you are using
spec-classes in your project, you can feel free to use this sentinel also.

`MISSING` is implemented in `spec_classes.types.missing`, and is an instance of
the singleton class `_MissingType` (every instantiation will return the same
instance). `MISSING` is falsey (`bool(MISSING) is False`), but otherwise cannot
be compared to anything else. Its string representation is `'MISSING'`.