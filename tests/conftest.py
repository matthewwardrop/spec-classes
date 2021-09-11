from __future__ import annotations

from typing import Dict, List, Set

import pytest

from spec_classes import spec_class
from spec_classes.spec_class import SpecClassMetadata
from spec_classes.types import KeyedList, KeyedSet


@spec_class(key="key")
class Spec:
    key: str = "key"
    scalar: int
    list_values: List[int]
    dict_values: Dict[str, int]
    set_values: Set[str]
    spec: UnkeyedSpec
    spec_list_items: List[UnkeyedSpec]
    spec_dict_items: Dict[str, UnkeyedSpec]
    keyed_spec_list_items: KeyedList[KeyedSpec, str]
    keyed_spec_dict_items: Dict[str, KeyedSpec]
    keyed_spec_set_items: KeyedSet[KeyedSpec, str]
    recursive: Spec


@spec_class
class UnkeyedSpec:
    nested_scalar: int = 1
    nested_scalar2: str = "original value"


@spec_class(key="key")
class KeyedSpec:
    key: str = "key"
    nested_scalar: int = 1
    nested_scalar2: str = "original value"


@pytest.fixture
def spec_cls():
    assert isinstance(Spec.__spec_class__, SpecClassMetadata)
    return Spec


@pytest.fixture
def unkeyed_spec_cls():
    return UnkeyedSpec


@pytest.fixture
def keyed_spec_cls():
    return KeyedSpec
