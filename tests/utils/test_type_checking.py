import sys
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union

from typing_extensions import Literal, NotRequired, Required, TypedDict

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

        assert check_type([], List)
        assert not check_type("a", List)
        assert check_type(["a", "b"], List[str])
        assert not check_type([1, 2], List[str])

        assert check_type((), Tuple)
        assert check_type((1, "a"), Tuple[int, str])
        assert not check_type((1,), Tuple[str])
        assert not check_type(("1", 2), Tuple[str, ...])

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

        class MyType:
            pass

        class SubType(MyType):
            pass

        assert check_type(MyType, Type[MyType])
        assert check_type(SubType, Type[MyType])

        assert check_type(1, float)
        assert not check_type(1.0, int)

        if sys.version_info >= (3, 9):
            assert check_type(["a", "b"], list[str])
            assert check_type((1, 2, 3, 4), tuple[int, ...])
            assert check_type((1, 2, 3), tuple[int, int, float])
            assert not check_type((1, 2, 3), tuple[int, int])
            assert not check_type({1: "a", 2: "b"}, dict[str, int])
            assert not check_type({1, 2}, set[str])
            assert not check_type(str, type[MyType])

        if sys.version_info >= (3, 10):
            assert check_type([1, "a"], list[str | int])

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
        assert type_label(Union[Any, Dict[str, int]]) == "Any | dict[str, int]"
        assert type_label(Literal["a", True, 3, b"c"]) == "Literal['a', True, 3, b'c']"
        assert type_label(Union[str, int]) == "str | int"
        assert type_label(Optional[int]) == "int | None"

        if sys.version_info >= (3, 10):
            assert type_label(str | int) == "str | int"

    def test_type_instantiate(self):
        assert type_instantiate(str) == ""
        assert type_instantiate(list) == []
        assert type_instantiate(List[str]) == []
        assert type_instantiate(dict, a=1) == {"a": 1}
        assert type_instantiate(Dict[str, int], a=1) == {"a": 1}

    def test_typed_dict(self):
        class Movie(TypedDict):
            name: str
            year: int

        assert check_type({"name": "The Matrix", "year": 1999}, Movie)
        assert not check_type({"name": "The Matrix"}, Movie)
        assert not check_type({"name": "The Matrix", "year": "1999"}, Movie)

        class NonTotalMovie(TypedDict, total=False):
            name: str
            year: int

        assert check_type({"name": "The Matrix", "year": 1999}, NonTotalMovie)
        assert check_type({"name": "The Matrix"}, NonTotalMovie)

        class AnnotatedMovie(TypedDict):
            name: Required[str]
            year: NotRequired[int]

        assert check_type({"name": "The Matrix"}, AnnotatedMovie)
        assert not check_type({"year": 1999}, AnnotatedMovie)

        class PartiallyAnnotatedMovie(TypedDict):
            name: str
            year: NotRequired[int]

        assert check_type({"name": "The Matrix"}, PartiallyAnnotatedMovie)
        assert not check_type({"year": 1999}, PartiallyAnnotatedMovie)

        class PartiallyAnnotatedMovie2(TypedDict, total=False):
            name: Required[str]
            year: int

        assert check_type({"name": "The Matrix"}, PartiallyAnnotatedMovie2)
        assert not check_type({"year": 1999}, PartiallyAnnotatedMovie2)
