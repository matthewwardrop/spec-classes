Every attributed [managed by spec-classes](basic.md#managed-attributes) is
furnished with generated scalar helper methods that simplify incremental
mutation of the attributes and adoption of a copy-on-write workflow.

The methods and their signatures are:

  - `with_<attr>(_new_value, *, _inplace=False, _if=True)`:  Sets
    `<attr>` to `_new_value` if `_if` is `True`. If `_inplace` is `True`, then
    the value is mutated on the current instance.
  - `update_<attr>(_new_value, *, _inplace=False, _if=True)`: Updates an instance
    (this differs from `with_<attr>` in that spec-classes will be incrementally
    updated rather than replaced by this method).
  - `transform_<attr>(_new_value, *, _inplace=False, _if=True)`: If `_if` is
    `True`, applies a function to the current value of `<attr>`, stores the
    result as the new value for `<attr>` on a copy of the spec class instance.
    If `_inplace` is `True`, then the value is mutated on the current instance.
  - `reset_<attr>(_new_value, *, _inplace=False, _if=True)`: Resets the attribute
    back to the default value provided by the class (or `MISSING` if there is no
    default), if `_if` is `True`. If `_inplace` is `True`, then the value is
    mutated on the current instance.

For example:
```python
@spec_class
class Box:
    width: float
    height: float
    depth: float
    color: str = 'blue'

    @property
    def volume(self):
        return self.width * self.height * self.depth

box = Box(color='red')
box  # Box(width=MISSING, height=MISSING, depth=MISSING, color='red')
box_modified = box.with_width(10.).with_height(10.).with_depth(10.)
box_modified  # Box(width=10.0, height=10.0, depth=10.0, color='red')
box_modified.volume  # 1000.0
box_modified.transform_width(lambda width: width * 2).volume  # 2000.0
box_modified.reset_color().color  # 'blue'
assert box is not box_modified

box_modified2 = box.with_width(10., _inplace=True).with_height(10., _inplace=True).with_depth(10., _inplace=True)
assert box is box_modified2
```

## Extensions for spec-class attributes

When the type of the attribute being mutated by these utility methods is also a
spec class, the `with_<attr>` and `transform_<attr>` methods above are extended
to allow direct mutation of the attributes of the nested spec class. For
example:

```python
@spec_class
class Box:
    width: float
    height: float
    depth: float
    color: str

    nested_box: "Box"

help(Box().with_nested_box)
# with_nested_box(_new_value: __main__.Box = MISSING, *, _inplace: bool = False, _if: bool = True, width: float = None, height: float = None, depth: float = None, color: str = None, nested_box: __main__.Box = None) method of __main__.Box instance
#     Return a `Box` instance identical to this one except with `nested_box` or its attributes mutated.
#
#     Args:
#         _new_value: The new value for `nested_box`.
#         _inplace: Whether to perform change without first copying.
#         _if: This action is only taken when `_if` is `True`. If it is `False`,
#             this is a no-op.
#         width: An optional new value for nested_box.width.
#         height: An optional new value for nested_box.height.
#         depth: An optional new value for nested_box.depth.
#         color: An optional new value for nested_box.color.
#         nested_box: An optional new value for nested_box.nested_box.
#     Returns:
#         A reference to the mutated `Box` instance.

help(Box().update_nested_box)
# update_nested_box(_new_value: Callable = MISSING, *, _inplace: bool = False, _if: bool = True, width: float = MISSING, height: float = MISSING, depth: float = MISSING, color: str = MISSING, nested_box: __main__.Box = MISSING) method of __main__.Box instance
#     Return a `Box` instance identical to this one except with `nested_box` or its attributes updated.
#
#     Args:
#         _new_value: An optional value to replace the old value for
#             `nested_box`.
#         _inplace: Whether to perform change without first copying.
#         _if: This action is only taken when `_if` is `True`. If it is `False`,
#             this is a no-op.
#         width: An optional new value for nested_box.width.
#         height: An optional new value for nested_box.height.
#         depth: An optional new value for nested_box.depth.
#         color: An optional new value for nested_box.color.
#         nested_box: An optional new value for nested_box.nested_box.

#     Returns:
#         A reference to the mutated `Box` instance.

help(Box().transform_nested_box)
# transform_nested_box(_transform: Callable = MISSING, *, _inplace: bool = False, _if: bool = True, width: float = None, height: float = None, depth: float = None, color: str = None, nested_box: __main__.Box = None) method of __main__.Box instance
#     Return a `Box` instance identical to this one except with `nested_box` or its attributes transformed.
#
#     Args:
#         _transform: A function that takes the old value for nested_box as
#             input, and returns the new value.
#         _inplace: Whether to perform change without first copying.
#         _if: This action is only taken when `_if` is `True`. If it is `False`,
#             this is a no-op.
#         width: An optional transformer for nested_box.width.
#         height: An optional transformer for nested_box.height.
#         depth: An optional transformer for nested_box.depth.
#         color: An optional transformer for nested_box.color.
#         nested_box: An optional transformer for nested_box.nested_box.
#     Returns:
#         A reference to the mutated `Box` instance.

(
  Box()
  .with_nested_box(width=10., height=10., depth=10., color='red')
  .update_nested_box(width=30.)
  # Using `with_nested_box` instead would reset other properties to their default values.
)
# Box(
#     width=MISSING,
#     height=MISSING,
#     depth=MISSING,
#     color=MISSING,
#     nested_box=Box(
#         width=30.0,
#         height=10.0,
#         depth=10.0,
#         color='red',
#         nested_box=MISSING
#     )
# )

```
