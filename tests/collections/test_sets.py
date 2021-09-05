import re
from typing import Set

import pytest

from spec_classes import Attr, MISSING, spec_class
from spec_classes.collections import SetMutator
from spec_classes.types import KeyedSet


@spec_class(key="key")
class Spec:
    key: str
    a: int


class TestSetMutator:
    @pytest.fixture
    def attr_spec(self):
        return Attr.from_attr_value(
            "attr", "value", type=Set[str], prepare_item=lambda self, x: str(x)
        )

    @pytest.fixture
    def attr_spec2(self):
        return Attr.from_attr_value("attr", "value", type=KeyedSet[Spec, str])

    def test_cow(self, attr_spec):
        c = {"a"}
        s = SetMutator(attr_spec, object(), collection=c)
        assert s.collection is c

        s = SetMutator(attr_spec, object(), collection=c, inplace=False)
        assert s.collection is not c

    def test_prepare(self, attr_spec):
        s = SetMutator(attr_spec, object())

        assert s.collection is MISSING
        s.prepare()
        assert s.collection == set()

        s = SetMutator(attr_spec, object(), collection={1, 2})

        assert s.collection == {1, 2}
        s.prepare()
        assert s.collection == {"1", "2"}

        assert s.collection == {"1", "2"}
        s.prepare()
        assert s.collection == {"1", "2"}

    def test_add_item(self, attr_spec, attr_spec2):
        s = SetMutator(attr_spec, object())

        s.add_item("a")
        assert s.collection == {"a"}

        s2 = SetMutator(attr_spec2, object())

        s2.add_item("a")
        assert list(s2.collection) == [Spec("a")]

        s2.add_item("b", attrs={"a": 10})
        assert sorted(s2.collection, key=lambda x: x.key) == [
            Spec("a"),
            Spec("b", a=10),
        ]

        with pytest.raises(
            ValueError,
            match=re.escape(
                "Attempted to add an invalid item `1` to `attr`. Expected item of type `Spec`."
            ),
        ):
            s2.add_item(1)

    def test_add_items(self, attr_spec):
        s = SetMutator(attr_spec, object())
        s.add_items({"a", "b"})
        assert s.collection == {"a", "b"}

        with pytest.raises(
            TypeError,
            match=re.escape("Incoming collection for `attr` is not iterable."),
        ):
            s.add_items(1)

    def test_transform_item(self, attr_spec):
        s = SetMutator(attr_spec, object(), collection={"a", "b"})
        s.transform_item("a", lambda x: x + "+")
        assert s.collection == {"a+", "b"}

        with pytest.raises(
            ValueError, match=re.escape("Value `'c'` not found in collection `attr`.")
        ):
            s.transform_item("c", lambda x: x)

    def test_remove_item(self, attr_spec):
        s = SetMutator(attr_spec, object(), collection={"a", "b"})
        s.remove_item("a")
        assert s.collection == {"b"}

        with pytest.raises(
            ValueError, match=re.escape("Value `'c'` not found in collection `attr`.")
        ):
            s.remove_item("c")
