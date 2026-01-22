from __future__ import annotations

import copy
import dataclasses
import inspect
import re
import sys
import textwrap
import warnings
from types import ModuleType
from typing import Any, Callable, Dict, List

import pytest

from spec_classes import MISSING, Attr, FrozenInstanceError, spec_class, spec_property
from spec_classes.spec_class import SpecClassMetadata, _SpecClassMetadataPlaceholder


class TestFramework:
    def test_bootstrapping(self):
        @spec_class
        class MyClass:
            a: int

        @spec_class
        class MyClass2:
            a: int

        @spec_class(bootstrap=True)
        class MyClass3:
            a: int

        assert isinstance(
            MyClass.__dict__["__spec_class__"], _SpecClassMetadataPlaceholder
        )
        assert isinstance(
            MyClass.__dict__["__dataclass_fields__"], _SpecClassMetadataPlaceholder
        )
        assert MyClass(a=1).a == 1
        assert isinstance(MyClass.__dict__["__spec_class__"], SpecClassMetadata)
        assert isinstance(MyClass.__dict__["__dataclass_fields__"], dict)

        # Test auto-bootstrapping by __dataclass_fields__ (in addition to __spec_class__)
        assert isinstance(MyClass2.__dataclass_fields__, dict)

        assert isinstance(MyClass3.__dict__["__spec_class__"], SpecClassMetadata)
        assert isinstance(MyClass3.__dict__["__dataclass_fields__"], dict)
        assert MyClass3(a=1).a == 1

    def test_key(self, spec_cls):
        assert spec_cls.__spec_class__.key == "key"

    def test_annotations(self, spec_cls):
        assert set(spec_cls.__annotations__) == {
            "dict_values",
            "key",
            "keyed_spec_dict_items",
            "keyed_spec_list_items",
            "keyed_spec_set_items",
            "list_values",
            "set_values",
            "scalar",
            "spec",
            "spec_dict_items",
            "spec_list_items",
            "recursive",
        }

    def test_spec_inheritance(self):
        @spec_class(key="value")
        class Item:
            value: int

        @spec_class(bootstrap=True)
        class ItemSub(Item):
            value2: int = 1

        assert set(ItemSub.__spec_class__.annotations) == {"value", "value2"}
        assert ItemSub.__spec_class__.key == "value"

        @spec_class(key=None, bootstrap=True)
        class ItemSubSub(ItemSub):
            value3: int = 1

        assert set(ItemSubSub.__spec_class__.annotations) == {
            "value",
            "value2",
            "value3",
        }
        assert ItemSubSub.__spec_class__.key is None

    def test_spec_arguments(self):
        @spec_class(attrs={"value"}, attrs_typed={"items": List[str]}, bootstrap=True)
        class Item:
            pass

        assert hasattr(Item, "with_value")
        assert hasattr(Item, "transform_value")
        assert hasattr(Item, "with_items")
        assert hasattr(Item, "with_item")
        assert hasattr(Item, "without_item")
        assert hasattr(Item, "transform_item")

        @spec_class(key="key", attrs_typed={"key": str}, bootstrap=True)
        class Item:
            pass

        assert Item.__annotations__ == {"key": str}

        with pytest.raises(
            ValueError,
            match="`spec_cls` cannot be used to generate helper methods for private attributes",
        ):

            @spec_class(attrs={"_private"})
            class Item:
                pass

    def test_annotation_overrides(self):
        @spec_class(attrs_typed={"x": int}, bootstrap=True)
        class Item:
            x: str

        assert Item.__annotations__ == {"x": "str"}
        assert Item.__spec_class__.annotations == {"x": int}

        with pytest.raises(TypeError):
            Item().x = "invalid type"

    def test_spec_methods(self, spec_cls):
        assert hasattr(spec_cls, "__init__")
        assert hasattr(spec_cls, "__repr__")
        assert hasattr(spec_cls, "__eq__")
        assert hasattr(spec_cls, "__spec_class_init__")
        assert hasattr(spec_cls, "__spec_class_repr__")
        assert hasattr(spec_cls, "__spec_class_eq__")

        assert set(inspect.Signature.from_callable(spec_cls.__init__).parameters) == {
            "dict_values",
            "key",
            "keyed_spec_dict_items",
            "keyed_spec_list_items",
            "keyed_spec_set_items",
            "list_values",
            "recursive",
            "scalar",
            "self",
            "set_values",
            "spec",
            "spec_dict_items",
            "spec_list_items",
        }
        assert (
            inspect.Signature.from_callable(spec_cls.__init__).parameters["key"].default
            is MISSING
        )
        for attr, param in inspect.Signature.from_callable(
            spec_cls.__init__
        ).parameters.items():
            if attr not in {"self", "key"}:
                assert param.default is MISSING

        assert spec_cls(key="key").key == "key"
        assert (
            repr(
                spec_cls(
                    key="key",
                    list_values=[1, 2, 3],
                    dict_values={"a": 1, "b": 2},
                    recursive=spec_cls(key="nested"),
                    set_values={
                        "a"
                    },  # sets are unordered, so we use one item to guarantee order
                )
            )
            == textwrap.dedent(
                """
        Spec(
            key='key',
            scalar=MISSING,
            list_values=[
                1,
                2,
                3
            ],
            dict_values={
                'a': 1,
                'b': 2
            },
            set_values={
                'a'
            },
            spec=MISSING,
            spec_list_items=MISSING,
            spec_dict_items=MISSING,
            keyed_spec_list_items=MISSING,
            keyed_spec_dict_items=MISSING,
            keyed_spec_set_items=MISSING,
            recursive=Spec(key='nested', ...)
        )
        """
            ).strip()
        )

        assert (
            spec_cls(
                key="key",
                list_values=[1, 2, 3],
                dict_values={"a": 1, "b": 2},
                recursive=spec_cls(key="nested"),
                set_values={
                    "a"
                },  # sets are unordered, so we use one item to guarantee order
            ).__repr__(indent=False)
            == (
                "Spec(key='key', scalar=MISSING, list_values=[1, 2, 3], dict_values={'a': 1, 'b': 2}, set_values={'a'}, "
                "spec=MISSING, spec_list_items=MISSING, spec_dict_items=MISSING, keyed_spec_list_items=MISSING, keyed_spec_dict_items=MISSING, "
                "keyed_spec_set_items=MISSING, recursive=Spec(key='nested', ...))"
            )
        )

        with pytest.raises(
            ValueError,
            match=r"Some attributes were both included and excluded: {'key'}\.",
        ):
            spec_cls("key").__repr__(
                include_attrs=["key", "asd"], exclude_attrs=["key"]
            )

        # Check that type checking works during direct mutation of elements
        s = spec_cls(key="key")
        s.scalar = 10
        assert s.scalar == 10

        with pytest.raises(
            TypeError,
            match=r"Attempt to set `Spec\.scalar` with an invalid type \[got `'string'`; expecting `int`\].",
        ):
            s.scalar = "string"

        # Check that attribute deletion works
        del s.scalar
        assert "scalar" not in s.__dict__

        # Test empty containers
        assert (
            spec_cls(
                key="key",
                list_values=[],
                dict_values={},
                set_values=set(),  # sets are unordered, so we use one item to guarantee order
            ).__repr__(indent=True)
            == textwrap.dedent(
                """
            Spec(
                key='key',
                scalar=MISSING,
                list_values=[],
                dict_values={},
                set_values=set(),
                spec=MISSING,
                spec_list_items=MISSING,
                spec_dict_items=MISSING,
                keyed_spec_list_items=MISSING,
                keyed_spec_dict_items=MISSING,
                keyed_spec_set_items=MISSING,
                recursive=MISSING
            )
        """
            ).strip()
        )

        # Test recursive representations
        s = spec_cls()
        s.with_recursive(s, _inplace=True)
        assert (
            s.__repr__(indent=True)
            == textwrap.dedent(
                """
            Spec(
                key='key',
                scalar=MISSING,
                list_values=MISSING,
                dict_values=MISSING,
                set_values=MISSING,
                spec=MISSING,
                spec_list_items=MISSING,
                spec_dict_items=MISSING,
                keyed_spec_list_items=MISSING,
                keyed_spec_dict_items=MISSING,
                keyed_spec_set_items=MISSING,
                recursive=<self>
            )
        """
            ).strip()
        )

        assert spec_cls(key="key") != "key"
        assert spec_cls(key="key") == spec_cls(key="key")
        assert spec_cls(key="key") != spec_cls(key="notkey")

        # Test passing around of callable values with default implementations, and classes
        @spec_class(bootstrap=True)
        class Item:
            x: int = 1
            f: Callable
            g: type

            def f(self):
                pass

        assert hasattr(Item, "__init__")
        assert hasattr(Item, "__repr__")
        assert hasattr(Item, "__eq__")

        assert set(inspect.Signature.from_callable(Item.__init__).parameters) == {
            "self",
            "x",
            "f",
            "g",
        }
        assert (
            inspect.Signature.from_callable(Item.__init__).parameters["x"].default == 1
        )

        assert repr(Item()) == "Item(x=1, f=<bound method f of self>, g=MISSING)"

        def f(x):
            return x

        assert Item().with_f(f).f is f
        assert Item().with_g(Item).g is Item

        assert Item() == Item()
        assert Item().with_f(f) != Item()

        # Test that key default properly unset when it is a method or property
        @spec_class(key="key", bootstrap=True)
        class Item:
            @property
            def key(self):
                return "key"

        assert set(inspect.Signature.from_callable(Item.__init__).parameters) == {
            "self",
            "key",
        }
        assert (
            inspect.Signature.from_callable(Item.__init__).parameters["key"].default
            is MISSING
        )

        # Test that key is succesfully handled in super() constructors
        @spec_class(key="key")
        class KeyedItem:
            key: str

            def __init__(self, key):
                self.key = key
                self.b = 10

        @spec_class
        class SubKeyedItem(KeyedItem):
            key: str = "Hi"

        with pytest.raises(
            TypeError,
            match=re.escape("__init__() missing 1 required positional argument: 'key'"),
        ):
            KeyedItem()
        assert SubKeyedItem().key == "Hi"
        assert SubKeyedItem().b == 10

    def test_attr_deletion(self):
        @spec_class
        class MyClass:
            mylist: list = []

        m = MyClass()
        del m.mylist
        assert m.mylist is not MyClass.mylist
        assert m.mylist == []

    def test_attr_preparation(self):
        @spec_class
        class MyClass:
            prepared_str: str = "a"
            prepared_items: List[str] = []

            def _prepare_prepared_str(self, prepared_str):
                return "c"

            def _prepare_prepared_items(self, prepared_items):
                return ["a", "b", "c"]

            def _prepare_prepared_item(self, prepared_item):
                return "c"

        assert MyClass().prepared_items == ["c", "c", "c"]
        assert MyClass(prepared_items="a").prepared_items == ["c", "c", "c"]
        assert MyClass().with_prepared_item("a").prepared_items == ["c", "c", "c", "c"]

    def test_deepcopy_with_instance_method_values(self):
        @spec_class
        class MyClass:
            value: Callable

            def __init__(self, value=None):
                self.value = value or self.method

            def method(self):
                pass

        copy.deepcopy(
            MyClass()
        )  # If the instance method value causes recursion, we'd catch it here.

    def test_deepcopy_with_module_values(self):
        @spec_class
        class MyClass:
            module: ModuleType = sys

            module_items: List[ModuleType] = [sys]

        assert MyClass().module is sys
        assert MyClass().module_items == [sys]
        assert MyClass().with_module_item(sys).module_items == [sys, sys]

        copy.deepcopy(
            MyClass()
        )  # If the instance method value causes recursion, we'd catch it here.

    def test_do_not_copy(self):
        @spec_class(do_not_copy=["shallow_list"], bootstrap=True)
        class Item:
            value: str
            deep_list: list
            shallow_list: object

        assert Item.__spec_class__.attrs["value"].do_not_copy is False
        assert Item.__spec_class__.attrs["deep_list"].do_not_copy is False
        assert Item.__spec_class__.attrs["shallow_list"].do_not_copy is True

        list_obj = []
        assert (
            Item()
            .with_deep_list(list_obj)
            .with_shallow_list(list_obj)
            .with_value("x")
            .deep_list
            is not list_obj
        )
        assert (
            Item()
            .with_deep_list(list_obj)
            .with_shallow_list(list_obj)
            .with_value("x")
            .shallow_list
            is list_obj
        )

        @spec_class(do_not_copy=True, bootstrap=True)
        class ShallowItem:
            value: str
            deep_list: list
            shallow_list: object

        assert ShallowItem.__spec_class__.attrs["value"].do_not_copy is True
        assert ShallowItem.__spec_class__.attrs["deep_list"].do_not_copy is True
        assert ShallowItem.__spec_class__.attrs["shallow_list"].do_not_copy is True

    def test_overriding_methods(self):
        class Item:
            key: str

            def __init__(self, key=None):
                pass

        assert spec_class(Item).__init__ is Item.__init__

    def test_spec_properties(self):
        @spec_class(bootstrap=True)
        class Item:
            x: int

            @property
            def x(self):
                return 1

        assert set(inspect.Signature.from_callable(Item.__init__).parameters) == {
            "self",
            "x",
        }
        assert isinstance(Item(), Item)

        @spec_class(bootstrap=True)
        class Item2:
            x: int

            @property
            def x(self):
                return getattr(self, "_x", 1)

            @x.setter
            def x(self, x):
                self._x = x

        assert set(inspect.Signature.from_callable(Item2.__init__).parameters) == {
            "self",
            "x",
        }
        assert (
            inspect.Signature.from_callable(Item2.__init__).parameters["x"].default
            is MISSING
        )
        assert Item2().x == 1
        assert Item2(x=10).x == 10

        @spec_class(attrs={"x"}, bootstrap=True)
        class Item3:
            x: int

            @property
            def x(self):
                return 1

        assert set(inspect.Signature.from_callable(Item3.__init__).parameters) == {
            "self",
            "x",
        }
        assert (
            inspect.Signature.from_callable(Item3.__init__).parameters["x"].default
            is MISSING
        )

        with pytest.raises(
            AttributeError,
            match="Cannot set `Item3.x` to `1`. Is this a property without a setter?",
        ):
            assert Item3(x=1)

    def test_frozen(self):
        @spec_class(frozen=True, bootstrap=True)
        class Item:
            x: int = 1

        assert Item.__spec_class__.owner is Item
        assert Item.__spec_class__.frozen is True
        assert Item().x == 1
        assert Item(x=10).with_x(20).x == 20

        with pytest.raises(FrozenInstanceError):
            Item(x=10).x = 20
        with pytest.raises(FrozenInstanceError):
            Item(x=10).with_x(20, _inplace=True)
        with pytest.raises(FrozenInstanceError):
            del Item(x=10).x

    def test_kwarg_overflow(self):
        @spec_class(init_overflow_attr="options")
        class MyClass:
            options: Dict[str, Any]

        assert MyClass(a=1, b=2).options == {"a": 1, "b": 2}

        @spec_class(init_overflow_attr="options")
        class MyClass:
            pass

        assert MyClass(a=1, b=2).options == {"a": 1, "b": 2}

        @spec_class(init_overflow_attr="options")
        class MyClass:
            a: int

        assert MyClass(a=1, b=2).options == {"b": 2}

    def test_subclassing(self):
        @spec_class(key="key")
        class A:
            key: str
            field: int
            overridden: float = 1.0

        @spec_class
        class B(A):
            value: str

            @property
            def overridden(self):
                return 2.0

        class C(A):
            overridden = 2.0

        assert B("foo").key == "foo"
        assert B(key="foo").key == "foo"
        assert B("foo", field=10).field == 10
        assert B("foo", value="bar").value == "bar"
        assert B("foo").overridden == 2.0

        assert C("foo").overridden == 2.0

    def test_subclassing_with_new_override(self):
        @spec_class
        class A:
            pass

        @spec_class
        class B(A):
            def __new__(cls, *args, **kwargs):
                return super().__new__(cls)

        assert isinstance(B(), B)

    def test_respect_super_init(self):
        @spec_class
        class A:
            a: int
            a_overridden: int
            a_defaulted: int

            def __init__(self, a=100, a_overridden=100, a_defaulted=100):
                self.a = a + 1
                self.a_overridden = a_overridden + 1
                self.a_defaulted = a_defaulted + 1

        @spec_class
        class B:
            b: int

            def __init__(self, b=10):
                self.b = 100

        @spec_class
        class C(A, B):
            a_overridden: int = 10
            a_defaulted = (
                10  # default changed, but not owner. Passed to super constructor.
            )
            c: int

        class D(C):
            a_defaulted = 1000

        assert A().a_overridden == 101
        assert list(C().__spec_class__.annotations) == [
            "b",
            "a",
            "a_overridden",
            "a_defaulted",
            "c",
        ]
        assert C().a == 101
        assert C().a_overridden == 10
        assert C().a_defaulted == 11
        assert C().b == 100
        assert not hasattr(C(), "c")
        assert C(a=1).a == 2
        assert C(b=1).b == 100
        assert D().a_defaulted == 1001

    def test_class_attribute_masking(self):
        @spec_class
        class Item:
            a: List[int] = [1, 2, 3]

        assert Item().a == [1, 2, 3]

        item = Item()
        del item.__dict__["a"]
        assert item.a is Item.a

        assert item.with_a().a == []
        assert item.with_a().a is not Item.a

        del item.a
        assert item.a is not Item.a

    def test_copy_behavior(self):
        @spec_class
        class MySpec:
            values: List[str]
            pending_write: bool = True
            copied: bool = False

            @property
            def values(self):
                if self.pending_write:
                    raise RuntimeError("Should not access element until set.")
                return getattr(self, "_values", [])

            @values.setter
            def values(self, values):
                self.pending_write = False
                self._values = values

            def __deepcopy__(self, memo):
                if self.copied:
                    raise RuntimeError("Should not copy more than once during setting.")
                return MySpec(values=self.values)

        m = MySpec(pending_write=False)
        assert m.with_value("a").values == ["a"]
        assert m.with_values(["b"]).values == ["b"]
        assert m.with_value("a", _inplace=True).with_values(["b"], _inplace=True) is m
        assert m.with_value("a", _inplace=True).with_values(
            ["b"], _inplace=True
        ).values == ["b"]

        @spec_class
        class PostCopy:
            def __post_copy__(self):
                raise RuntimeError("Post copy!")

        with pytest.raises(RuntimeError, match="Post copy!"):
            copy.deepcopy(PostCopy())

    def test_respect_new(self):
        @spec_class
        class MySpec:
            a: int

            def __new__(self, a=1):
                assert a == 2
                return "hi"

        assert MySpec(a=2) == "hi"

    def test_annotation_types(self):
        @spec_class(bootstrap=True)
        class MySpec:
            ANNOTATION_TYPES = {"my_str": str}

            a: my_str  # noqa: F821; type defined by ANNOTATION_TYPES

        assert MySpec.__spec_class__.annotations["a"] is str

        @spec_class(bootstrap=True)
        class MySpec2:
            @classmethod
            def ANNOTATION_TYPES(cls):
                return {
                    "my_str": str,
                }

            a: my_str  # noqa: F821; type defined by ANNOTATION_TYPES

        assert MySpec2.__spec_class__.annotations["a"] is str

    def test_inherited_defaults(self):
        @spec_class
        class Spec:
            attr: str = "Hello"

        @spec_class
        class SubSpec(Spec):
            @property
            def attr(self):
                return "World"

        assert SubSpec().attr == "World"

    def test_explicit_attr_specs(self):
        @spec_class(bootstrap=True)
        class Spec:
            attr: str = Attr(default="Hello World")
            hidden_attr: str = Attr(
                default="Hidden", init=False, repr=False, compare=False
            )

        # Init and masked attrs
        assert set(inspect.Signature.from_callable(Spec.__init__).parameters) == {
            "self",
            "attr",
        }
        assert Spec(attr="Replaced").attr == "Replaced"
        with pytest.raises(
            TypeError,
            match=re.escape(
                "__init__() got unexpected keyword arguments: {'hidden_attr'}."
            ),
        ):
            Spec(hidden_attr="Not here")
        assert Spec().hidden_attr == "Hidden"

        # Compare
        assert Spec(attr="Hi").with_hidden_attr("Changed") == Spec(
            attr="Hi"
        ).with_hidden_attr("Different")

        # Representation
        assert str(Spec(attr="Replaced")) == "Spec(attr='Replaced')"

    def test_invalidation(self):
        @spec_class
        class Spec:
            always_invalidated_property: str
            attr: str = Attr(default="Hello World")
            unmanaged_attr = "Hi"
            invalidated_attr: str = Attr(
                default="Invalidated",
                repr=False,
                invalidated_by=["attr", "unmanaged_attr"],
            )

            @spec_property(cache=True, invalidated_by=["unmanaged_attr"])
            def invalidated_property(self):
                return self.unmanaged_attr

            @spec_property(cache=True, invalidated_by="*")
            def always_invalidated_property(self):
                return "Invalidated"

        assert Spec.__spec_class__.invalidation_map == {
            "attr": {"invalidated_attr"},
            "unmanaged_attr": {"invalidated_attr", "invalidated_property"},
            "*": {"always_invalidated_property"},
        }

        s = Spec(
            invalidated_attr="Pre-invalidation",
            always_invalidated_property="Pre-invalidation",
        )
        assert s.invalidated_attr == "Pre-invalidation"
        assert s.always_invalidated_property == "Pre-invalidation"
        assert s.with_attr("Hi").invalidated_attr == "Invalidated"
        assert s.with_attr("Hi").always_invalidated_property == "Invalidated"

        @spec_class
        class SubSpec(Spec):
            sub_invalidated_attr: str = Attr(
                default="Also Invalidated",
                repr=False,
                invalidated_by=["invalidated_attr"],
            )

        assert SubSpec.__spec_class__.invalidation_map == {
            "attr": {"invalidated_attr"},
            "invalidated_attr": {"sub_invalidated_attr"},
            "unmanaged_attr": {"invalidated_attr", "invalidated_property"},
            "*": {"always_invalidated_property"},
        }

        s = SubSpec(
            invalidated_attr="Pre-invalidation",
            sub_invalidated_attr="Also Pre-invalidation",
        )
        assert s.invalidated_attr == "Pre-invalidation"
        assert s.sub_invalidated_attr == "Also Pre-invalidation"
        assert s.invalidated_property == s.unmanaged_attr
        s.unmanaged_attr = "Changed"
        assert s.invalidated_attr == "Invalidated"
        assert s.sub_invalidated_attr == "Also Invalidated"
        assert s.invalidated_property == s.unmanaged_attr

    def test_overlapping_attributes(self):
        @spec_class
        class Spec:
            items: List[int]

        assert Spec.__spec_class__.attrs["items"].item_name == "item"

        @spec_class
        class Spec:
            item: int
            items: List[int]

        assert Spec.__spec_class__.attrs["items"].item_name == "items_item"

        with pytest.raises(
            RuntimeError,
            match=re.escape(
                "`spec_class.items`'s singular name 'item' overlaps with an existing attribute, and so does the fallback of 'items_item'. Please rename the attribute(s) to avoid this collision."
            ),
        ):

            @spec_class(bootstrap=True)
            class Spec:
                item: int
                items_item: int
                items: List[int]

    def test_post_init(self):
        @spec_class
        class Spec:
            a: int = 10

            def __post_init__(self):
                self.b = 2 * self.a

        assert Spec().b == 20
        assert Spec(a=50).b == 100

    def test_dataclasses_compatibility(self):
        @spec_class
        class MySpec:
            a: int = dataclasses.field(default_factory=lambda: 0)

        assert MySpec().a == 0
        assert dataclasses.replace(MySpec(), a=10).a == 10

    def test_staticmethod_attributes(self):
        """
        Static methods are not directly pickleable, and so need to be accessed
        via `__get__`. This makes sure this is true when overridden in
        subclasses.
        """

        @spec_class
        class Spec:
            a: Callable = staticmethod(lambda x: x)

        class SubSpec(Spec):
            a = staticmethod(lambda x: x)

        SubSpec()  # Would fail if attempting to deepcopy `staticmethod`.

    def test_nested_type_resolution(self):
        @spec_class
        class A:
            class B:
                pass

            a: B

        assert A.__spec_class__.attrs["a"].type is A.B

    def test_multiple_inheritance_conflicting_keys(self):
        """Test warning when multiple parents have different key attributes."""

        @spec_class(key="key1", bootstrap=True)
        class Parent1:
            key1: str

        @spec_class(key="key2", bootstrap=True)
        class Parent2:
            key2: str

        # Should warn about conflicting keys
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            @spec_class(bootstrap=True)
            class Child(Parent1, Parent2):
                pass

            # Check that a warning was issued
            assert len(w) == 1
            assert "conflicting `key` attributes" in str(w[0].message)
            assert "key1" in str(w[0].message)

        # The last key collected (left-most parent) should be used
        assert Child.__spec_class__.key == "key1"

    def test_multiple_inheritance_conflicting_overflow_attrs(self):
        """Test warning when multiple parents have different init_overflow_attr."""

        @spec_class(init_overflow_attr="overflow1", bootstrap=True)
        class Parent1:
            attr1: int = 1

        @spec_class(init_overflow_attr="overflow2", bootstrap=True)
        class Parent2:
            attr2: int = 2

        # Should warn about conflicting overflow attributes
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            @spec_class(bootstrap=True)
            class Child(Parent1, Parent2):
                pass

            # Check that a warning was issued
            assert len(w) == 1
            assert "conflicting `init_overflow_attr`" in str(w[0].message)
            assert "overflow1" in str(w[0].message)

        # The last overflow attr collected (left-most parent) should be used
        assert Child.__spec_class__.init_overflow_attr == "overflow1"

    def test_multiple_inheritance_attr_override(self):
        """Test that child can override parent attributes."""

        @spec_class(bootstrap=True)
        class Parent1:
            attr1: int = 1
            common: str = "parent1"

        @spec_class(bootstrap=True)
        class Parent2:
            attr2: int = 2
            common: str = "parent2"

        @spec_class(bootstrap=True)
        class Child(Parent1, Parent2):
            common: str = "child"
            attr3: int = 3

        # Child's definition should override parent's
        child = Child()
        assert child.common == "child"

        # Check that the owner is set correctly for overridden attributes
        assert Child.__spec_class__.attrs["common"].owner is Child

    def test_multiple_inheritance_mro_order(self):
        """Test that attributes are inherited in correct MRO order."""

        @spec_class(bootstrap=True)
        class A:
            a: int = 1

        @spec_class(bootstrap=True)
        class B(A):
            b: int = 2

        @spec_class(bootstrap=True)
        class C(A):
            c: int = 3
            a: int = 10  # Override A's attribute

        @spec_class(bootstrap=True)
        class D(B, C):
            d: int = 4

        # D should have all attributes
        assert set(D.__spec_class__.attrs.keys()) >= {"a", "b", "c", "d"}

        # C's override of 'a' should be used (C comes after B in MRO)
        d = D()
        assert d.a == 10
        assert d.b == 2
        assert d.c == 3
        assert d.d == 4

    def test_multiple_inheritance_frozen_reset(self):
        """Test that frozen attribute is always reset in child classes."""

        @spec_class(frozen=True, bootstrap=True)
        class Parent:
            attr1: int = 1

        # Child should not inherit frozen=True
        @spec_class(bootstrap=True)
        class Child(Parent):
            attr2: int = 2

        # Child should not be frozen by default
        assert Child.__spec_class__.frozen is False

        # But can be explicitly set
        @spec_class(frozen=True, bootstrap=True)
        class FrozenChild(Parent):
            attr3: int = 3

        assert FrozenChild.__spec_class__.frozen is True

    def test_multiple_inheritance_do_not_copy_reset(self):
        """Test that do_not_copy attribute is always reset in child classes."""

        @spec_class(do_not_copy=True, bootstrap=True)
        class Parent:
            attr1: int = 1

        # Child should not inherit do_not_copy=True
        @spec_class(bootstrap=True)
        class Child(Parent):
            attr2: int = 2

        # Child's do_not_copy should be reset to False
        assert Child.__spec_class__.do_not_copy is False

        # But can be explicitly set
        @spec_class(do_not_copy=True, bootstrap=True)
        class NoCopyChild(Parent):
            attr3: int = 3

        assert NoCopyChild.__spec_class__.do_not_copy is True

    def test_multiple_inheritance_diamond_pattern(self):
        """Test diamond inheritance pattern to ensure proper MRO handling."""

        @spec_class(bootstrap=True)
        class A:
            a: int = 1

        @spec_class(bootstrap=True)
        class B(A):
            b: int = 2

        @spec_class(bootstrap=True)
        class C(A):
            c: int = 3

        @spec_class(bootstrap=True)
        class D(B, C):
            d: int = 4

        # D should have all attributes from the diamond
        assert set(D.__spec_class__.attrs.keys()) >= {"a", "b", "c", "d"}

        # Verify instance creation works correctly
        instance = D()
        assert instance.a == 1
        assert instance.b == 2
        assert instance.c == 3
        assert instance.d == 4

    def test_inheritance_from_non_spec_class(self):
        """Test that inheriting from a non-spec-class works correctly."""

        class RegularParent:
            regular_attr: int = 10

            def regular_method(self):
                return "regular"

        @spec_class(bootstrap=True)
        class SpecChild(RegularParent):
            spec_attr: int = 20

        # Should only manage spec_attr, not regular_attr
        assert "spec_attr" in SpecChild.__spec_class__.attrs
        assert "regular_attr" not in SpecChild.__spec_class__.attrs

        # But regular_attr should still be accessible
        instance = SpecChild()
        assert instance.regular_attr == 10
        assert instance.spec_attr == 20
        assert instance.regular_method() == "regular"

        # And spec-class methods should work
        instance2 = instance.with_spec_attr(25)
        assert instance2.spec_attr == 25
