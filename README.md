# Spec Classes

This is a small utility package that provides the `spec_cls` decorator
that adds helper methods to allow users to mutate fields.

## Installation

```shell
pip install spec-classes
```

## Documentation
There is not much in the way of standalone documentation, but everything
is documented fairly thoroughly in the source code, or you can
install it and the view the inline documentation using:

```python
>>> from spec_classes import spec_class

>>> help(spec_class)
A class decorator that adds `with_<field>`, `transform_<field>` and
`without_<field>` methods to a class in order to simplify the incremental
building and mutating of specification objects. By default these methods
return a new instance decorated class, with the appropriate field mutated.
...
```

## Examples

```python
@spec_class
class UnkeyedSpec:
    nested_scalar: int = 1
    nested_scalar2: str = 'original value'

@spec_class(key='key')
class KeyedSpec:
    key: str = 'key'
    nested_scalar: int = 1
    nested_scalar2: str = 'original value'


@spec_class(key='key')
class Spec:
    key: str = None
    scalar: int = None
    list_values: List[int] = None
    dict_values: Dict[str, int] = None
    set_values: Set[str] = None
    spec: UnkeyedSpec = None
    spec_list_items: List[UnkeyedSpec] = None
    spec_dict_items: Dict[str, UnkeyedSpec] = None
    keyed_spec_list_items: List[KeyedSpec] = None
    keyed_spec_dict_items: Dict[str, KeyedSpec] = None
    recursive: Spec = None


s = Spec()
spec.with_scalar(3).with_spec_list_item('x')....
```
