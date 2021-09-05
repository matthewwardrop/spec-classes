import re
from typing import Dict

import pytest

from spec_classes import Attr, MISSING, spec_class
from spec_classes.collections import MappingMutator


@spec_class(key="key")
class Spec:
    key: str
    a: int


class TestMappingMutator:
    @pytest.fixture
    def attr_spec(self):
        return Attr.from_attr_value(
            "attr", "value", type=Dict[str, str], prepare_item=lambda self, x: str(x)
        )

    @pytest.fixture
    def attr_spec2(self):
        return Attr.from_attr_value("attr", "value", type=Dict[str, Spec])

    def test_cow(self, attr_spec):
        c = {"a": 1}
        s = MappingMutator(attr_spec, object(), collection=c)
        assert s.collection is c

        s = MappingMutator(attr_spec, object(), collection=c, inplace=False)
        assert s.collection is not c

    def test_prepare(self, attr_spec):
        s = MappingMutator(attr_spec, object())

        assert s.collection is MISSING
        s.prepare()
        assert s.collection == {}

        s = MappingMutator(attr_spec, object(), collection={"a": 1, "b": 2})

        assert s.collection == {"a": 1, "b": 2}
        s.prepare()
        assert s.collection == {"a": "1", "b": "2"}

        assert s.collection == {"a": "1", "b": "2"}
        s.prepare()
        assert s.collection == {"a": "1", "b": "2"}

    def test_add_item(self, attr_spec, attr_spec2):
        s = MappingMutator(attr_spec, object())

        s.add_item("a", "1")
        assert s.collection == {"a": "1"}

        s2 = MappingMutator(attr_spec2, object())

        s2.add_item("a", "1")
        assert s2.collection == {"a": Spec("1")}

        s2.add_item("b", "2", attrs={"a": 10})
        assert s2.collection == {"a": Spec("1"), "b": Spec("2", a=10)}

        with pytest.raises(
            ValueError,
            match=re.escape(
                "Attempted to add an invalid item `1` to `attr`. Expected item of type `Spec`."
            ),
        ):
            s2.add_item("c", 1)

    def test_add_items(self, attr_spec):
        s = MappingMutator(attr_spec, object())
        s.add_items({"a": 1, "b": 2})
        assert s.collection == {"a": "1", "b": "2"}

        with pytest.raises(
            TypeError,
            match=re.escape("Incoming collection for `attr` is not a mapping."),
        ):
            s.add_items(1)

    def test_transform_item(self, attr_spec):
        s = MappingMutator(attr_spec, object(), collection={"a": "1", "b": "2"})
        s.transform_item("a", lambda x: x + "0")
        assert s.collection == {"a": "10", "b": "2"}

        with pytest.raises(
            KeyError, match=re.escape("Key `10` not found in collection `attr`.")
        ):
            s.transform_item(10, lambda x: x)

    def test_remove_item(self, attr_spec):
        s = MappingMutator(attr_spec, object(), collection={"a": "1", "b": "2"})
        s.remove_item("a")
        assert s.collection == {"b": "2"}

        with pytest.raises(
            KeyError, match=re.escape("Key `'c'` not found in collection `attr`.")
        ):
            s.remove_item("c")
