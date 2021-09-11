import re
from typing import List

import pytest

from spec_classes import Attr, MISSING, spec_class
from spec_classes.collections import SequenceMutator


@spec_class(key="key")
class Spec:
    key: str
    a: int


class TestSequenceMutator:
    @pytest.fixture
    def attr_spec(self):
        return Attr.from_attr_value(
            "attr", "value", type=List[str], prepare_item=lambda self, x: str(x)
        )

    @pytest.fixture
    def attr_spec2(self):
        return Attr.from_attr_value("attr", "value", type=List[Spec])

    def test_cow(self, attr_spec):
        c = [1, 2, 3]
        s = SequenceMutator(attr_spec, object(), collection=c)
        assert s.collection is c

        s = SequenceMutator(attr_spec, object(), collection=c, inplace=False)
        assert s.collection is not c

    def test_prepare(self, attr_spec):
        s = SequenceMutator(attr_spec, object())

        assert s.collection is MISSING
        s.prepare()
        assert s.collection == []

        s = SequenceMutator(attr_spec, object(), collection=[1, 2, 3])

        assert s.collection == [1, 2, 3]
        s.prepare()
        assert s.collection == ["1", "2", "3"]

        assert s.collection == ["1", "2", "3"]
        s.prepare()
        assert s.collection == ["1", "2", "3"]

    def test_add_item(self, attr_spec, attr_spec2):
        s = SequenceMutator(attr_spec, object())

        s.add_item("a")
        assert s.collection == ["a"]

        s2 = SequenceMutator(attr_spec2, object())

        s2.add_item("a")
        assert s2.collection == [Spec("a")]

        s2.add_item("b", attrs={"a": 10})
        assert s2.collection == [Spec("a"), Spec("b", a=10)]

        s2.add_item("c", value_or_index=0)
        assert s2.collection == [Spec("c"), Spec("b", a=10)]

        s2.add_item("d", value_or_index=10, insert=True)
        assert s2.collection == [Spec("c"), Spec("b", a=10), Spec("d")]

        with pytest.raises(
            ValueError,
            match=re.escape(
                "Attempted to add an invalid item `1` to `attr`. Expected item of type `Spec`."
            ),
        ):
            s2.add_item(1)

    def test_add_items(self, attr_spec):
        s = SequenceMutator(attr_spec, object())
        s.add_items([1, 2, 3])
        assert s.collection == ["1", "2", "3"]

        with pytest.raises(
            TypeError,
            match=re.escape("Incoming collection for `attr` is not iterable."),
        ):
            s.add_items(1)

    def test_transform_item(self, attr_spec):
        s = SequenceMutator(attr_spec, object(), collection=["1", "2", "3"])
        s.transform_item(0, lambda x: x + "0")
        assert s.collection == ["10", "2", "3"]
        s.transform_item("10", lambda x: x + "0")
        assert s.collection == ["100", "2", "3"]

        with pytest.raises(
            IndexError, match=re.escape("Index `10` not found in collection `attr`.")
        ):
            s.transform_item(10, lambda x: x)

        with pytest.raises(
            ValueError, match=re.escape("Item `'10'` not found in collection `attr`.")
        ):
            s.transform_item("10", lambda x: x)

    def test_remove_item(self, attr_spec):
        s = SequenceMutator(attr_spec, object(), collection=["1", "2", "3"])
        s.remove_item(0)
        assert s.collection == ["2", "3"]
        s.remove_item("3")
        assert s.collection == ["2"]

        with pytest.raises(
            IndexError, match=re.escape("Index `10` not found in collection `attr`.")
        ):
            s.remove_item(10)

        with pytest.raises(
            ValueError, match=re.escape("Item `'10'` not found in collection `attr`.")
        ):
            s.remove_item("10")
