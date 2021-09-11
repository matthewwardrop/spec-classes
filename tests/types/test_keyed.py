# flake8: noqa: E741; Short names are fine here in the tests.

from typing import Set

import pytest

from spec_classes import spec_class
from spec_classes.types import KeyedList, KeyedSet


class TestKeyedList:
    def test_constructor(self):
        l = KeyedList()
        assert l == []
        assert l._list == []
        assert l._dict == {}

        l2 = KeyedList([1, 2, 3])
        assert l2 == [1, 2, 3]
        assert l2._list == [1, 2, 3]
        assert l2._dict == {1: 1, 2: 2, 3: 3}

    def test_getitem(self):
        l = KeyedList([1, 2, 3], key=str)
        assert 0 not in l
        assert 2 in l
        assert l[0] == 1
        assert l["1"] == 1
        assert l[1] == 2
        assert l["2"] == 2
        with pytest.raises(IndexError):
            l[3]
        with pytest.raises(KeyError):
            l["4"]

        sliced = l[1:3]
        assert isinstance(sliced, KeyedList)
        assert sliced[0] == 2
        assert sliced["2"] == 2

    def test_setitem(self):
        l = KeyedList([1, 2, 3], key=str)

        l[0] = 10
        assert l[0] == 10
        assert l["10"] == 10
        with pytest.raises(KeyError):
            l["1"]

        l["10"] = 1
        assert l[0] == 1
        assert l["1"] == 1
        with pytest.raises(KeyError, match=r"'10'"):
            l["10"]

        with pytest.raises(KeyError, match=r"'10'"):
            l["10"] = 10

        with pytest.raises(
            RuntimeError, match=r"Cannot assign multiple values at a time\."
        ):
            l[0:10] = range(10)

    def test_delitem(self):
        l = KeyedList([1, 2, 3], key=str)

        del l[0]
        assert l[0] == 2
        assert l["2"] == 2
        assert len(l) == 2
        with pytest.raises(KeyError, match="'1'"):
            l["1"]

        del l["2"]
        assert l[0] == 3
        assert l["3"] == 3
        assert len(l) == 1
        with pytest.raises(KeyError, match="'2'"):
            l["2"]

        with pytest.raises(KeyError, match=r"'10'"):
            del l["10"]

        with pytest.raises(
            RuntimeError, match=r"Cannot delete multiple values at a time\."
        ):
            del l[0:10]

    def test_duplicate_keys(self):
        with pytest.raises(
            ValueError, match=r"Item with key `'1'` already in `KeyedList`\."
        ):
            KeyedList([1, 1], key=str)

    def test_dict_behaviors(self):
        l = KeyedList([1, 2, 3], key=str)

        assert list(l.keys()) == ["1", "2", "3"]
        assert list(l.items()) == [("1", 1), ("2", 2), ("3", 3)]
        assert "1" in l
        assert {} not in l
        assert l.get("1") == 1
        assert l.get("10") is None
        assert l.get("10", 10) == 10
        assert l.index_for_key("1") == 0
        assert l.index_for_key("2") == 1

        with pytest.raises(KeyError, match=r"'10'"):
            l.index_for_key("10")

    def test_equality(self):
        assert KeyedList([1, 2, 3, 4]) == KeyedList([1, 2, 3, 4])
        assert KeyedList([1, 2, 3, 4]) == [1, 2, 3, 4]
        assert KeyedList([1, 2, 3, 4]) != KeyedList([1, 2, 3])
        assert KeyedList([1, 2, 3, 4]) != "hi"

    def test_addition(self):
        assert KeyedList([1, 2]) + KeyedList([3, 4]) == [1, 2, 3, 4]
        assert KeyedList([1, 2]) + [3, 4] == [1, 2, 3, 4]
        assert [1, 2] + KeyedList([3, 4]) == [1, 2, 3, 4]

        with pytest.raises(TypeError):
            KeyedList([1, 2]) + 1

        with pytest.raises(TypeError):
            1 + KeyedList([1, 2])

    def test_repr(self):
        assert repr(KeyedList([1, 2])) == "KeyedList([1, 2])"
        assert repr(KeyedList[int, int]([1, 2])) == "KeyedList[int, int]([1, 2])"

    def test_typed(self):
        assert KeyedList[int, int]([1, 2, 3]) == [1, 2, 3]
        assert KeyedList[int, str]([1, 2, 3], key=str) == [1, 2, 3]

        with pytest.raises(
            TypeError, match="Invalid item type. Got: `1`; Expected instance of: `str`."
        ):
            KeyedList[str, str]([1, 2, 3], key=str)
        with pytest.raises(
            TypeError,
            match="Invalid key type. Got: `'1'`; Expected instance of: `int`.",
        ):
            KeyedList[int, int]([1, 2, 3], key=str)

    def test_spec_class(self):
        @spec_class(key="key")
        class KeyedSpec:
            key: str
            value: int

        @spec_class
        class Spec:
            keyed_items: KeyedList[KeyedSpec, str]

        assert Spec(keyed_items=[KeyedSpec("a")]).keyed_items == [KeyedSpec("a")]

        s = Spec()
        assert s.with_keyed_item(KeyedSpec("a")).keyed_items == [KeyedSpec("a")]
        assert s.with_keyed_item("a").keyed_items == [KeyedSpec("a")]
        assert s.with_keyed_item("a", value=3).keyed_items == [KeyedSpec("a", value=3)]

    def test_edge_cases(self):
        with pytest.raises(TypeError, match=r"Key extractor for .*"):
            KeyedList([{1}, {2}, {3}])

    def test_spec_class_type_check_hook(self):
        l = KeyedList([1, 2, 3])

        assert KeyedList.__spec_class_check_type__(l, KeyedList)
        assert KeyedList.__spec_class_check_type__(l, KeyedList[int, int])
        assert not KeyedList.__spec_class_check_type__("hi", KeyedList)
        assert not KeyedList.__spec_class_check_type__(l, KeyedList[str, int])
        assert not KeyedList.__spec_class_check_type__(l, KeyedList[int, str])
        assert not KeyedList.__spec_class_check_type__(l, KeyedList[str, str])


