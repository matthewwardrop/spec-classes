import dataclasses
import re
from typing import Any, List, Optional

import pytest

from spec_classes import Attr, MISSING, spec_class
from spec_classes.collections import SequenceMutator


class TestAttr:
    def test_from_attr_value(self):
        a = Attr.from_attr_value("attr", "value", compare=False)
        assert a.name == "attr"
        assert a.default == "value"
        assert a.compare is False

        a = Attr.from_attr_value("attr", a)
        assert a.name == "attr"
        assert a.default == "value"
        assert a.compare is False

        f = dataclasses.field(
            default="value",
            init=False,
            repr=False,
            compare=False,
            hash=False,
            metadata={"foo": "bar"},
        )
        a = Attr.from_attr_value("attr", f)
        assert a.name == "attr"
        for attr in {
            "default",
            "default_factory",
            "init",
            "repr",
            "compare",
            "hash",
            "metadata",
        }:
            a_value = getattr(a, attr)
            f_value = getattr(f, attr)
            assert (
                a_value == f_value
                or a_value is MISSING
                and f_value is dataclasses.MISSING
            )

    def test_constructor(self):
        with pytest.raises(
            ValueError,
            match=re.escape(
                "Only one of `default` and `default_factory` can be specified."
            ),
        ):
            Attr(default="Hi", default_factory=lambda: "Hi")

    def test_default_helpers(self):
        assert Attr(default="Hi").has_default
        assert Attr(default_factory=lambda: "Hi").has_default
        assert not Attr().has_default

        assert Attr(default="Hi").default_value == "Hi"
        assert Attr(default_factory=lambda: "Hi").default_value == "Hi"
        assert Attr().default_value is MISSING

    def test_set_name(self):
        class MyClass:
            a: int = Attr(default=Attr())

        assert MyClass.a.name == "a"
        assert MyClass.a.owner is MyClass
        assert MyClass.a.type is int

        # Check that __set_name__ is called on `default` if possible
        assert MyClass.a.default.name == "a"
        assert MyClass.a.default.owner is MyClass
        assert MyClass.a.default.type is int

    def test_derived_attributes(self):
        @spec_class(key="key")
        class MySpec:
            key: str
            field1: int
            field2: str

        class MyClass:
            attr1: MySpec = Attr()
            attr2: List[MySpec] = Attr(default_factory=[])
            attr3: Optional[MySpec] = Attr()
            attr4: List[Optional[MySpec]] = Attr(default_factory=[])

        a1 = MyClass.attr1
        a2 = MyClass.attr2
        a3 = MyClass.attr3
        a4 = MyClass.attr4

        # Qualified name
        a2.owner = None
        assert a1.qualified_name == "MyClass.attr1"
        assert a2.qualified_name == "attr2"
        assert a3.qualified_name == "MyClass.attr3"
        assert a4.qualified_name == "MyClass.attr4"

        # Spec Type
        assert a1.spec_type is MySpec
        assert a2.spec_type is None
        assert a3.spec_type is None
        assert a4.spec_type is None

        # Spec Type (polymorphic)
        assert a1.spec_type_polymorphic is MySpec
        assert a2.spec_type_polymorphic is None
        assert a3.spec_type_polymorphic is MySpec
        assert a4.spec_type_polymorphic is None

        # Is Collection
        assert a1.is_collection is False
        assert a2.is_collection is True
        assert a3.is_collection is False
        assert a4.is_collection is True

        # Collection Mutator Type
        assert a1.collection_mutator_type is None
        assert a2.collection_mutator_type is SequenceMutator
        assert a3.collection_mutator_type is None
        assert a4.collection_mutator_type is SequenceMutator

        # Item Name
        assert a1.item_name == "attr1_item"
        assert a2.item_name == "attr2_item"
        assert a3.item_name == "attr3_item"
        assert a4.item_name == "attr4_item"

        # Item type
        assert a1.item_type is Any
        assert a2.item_type is MySpec
        assert a3.item_type is Any
        assert a4.item_type is Optional[MySpec]

        # Item spec type
        assert a1.item_spec_type is None
        assert a2.item_spec_type is MySpec
        assert a3.item_spec_type is None
        assert a4.item_spec_type is None

        # Item spec type (polymorphic)
        assert a1.item_spec_type_polymorphic is None
        assert a2.item_spec_type_polymorphic is MySpec
        assert a3.item_spec_type_polymorphic is None
        assert a4.item_spec_type_polymorphic is MySpec

        # Item spec key type
        assert a1.item_spec_key_type is None
        assert a2.item_spec_key_type is str
        assert a3.item_spec_key_type is None
        assert a4.item_spec_key_type is None

        # Item spec key type (polymorphic)
        assert a1.item_spec_polymorphic_key_type is None
        assert a2.item_spec_polymorphic_key_type is str
        assert a3.item_spec_polymorphic_key_type is None
        assert a4.item_spec_polymorphic_key_type is str

    def test_decorators(self):
        class MyClass:
            attr: List[str] = Attr()

            @attr.preparer
            def _(self, attr):
                return list(attr)

            @attr.item_preparer
            def _(self, attr_item):
                return str(attr_item)

        assert MyClass.attr.prepare(None, {"a"}) == ["a"]
        assert MyClass.attr.prepare_item(None, 1) == "1"
