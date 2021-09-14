Attributes that have a type subclassing from `MutableSequence`, `MutableMapping`
or `MutableSet` (see `collections.abc` in the standard library; and note that
these include the standard `list`, `dict` and `set` datatypes) are considered to
be collections. In addition to the scalar helper methods, spec-classes also
adds three more helper methods to assist with the mutation of elements of the
collection; again with a view to simplifying incremental setting of the
attributes and/or adoption of a copy-on-write workflow. The helper methods are:

  - `with_<attr_singular>(...)`
  - `update_<attr_singular>(...)`
  - `transform_<attr_singular>(...)`
  - `without_<attr_sigular>(...)`

The concrete signatures differ based on the collection type, and so will be
explored in more detail below. As for the scalar methods, when the collected
item type is a spec-class, additional fields are added to the methods to allow
direct access or mutation of attributes of the elements in the collection.

## Method "Singular" Naming

As indicated above, the collection methods are named after the singular form of the attribute name. The generation of the singular form is handled
by the excellent [`inflect`](https://github.com/jaraco/inflect) library.

This approach has two main benefits:
  1. It clearly distinguishes the target of the collection from the scalar helper methods.
  2. It encourages sensible naming of collections (i.e. plural names).

If `inflect` cannot find a singular form either because the attribute name was
not plural, or the plural form is the same as the singular form, or the plural
form overlaps with an existing attribute, then a suffix of `_item` will be used
instead. If the resulting singular form overlaps with an existing attribute, a
`RuntimeError` is raised and the user is invited to remedy the problem by
renaming the attribute(s).

By way of example, here are a few mappings:

| attribute name | singular form |
| --- | --- |
| numbers | number |
| children | child |
| errata | erratum |
| collection | collection_item |


## Mutable Sequences

The helper method signatures for mutable sequences (including `list`) are:

  - `with_<attr_singular>(_item, *, _index=MISSING, _insert=False, _inplace=False, _if=True)`:
    Adds an element to the collection when `_if` is `True`. If `_index` is
    provided, the item at that index is replaced unless `_insert` is `True` in
    which case the new item is inserted before it. If `_inplace` is `True` then
    the current instance is mutated, otherwise the mutation happens on a
    copy.
  - `update_<attr_singular>(_value_or_index, _new_item=MISSING, *, _by_index=MISSING, _inplace=False, _if=True)`:
    Updates/replaces an element of the collection. Indexing semantics are as for
    `transform_<attr_singular>` below.
  - `transform_<attr_singular>(_value_or_index, _transform, *, _by_index=MISSING, _inplace=False, _if=True)`:
    Transforms an element of the collection if `_if` is `True`. The item to be
    transformed is passed to the callable `_transform`, and is:

    - if `_by_index` is `False`, the first instance of `_value_or_index` in the
      collection.
    - if `_by_index` is `True`, the item at index `_value_or_index`.

    If `_by_index` is not specified, it defaults to `True` if `_value_or_index`
    is not of the same type as as that contained in the sequence. If `_inplace`
    is `True` then the current instance is mutated, otherwise the mutation
    happens on a copy.
  - `without_<attr_singular>(_value_or_index, *, _by_index: bool = False, _inplace: bool = False, _if=True)`:
    Removes an element from the collection if `_if` is `True`. The item to be
    removed is:

    - if `_by_index` is `False`, the first instance of `_value_or_index` in the
      collection.
    - if `_by_index` is `True`, the item at index `_value_or_index`.

    If `_by_index` is not specified, it defaults to `True` if `_value_or_index`
    is not of the same type as as that contained in the sequence. If `_inplace`
    is `True` then the current instance is mutated, otherwise the mutation
    happens on a copy.

```python
@spec_class
class FavoriteNumbers:
    numbers: List[int] = []

assert FavoriteNumbers().with_number(10).without_number(10).numbers == []
```

## Mutable Mappings

The helper method signatures for mutable mappings (including `dict`) are:

  - `with_<attr_singular>(_key, _value, *, _inplace=False, _if=True)`:
    Adds an element to the collection when `_if` is `True` by setting the value
    assigned to key `_key` to value `_value`. If `_inplace` is `True` then the
    current instance is mutated, otherwise the mutation happens on a copy.
  - `update_<attr_singular>(_key, _new_item=MISSING, *, _inplace=False, _if=True)`:
    Updates/replaces an element of the collection when `_if` is `True`.If
    `_inplace` is `True` then the current instance is mutated, otherwise the
    mutation happens on a copy.
  - `transform_<attr_singular>(_key, _transform, *, _inplace=False, _if=True)`:
    Transforms the value associated with key `_key` by passing it through the
    callable `_transform` when `_if` is `True`. If `_inplace` is `True` then the
    current instance is mutated, otherwise the mutation happens on a copy.
  - `without_<attr_singular>(_key, *, _inplace: bool = False, _if=True)`:
    Removes the mapping for `_key` from the collection when `_if` is `True`. If
    `_inplace` is `True` then the current instance is mutated, otherwise the
    mutation happens on a copy.

```python
@spec_class
class ExaminationScores:
    scores: Dict[str, float] = {}

assert (
    ExaminationScores()
    .with_score("Peter", 10.1)
    .with_score("Justine", 13.3)
    .without_score("Peter")
    .scores
) == {'Peter': 10.1}
```

## Mutable Sets

The helper method signatures for mutable sets (including `set`) are:

  - `with_<attr_singular>(_item, *, _inplace=False, _if=True)`:
    Adds the nominated element `_item` to the collection when `_if` is `True`.
    If `_inplace` is `True` then the current instance is mutated, otherwise the
    mutation happens on a copy.
  - `update_<attr_singular>(_item, _new_item=MISSING, *, _inplace=False, _if=True)`:
    Updates/replaces an element of the collection when `_if` is `True`. If
    `_inplace` is `True` then the current instance is mutated, otherwise the
    mutation happens on a copy.
  - `transform_<attr_singular>(_item, _transform, *, _inplace=False, _if=True)`:
    Transforms the nominated `_item` by passing it through the callable
    `_transform` when `_if` is `True`. If `_inplace` is `True` then the current
    instance is mutated, otherwise the mutation happens on a copy.
  - `without_<attr_singular>(_item, *, _inplace: bool = False, _if=True)`:
    Removes `_item` from the collection when `_if` is `True`. If `_inplace` is
    `True` then the current instance is mutated, otherwise the mutation happens
    on a copy.

```python
@spec_class
class FavoriteNumbers:
    numbers: Set[int]

assert (
    FavoriteNumbers()
    .with_number(1)
    .with_number(2)
    .transform_number(1, lambda x: x+1)
    .without_number(2)
    .numbers
) == set()
```

## Extensions for spec-class types

Just as for the scalar methods, if the item stored within any of the collections
above is a spec-class, then the `.with_<attr_singular>()` and
`.transform_<attr_singular>()` method signatures are extended with to allow
direct mutation of the attributes of the nested spec classes. The following
example is for sequence containers but the logic is the same for all
collections.

```python
@spec_class
class Box:
    label: str
    items: List[str]
    children: List["Box"]

help(Box().with_child)
# with_child(_item: __main__.Box = MISSING, *, _index: int = MISSING, _insert: bool = False, _inplace: bool = False, _if: bool = True, label: str = None, items: List[str] = None, children: List[__main__.Box] = None) method of __main__.Box instance
#     Return a `Box` instance identical to this one except with an item added to or updated in `children`.
#
#     Args:
#         _item: A new `Box` instance for children.
#         _index: Index for which to insert or replace, depending on `insert`;
#             if not provided, append.
#         _insert: Insert item before children[index], otherwise replace this
#             index.
#         _inplace: Whether to perform change without first copying.
#         _if: This action is only taken when `_if` is `True`. If it is `False`,
#             this is a no-op.
#         label: An optional new value for `child.label`.
#         items: An optional new value for `child.items`.
#         children: An optional new value for `child.children`.
#     Returns:
#         A reference to the mutated `Box` instance.

help(Box().transform_child)
# transform_child(_value_or_index: Union[__main__.Box, int], _transform: Callable = MISSING, *, _by_index: bool = MISSING, _inplace: bool = False, _if: bool = True, label: str = None, items: List[str] = None, childre
# n: List[__main__.Box] = None) method of __main__.Box instance
#     Return a `Box` instance identical to this one except with an item transformed in `children`.
#
#     Args:
#         _value_or_index: The value to transform, or (if `by_index=True`) its
#             index.
#         _transform: A function that takes the old item as input, and returns
#             the new item.
#         _by_index: If True, value_or_index is the index of the item to
#             transform.
#         _inplace: Whether to perform change without first copying.
#         _if: This action is only taken when `_if` is `True`. If it is `False`,
#             this is a no-op.
#         label: An optional transformer for `child.label`.
#         items: An optional transformer for `child.items`.
#         children: An optional transformer for `child.children`.
#     Returns:
#         A reference to the mutated `Box` instance.
```