class TestKeyedSet:
    def test_constructor(self):
        s = KeyedSet()
        assert set(s) == set()
        assert s._dict == {}

        s2 = KeyedSet({1, 2, 3}, key=str)
        assert s2._dict == {"1": 1, "2": 2, "3": 3}

    def test_contains(self):
        s = KeyedSet({1, 2, 3}, key=str)
        assert 1 in s
        assert "1" in s
        assert 4 not in s
        assert "4" not in s

    def test_iter(self):
        s = KeyedSet({1, 2, 3}, key=str)
        assert set(iter(s)) == {1, 2, 3}

    def test_len(self):
        assert len(KeyedSet({1, 2, 3}, key=str)) == 3

    def test_add(self):
        s = KeyedSet({1, 2, 3}, key=str)
        s.add(4)
        assert 4 in s

    def test_discard(self):
        s = KeyedSet({1, 2, 3}, key=str)

        s.discard(4)
        assert len(s) == 3

        s.discard(2)
        assert set(s) == {1, 3}

        s.discard("1")
        assert set(s) == {3}

    def test_equality(self):
        s = KeyedSet({1, 2, 3}, key=str)
        assert s == {1, 2, 3}
        assert s != KeyedSet({1, 2}, key=str)
        assert s == KeyedSet({1, 2, 3}, key=str)
        assert s != "hi"

    def test_repr(self):
        s = KeyedSet({1, 2, 3}, key=str)
        assert repr(s) == "KeyedSet({1, 2, 3})"

        s2 = KeyedSet[int, str]({1, 2, 3}, key=str)
        assert repr(s2) == "KeyedSet[int, str]({1, 2, 3})"

    def test_dict_feature(self):
        s = KeyedSet({1, 2, 3}, key=str)

        assert list(s.keys()) == ["1", "2", "3"]
        assert s["1"] == 1
        assert s[1] == 1
        assert s.get("4") is None
        assert list(s.items()) == [("1", 1), ("2", 2), ("3", 3)]

    def test_item_equivalence(self):
        @spec_class(key="key")
        class Item:
            key: str
            name: str

        s = KeyedSet[Item, str](
            [Item("a"), Item("b"), Item("c")], enforce_item_equivalence=True
        )

        assert Item("a") in s
        assert Item("a", name="blah") not in s

        s.add(Item("a"))
        with pytest.raises(
            ValueError,
            match=r"Item for `'a'` already exists, and is not equal to the incoming item.",
        ):
            s.add(Item("a", name="blah"))

    def test_edge_cases(self):
        s = KeyedSet[Set[int], int]([{1}, {1, 2}, {1, 2, 3}], key=len)
        assert {1} in s
        assert 10 not in s
        assert s != {1, 2, 3}

        s.discard({1})
        assert sorted(s, key=len) == [{1, 2}, {1, 2, 3}]
        s.discard(10)
        assert sorted(s, key=len) == [{1, 2}, {1, 2, 3}]

    def test_spec_class(self):
        @spec_class(key="key")
        class KeyedSpec:
            key: str
            value: int

        @spec_class
        class Spec:
            keyed_items: KeyedList[KeyedSpec, str]

        assert list(Spec(keyed_items=[KeyedSpec("a")]).keyed_items) == [KeyedSpec("a")]

        s = Spec()
        assert list(s.with_keyed_item(KeyedSpec("a")).keyed_items) == [KeyedSpec("a")]
        assert list(s.with_keyed_item("a").keyed_items) == [KeyedSpec("a")]
        assert list(s.with_keyed_item("a", value=3).keyed_items) == [
            KeyedSpec("a", value=3)
        ]
