from __future__ import annotations

import sys
from typing import List

import pytest
from lazy_object_proxy import Proxy

from spec_classes import MISSING, spec_class
from spec_classes.utils.mutation import (
    _get_function_args,
    mutate_attr,
    mutate_value,
    protect_via_deepcopy,
)


@spec_class(key="key")
class Spec:
    key: str = "key"
    scalar: int
    list_values: List[int]


@spec_class(init_overflow_attr="kwargs")
class OverflowSpec:
    pass


def test_protect_via_deepcopy():
    a = 1
    b = (1, 2, 3)
    c = [1, 2, 3]
    assert protect_via_deepcopy(a) is a
    assert protect_via_deepcopy(b) is b
    assert protect_via_deepcopy(c) is not c
    assert protect_via_deepcopy(object) is object
    assert protect_via_deepcopy(sys) is sys


def test_mutate_attr():
    @spec_class
    class Item:
        attr: str

    item = Item()

    with pytest.raises(
        AttributeError, match=r"`Item\.attr` has not yet been assigned a value\."
    ):
        item.attr
    with pytest.raises(
        AttributeError, match=r"`Item\.attr` has not yet been assigned a value\."
    ):
        mutate_attr(item, "attr", MISSING).attr
    assert mutate_attr(item, "attr", "string") is not item
    assert mutate_attr(item, "attr", "string").attr == "string"

    with pytest.raises(
        TypeError, match="Attempt to set `Item.attr` with an invalid type"
    ):
        assert mutate_attr(item, "attr", 1)


def test_mutate_value():
    # Simple update
    assert mutate_value(MISSING, new_value="value") == "value"
    assert mutate_value("old_value", new_value="value") == "value"

    # Via constructor
    assert mutate_value(MISSING, constructor=str) == ""
    assert mutate_value(MISSING, constructor=list) == []

    # Via attr_spec spec-class initialization
    @spec_class
    class MySpec:
        a: int

    assert mutate_value(
        MISSING, new_value={"a": 10}, constructor=MySpec, expected_type=MySpec
    ) == MySpec(a=10)

    # Via proxy
    obj = object()
    assert mutate_value(Proxy(lambda: obj)) is obj

    # Via transform
    assert (
        mutate_value("old_value", transform=lambda x: x + "_renewed")
        == "old_value_renewed"
    )

    # Nested types
    class Object:
        attr = "default"

    assert (
        mutate_value(MISSING, constructor=Object, attrs={"attr": "value"}).attr
        == "value"
    )
    assert (
        mutate_value(
            MISSING,
            constructor=Object,
            attr_transforms={"attr": lambda x: f"{x}-transformed!"},
        ).attr
        == "default-transformed!"
    )
    assert not hasattr(
        mutate_value(
            MISSING, constructor=Object, attr_transforms={"missing_attr": lambda x: x}
        ),
        "missing_attr",
    )

    assert (
        mutate_value(MISSING, constructor=Spec, attrs={"key": "key", "scalar": 10}).key
        == "key"
    )
    assert (
        mutate_value(
            MISSING, constructor=Spec, attrs={"key": "key", "scalar": 10}
        ).scalar
        == 10
    )
    assert (
        mutate_value(
            Spec(key="key", scalar=10), constructor=Spec, attrs={"list_values": [20]}
        ).key
        == "key"
    )
    assert (
        mutate_value(
            Spec(key="key", scalar=10), constructor=Spec, attrs={"list_values": [20]}
        ).scalar
        == 10
    )
    assert mutate_value(
        Spec(key="key", scalar=10), constructor=Spec, attrs={"list_values": [20]}
    ).list_values == [20]
    assert (
        mutate_value(
            MISSING, constructor=Spec, attrs={"extra_attr": "value"}
        ).extra_attr
        == "value"
    )
    assert (
        mutate_value(
            MISSING, constructor=Spec, attr_transforms={"key": lambda x: "override"}
        ).key
        == "override"
    )
    assert (
        mutate_value(
            MISSING, constructor=Spec, attr_transforms={"new_attr": lambda x: "value"}
        ).new_attr
        == "value"
    )
    assert mutate_value(Spec(key="my_key"), constructor=Spec, replace=True).key == "key"

    with pytest.raises(
        ValueError, match="Cannot use attrs on a missing value without a constructor."
    ):
        assert mutate_value(MISSING, attrs={"invalid_attr": "value"})

    # Verify that construction is not recursive.
    assert not hasattr(
        mutate_value(MISSING, constructor=Spec, attrs={"scalar": MISSING}), "scalar"
    )


def test__get_function_args():
    attrs = {"key": "value", "extra": "value"}
    _get_function_args(int, attrs) == set()
    _get_function_args(lambda key, missing: 1, attrs) == {"key"}
    _get_function_args(lambda **kwargs: 1, attrs) == {"key", "extra"}
    _get_function_args(Spec, attrs) == {"key"}
    _get_function_args(OverflowSpec, attrs) == {"key", "extra"}
    _get_function_args(sys.exit, attrs) == set()
