from typing import List

import pytest
from lazy_object_proxy import Proxy

from spec_classes import spec_class, MISSING
from spec_classes.utils.mutation import mutate_attr, mutate_value


@spec_class(key='key')
class Spec:
    key: str = 'key'
    scalar: int
    list_values: List[int]


def test_mutate_attr():
    @spec_class
    class Item:
        attr: str

    item = Item()

    with pytest.raises(AttributeError, match=r"`Item\.attr` has not yet been assigned a value\."):
        item.attr
    with pytest.raises(AttributeError, match=r"`Item\.attr` has not yet been assigned a value\."):
        mutate_attr(item, 'attr', MISSING).attr
    assert mutate_attr(item, 'attr', 'string') is not item
    assert mutate_attr(item, 'attr', 'string').attr == 'string'

    with pytest.raises(TypeError, match="Attempt to set `Item.attr` with an invalid type"):
        assert mutate_attr(item, 'attr', 1)


def test_mutate_value():
    # Simple update
    assert mutate_value(MISSING, new_value="value") == "value"
    assert mutate_value("old_value", new_value="value") == "value"

    # Via constructor
    assert mutate_value(MISSING, constructor=str) == ''
    assert mutate_value(MISSING, constructor=list) == []

    # Via transform
    assert mutate_value("old_value", transform=lambda x: x + "_renewed") == "old_value_renewed"

    # Nested types
    class Object:
        attr = 'default'
    assert mutate_value(MISSING, constructor=Object, attrs={'attr': 'value'}).attr == 'value'
    assert mutate_value(MISSING, constructor=Object, attr_transforms={'attr': lambda x: f'{x}-transformed!'}).attr == 'default-transformed!'
    with pytest.raises(AttributeError, match="'Object' object has no attribute 'missing_attr'"):
        assert mutate_value(MISSING, constructor=Object, attr_transforms={'missing_attr': lambda x: x})

    assert mutate_value(MISSING, constructor=Spec, attrs={'key': 'key', 'scalar': 10}).key == 'key'
    assert mutate_value(MISSING, constructor=Spec, attrs={'key': 'key', 'scalar': 10}).scalar == 10
    assert mutate_value(Spec(key='key', scalar=10), constructor=Spec, attrs={'list_values': [20]}).key == 'key'
    assert mutate_value(Spec(key='key', scalar=10), constructor=Spec, attrs={'list_values': [20]}).scalar == 10
    assert mutate_value(Spec(key='key', scalar=10), constructor=Spec, attrs={'list_values': [20]}).list_values == [20]
    with pytest.raises(TypeError, match="Invalid attribute `invalid_attr` for spec class"):
        assert mutate_value(MISSING, constructor=Spec, attrs={'invalid_attr': 'value'})
    assert mutate_value(MISSING, constructor=Spec, attr_transforms={'key': lambda x: 'override'}).key == 'override'
    with pytest.raises(TypeError, match="Invalid attribute `invalid_attr` for spec class"):
        assert mutate_value(MISSING, constructor=Spec, attr_transforms={'invalid_attr': 'value'})
    assert mutate_value(Spec(key='my_key'), constructor=Spec, replace=True).key == 'key'

    with pytest.raises(ValueError, match="Cannot use attrs on a missing value without a constructor."):
        assert mutate_value(MISSING, attrs={'invalid_attr': 'value'})

    # Test proxied values
    obj = object()
    assert mutate_value(Proxy(lambda: obj)) is obj
