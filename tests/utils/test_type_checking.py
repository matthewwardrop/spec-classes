from collections.abc import Callable
from typing import (
    Any,
    Literal,
    Optional,
    TypeVar,
    Union,
)

from spec_classes import spec_class
from spec_classes.types import KeyedList, KeyedSet
from spec_classes.utils.type_checking import (
    check_type,
    get_collection_item_type,
    get_spec_class_for_type,
    type_instantiate,
    type_label,
)


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

        assert check_type([], list)
        assert not check_type("a", list)
        assert check_type(["a", "b"], list[str])
        assert not check_type([1, 2], list[str])

        assert check_type((), tuple)
        assert check_type((1, "a"), tuple[int, str])
        assert not check_type((1,), tuple[str])
        assert not check_type(("1", 2), tuple[str, ...])

        assert check_type({}, dict)
        assert not check_type("a", dict)
        assert check_type({"a": 1, "b": 2}, dict[str, int])
        assert not check_type({"a": "1", "b": "2"}, dict[str, int])
        assert not check_type({1: "a", 2: "b"}, dict[str, int])

        assert check_type(set(), set)
        assert not check_type("a", set)
        assert check_type({"a", "b"}, set[str])
        assert not check_type({1, 2}, set[str])

        assert check_type(lambda x: x, Callable)

        assert check_type([1, "a"], list[str | int])

        assert check_type("hi", Literal["hi"])
        assert not check_type(1, Literal["hi"])

        class MyType:
            pass

        class SubType(MyType):
            pass

        assert check_type(MyType, type[MyType])
        assert check_type(SubType, type[MyType])
        assert check_type(1, float)
        assert not check_type(1.0, int)
        assert check_type(["a", "b"], list[str])
        assert check_type((1, 2, 3, 4), tuple[int, ...])
        assert check_type((1, 2, 3), tuple[int, int, float])
        assert not check_type((1, 2, 3), tuple[int, int])
        assert not check_type({1: "a", 2: "b"}, dict[str, int])
        assert not check_type({1, 2}, set[str])
        assert not check_type(str, type[MyType])
        assert check_type([1, "a"], list[str | int])

    def test_get_collection_item_type(self):
        assert get_collection_item_type(list) is Any
        assert get_collection_item_type(list) is Any
        assert get_collection_item_type(list[str]) is str
        assert get_collection_item_type(dict[str, int]) is int
        assert get_collection_item_type(set[str]) is str
        assert get_collection_item_type(KeyedList[KeyedSpec, str]) is KeyedSpec
        assert get_collection_item_type(KeyedSet[KeyedSpec, str]) is KeyedSpec
        assert get_collection_item_type(TypeVar("typed_var")) is Any  # noqa: F821
        assert get_collection_item_type(list[TypeVar("typed_var")]) is Any  # noqa: F821

    def test_get_spec_class_for_type(self):
        assert get_spec_class_for_type(Spec) is Spec
        assert get_spec_class_for_type(str | Spec) is None
        assert get_spec_class_for_type(str | Spec, allow_polymorphic=True) is Spec
        assert (
            get_spec_class_for_type(str | Spec | Spec2, allow_polymorphic=True) is None
        )

        assert get_spec_class_for_type(list) is None
        assert get_spec_class_for_type(list) is None
        assert get_spec_class_for_type(list[Spec]) is None

    def test_attr_type_label(self):
        assert type_label(str) == "str"
        assert type_label(object) == "object"
        assert type_label(Spec) == "Spec"
        assert type_label(list) == "list"
        assert type_label(list[str]) == "list[str]"
        assert type_label(KeyedList[KeyedSpec, str]) == "KeyedList[KeyedSpec, str]"
        assert type_label(KeyedSet[KeyedSpec, str]) == "KeyedSet[KeyedSpec, str]"
        assert type_label("") == "str"
        assert type_label(KeyedList[KeyedSpec, str]()) == "KeyedList[KeyedSpec, str]"
        assert type_label(Any) == "Any"
        assert type_label(Union[Any, dict[str, int]]) == "Any | dict[str, int]"  # noqa
        assert type_label(Literal["a", True, 3, b"c"]) == "Literal['a', True, 3, b'c']"
        assert type_label(Union[str, int]) == "str | int"  # noqa
        assert type_label(Optional[int]) == "int | None"  # noqa
        assert type_label(str | int) == "str | int"

    def test_type_instantiate(self):
        assert type_instantiate(str) == ""
        assert type_instantiate(list) == []
        assert type_instantiate(list[str]) == []
        assert type_instantiate(dict, a=1) == {"a": 1}
        assert type_instantiate(dict[str, int], a=1) == {"a": 1}
