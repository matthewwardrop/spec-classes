from typing import Any, Callable, Dict, List, Set, TypeVar, Union

from spec_classes import spec_class
from spec_classes.types import KeyedList, KeyedSet
from spec_classes.utils.type_checking import (
    check_type,
    get_collection_item_type,
    get_spec_class_for_type,
    type_instantiate,
    type_label,
)
from typing_extensions import Literal


@spec_class
class Spec:
    pass


@spec_class
class Spec2:
    pass


@spec_class(key="key")
class KeyedSpec:
    key: str


class TestTypeChecking:
    def test_type_checking(self):

        assert check_type("string", str)
        assert check_type([], list)

        assert check_type([], List)
        assert not check_type("a", List)
        assert check_type(["a", "b"], List[str])
        assert not check_type([1, 2], List[str])

        assert check_type({}, Dict)
        assert not check_type("a", Dict)
        assert check_type({"a": 1, "b": 2}, Dict[str, int])
        assert not check_type({"a": "1", "b": "2"}, Dict[str, int])
        assert not check_type({1: "a", 2: "b"}, Dict[str, int])

        assert check_type(set(), Set)
        assert not check_type("a", Set)
        assert check_type({"a", "b"}, Set[str])
        assert not check_type({1, 2}, Set[str])

        assert check_type(lambda x: x, Callable)

        assert check_type([1, "a"], List[Union[str, int]])

        assert check_type("hi", Literal["hi"])
        assert not check_type(1, Literal["hi"])

    def test_get_collection_item_type(self):
        assert get_collection_item_type(list) is Any
        assert get_collection_item_type(List) is Any
        assert get_collection_item_type(List[str]) is str
        assert get_collection_item_type(Dict[str, int]) is int
        assert get_collection_item_type(Set[str]) is str
        assert get_collection_item_type(KeyedList[KeyedSpec, str]) is KeyedSpec
        assert get_collection_item_type(KeyedSet[KeyedSpec, str]) is KeyedSpec
        assert get_collection_item_type(TypeVar("typed_var")) is Any  # noqa: F821
        assert get_collection_item_type(List[TypeVar("typed_var")]) is Any  # noqa: F821

    def test_get_spec_class_for_type(self):
        assert get_spec_class_for_type(Spec) is Spec
        assert get_spec_class_for_type(Union[str, Spec]) is None
        assert get_spec_class_for_type(Union[str, Spec], allow_polymorphic=True) is Spec
        assert (
            get_spec_class_for_type(Union[str, Spec, Spec2], allow_polymorphic=True)
            is None
        )

        assert get_spec_class_for_type(list) is None
        assert get_spec_class_for_type(List) is None
        assert get_spec_class_for_type(List[Spec]) is None

    def test_attr_type_label(self):
        assert type_label(str) == "str"
        assert type_label(object) == "object"
        assert type_label(Spec) == "Spec"
        assert type_label(List) == "list"
        assert type_label(List[str]) == "list[str]"
        assert type_label(KeyedList[KeyedSpec, str]) == "KeyedList[KeyedSpec, str]"
        assert type_label(KeyedSet[KeyedSpec, str]) == "KeyedSet[KeyedSpec, str]"
        assert type_label("") == "str"
        assert type_label(KeyedList[KeyedSpec, str]()) == "KeyedList[KeyedSpec, str]"
        assert type_label(Any) == "Any"
        assert type_label(Union[Any, Dict[str, int]]) == "Union[Any, dict[str, int]]"

    def test_type_instantiate(self):
        assert type_instantiate(str) == ""
        assert type_instantiate(list) == []
        assert type_instantiate(List[str]) == []
        assert type_instantiate(dict, a=1) == {"a": 1}
        assert type_instantiate(Dict[str, int], a=1) == {"a": 1}
