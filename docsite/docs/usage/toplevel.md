Spec-classes are furnished with several high-level mutation methods that
simplify (and allow chaining) of copy-on-write mutations.

They are:

  - `update(_new_value, *, _inplace=False, _if=True, **<spec-attributes>)`:
    Returns `_new_value` and/or an instance with the nominated attribute
    values mutated.
  - `transform(_transform, *, _inplace=False, _if=True, **<transforms for
    attributes>)`: Returns the output of `_transform(<spec_class_instance>)` if
    `_transform` is supplied, and/or with its attributes mutated if they are
    passed via kwargs.
  - `reset(*, _inplace=False, _if=True)`: Resets all spec-class attributes to
    their default values.

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
box_modified = box.update(width=10., height=10., depth=10.)
box_modified  # Box(width=10.0, height=10.0, depth=10.0, color='red')
box_modified.volume  # 1000.0
box_modified.transform(width=lambda width: width * 2).volume  # 2000.0
box_modified.reset().color  # 'blue'
assert box is not box_modified

box_modified2 = box.update(width=10., height=10., depth=10., _inplace=True)
assert box is box_modified2
```

As with all spec-class methods, you can look up their documentation:
```python
help(Box().update)
# update(_new_value: __main__.Box = MISSING, *, _inplace: bool = False, _if: bool = True, width: float = MISSING, height: float = MISSING, depth: float = MISSING, color: str = 'blue') method of __main__.Box instance
#     Return `_new_value`, or an `Box` instance identical to this one except with nominated attributes mutated.

#     Args:
#         _new_value: A complete replacement for this instance.
#         _inplace: Whether to perform change without first copying.
#         _if: This action is only taken when `_if` is `True`. If it is `False`,
#             this is a no-op.
#         width: An optional new value for Box.width.
#         height: An optional new value for Box.height.
#         depth: An optional new value for Box.depth.
#         color: An optional new value for Box.color.

#     Returns:
#         `_new_value` or a reference to the mutated `Box` instance.
```
