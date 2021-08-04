# flake8: noqa: E741; Short names are fine here in the tests.

import pytest

from spec_classes import spec_class
from spec_classes.types import KeyedList


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

        class UnkeyedSpec:
            pass

        l = KeyedList[KeyedSpec, str]([KeyedSpec("a"), KeyedSpec("b")])
        assert l["a"] == KeyedSpec("a")

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
