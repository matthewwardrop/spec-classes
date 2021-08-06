from __future__ import annotations

import copy
import inspect
import textwrap
from typing import Any, Callable, Dict, List, Set

import pytest

from spec_classes import MISSING, spec_class, AttrProxy, FrozenInstanceError


@spec_class
class UnkeyedSpec:
    nested_scalar: int = 1
    nested_scalar2: str = "original value"


@spec_class(key="key")
class KeyedSpec:
    key: str = "key"
    nested_scalar: int = 1
    nested_scalar2: str = "original value"


@spec_class(key="key", bootstrap=True)
class Spec:
    key: str = "key"
    scalar: int
    list_values: List[int]
    dict_values: Dict[str, int]
    set_values: Set[str]
    spec: UnkeyedSpec
    spec_list_items: List[UnkeyedSpec]
    spec_dict_items: Dict[str, UnkeyedSpec]
    keyed_spec_list_items: List[KeyedSpec]
    keyed_spec_dict_items: Dict[str, KeyedSpec]
    recursive: Spec


@pytest.fixture
def spec_cls():
    assert Spec.__spec_class_bootstrapped__ is True
    return Spec


class TestFramework:
    def test_bootstrapping(self):
        @spec_class
        class MyClass:
            a: int

        @spec_class(bootstrap=True)
        class MyClass2:
            a: int

        assert MyClass.__spec_class_bootstrapped__ is False
        assert MyClass(a=1).a == 1
        assert MyClass.__spec_class_bootstrapped__ is True

        assert MyClass2.__spec_class_bootstrapped__ is True
        assert MyClass2(a=1).a == 1

    def test_key(self, spec_cls):
        assert spec_cls.__spec_class_key__ == "key"

    def test_annotations(self, spec_cls):
        assert set(spec_cls.__annotations__) == {
            "dict_values",
            "key",
            "keyed_spec_dict_items",
            "keyed_spec_list_items",
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

        @spec_class
        class ItemSub(Item):
            value2: int = 1

        ItemSub.__spec_class_bootstrap__()
        assert set(ItemSub.__spec_class_annotations__) == {"value", "value2"}
        assert ItemSub.__spec_class_key__ == "value"

        @spec_class(key=None)
        class ItemSubSub(ItemSub):
            value3: int = 1

        ItemSubSub.__spec_class_bootstrap__()
        assert set(ItemSubSub.__spec_class_annotations__) == {
            "value",
            "value2",
            "value3",
        }
        assert ItemSubSub.__spec_class_key__ is None

    def test_spec_arguments(self):
        @spec_class(attrs={"value"}, attrs_typed={"items": List[str]})
        class Item:
            pass

        Item.__spec_class_bootstrap__()

        assert hasattr(Item, "with_value")
        assert hasattr(Item, "transform_value")
        assert hasattr(Item, "with_items")
        assert hasattr(Item, "with_item")
        assert hasattr(Item, "without_item")
        assert hasattr(Item, "transform_item")

        @spec_class(key="key", attrs_typed={"key": str})
        class Item:
            pass

        Item.__spec_class_bootstrap__()

        assert Item.__annotations__ == {"key": str}

        with pytest.raises(
            ValueError,
            match="`spec_cls` cannot be used to generate helper methods for private attributes",
        ):

            @spec_class(attrs={"_private"})
            class Item:
                pass

    def test_annotation_overrides(self):
        @spec_class(attrs_typed={"x": int})
        class Item:
            x: str

        Item.__spec_class_bootstrap__()
        assert Item.__annotations__ == {"x": "str"}
        assert Item.__spec_class_annotations__ == {"x": int}

        with pytest.raises(TypeError):
            Item().x = "invalid type"

    def test_spec_methods(self):

        assert hasattr(Spec, "__init__")
        assert hasattr(Spec, "__repr__")
        assert hasattr(Spec, "__eq__")
        assert hasattr(Spec, "__spec_class_init__")
        assert hasattr(Spec, "__spec_class_repr__")
        assert hasattr(Spec, "__spec_class_eq__")

        assert set(inspect.Signature.from_callable(Spec.__init__).parameters) == {
            "dict_values",
            "key",
            "keyed_spec_dict_items",
            "keyed_spec_list_items",
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
            inspect.Signature.from_callable(Spec.__init__).parameters["key"].default
            is MISSING
        )
        for attr, param in inspect.Signature.from_callable(
            Spec.__init__
        ).parameters.items():
            if attr not in {"self", "key"}:
                assert param.default is MISSING

        assert Spec(key="key").key == "key"
        assert (
            repr(
                Spec(
                    key="key",
                    list_values=[1, 2, 3],
                    dict_values={"a": 1, "b": 2},
                    recursive=Spec(key="nested"),
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
            recursive=Spec(
                key='nested',
                scalar=MISSING,
                list_values=MISSING,
                dict_values=MISSING,
                set_values=MISSING,
                spec=MISSING,
                spec_list_items=MISSING,
                spec_dict_items=MISSING,
                keyed_spec_list_items=MISSING,
                keyed_spec_dict_items=MISSING,
                recursive=MISSING
            )
        )
        """
            ).strip()
        )

        assert Spec(
            key="key",
            list_values=[1, 2, 3],
            dict_values={"a": 1, "b": 2},
            recursive=Spec(key="nested"),
            set_values={
                "a"
            },  # sets are unordered, so we use one item to guarantee order
        ).__repr__(indent=False) == (
            "Spec(key='key', scalar=MISSING, list_values=[1, 2, 3], dict_values={'a': 1, 'b': 2}, set_values={'a'}, "
            "spec=MISSING, spec_list_items=MISSING, spec_dict_items=MISSING, keyed_spec_list_items=MISSING, keyed_spec_dict_items=MISSING, "
            "recursive=Spec(key='nested', scalar=MISSING, list_values=MISSING, dict_values=MISSING, set_values=MISSING, spec=MISSING, "
            "spec_list_items=MISSING, spec_dict_items=MISSING, keyed_spec_list_items=MISSING, keyed_spec_dict_items=MISSING, recursive=MISSING))"
        )

        with pytest.raises(
            ValueError,
            match=r"Some attributes were both included and excluded: {'key'}\.",
        ):
            Spec("key").__repr__(include_attrs=["key", "asd"], exclude_attrs=["key"])

        # Check that type checking works during direct mutation of elements
        s = Spec(key="key")
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
            Spec(
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
                recursive=MISSING
            )
        """
            ).strip()
        )

        assert Spec(key="key") != "key"
        assert Spec(key="key") == Spec(key="key")
        assert Spec(key="key") != Spec(key="notkey")

        # Test passing around of callable values with default implementations, and classes
        @spec_class
        class Item:
            x: int = 1
            f: Callable
            g: type

            def f(self):
                pass

        Item.__spec_class_bootstrap__()

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
        @spec_class(key="key")
        class Item:
            @property
            def key(self):
                return "key"

        Item.__spec_class_bootstrap__()

        assert set(inspect.Signature.from_callable(Item.__init__).parameters) == {
            "self",
            "key",
        }
        assert (
            inspect.Signature.from_callable(Item.__init__).parameters["key"].default
            is MISSING
        )

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

            def _prepare_prepared_item(self, prepared_item):
                return "c"

        assert MyClass().prepared_str == "c"
        assert MyClass(prepared_str="a").prepared_str == "c"
        assert MyClass(prepared_items=[1, 2, 3]).prepared_items == ["c", "c", "c"]

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

    def test_shallowcopy(self):
        @spec_class(shallowcopy=["shallow_list"])
        class Item:
            value: str
            deep_list: list
            shallow_list: object

        Item.__spec_class_bootstrap__()

        assert Item.__spec_class_shallowcopy__ == {"shallow_list"}

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

        @spec_class(shallowcopy=True)
        class ShallowItem:
            value: str
            deep_list: list
            shallow_list: object

        ShallowItem.__spec_class_bootstrap__()

        assert ShallowItem.__spec_class_shallowcopy__ == {
            "value",
            "deep_list",
            "shallow_list",
        }

    def test_overriding_methods(self):
        class Item:
            key: str

            def __init__(self, key=None):
                pass

        assert spec_class(Item).__init__ is Item.__init__

    def test_spec_properties(self):
        @spec_class
        class Item:
            x: int

            @property
            def x(self):
                return 1

        Item.__spec_class_bootstrap__()

        assert set(inspect.Signature.from_callable(Item.__init__).parameters) == {
            "self",
            "x",
        }
        assert isinstance(Item(), Item)

        @spec_class
        class Item2:
            x: int

            @property
            def x(self):
                return getattr(self, "_x", 1)

            @x.setter
            def x(self, x):
                self._x = x

        Item2.__spec_class_bootstrap__()

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

        @spec_class(attrs={"x"})
        class Item3:
            x: int

            @property
            def x(self):
                return 1

        Item3.__spec_class_bootstrap__()

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

    def test_spec_validation(self):

        with pytest.raises(
            ValueError, match="is missing required arguments to populate attributes"
        ):

            @spec_class(init=False)
            class Item:
                x: int = 1

            Item.__spec_class_bootstrap__()

    def test_singularisation(self):
        assert spec_class._get_singular_form("values") == "value"
        assert spec_class._get_singular_form("classes") == "class"
        assert spec_class._get_singular_form("collection") == "collection_item"

    def test_frozen(self):
        @spec_class(frozen=True)
        class Item:
            x: int = 1

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

    def test_get_attr_default(self):
        @spec_class
        class MyClass:
            def __spec_class_get_attr_default__(self, attr):
                return 1

            a: int
            b: int

        assert MyClass().a == 1
        assert MyClass().b == 1

        @spec_class
        class MySubClass(MyClass):
            c: str

        with pytest.raises(
            TypeError, match=r"Attempt to set `MySubClass\.c` with an invalid type"
        ):
            MySubClass()

    def test_subclassing(self):
        @spec_class
        class A:
            a: int
            a_overridden: int
            a_defaulted: int

            def __init__(self, a=MISSING, a_overridden=MISSING, a_defaulted=MISSING):
                self.a = 100
                self.a_overridden = 100
                self.a_defaulted = 100

        @spec_class
        class B:
            b: int

            def __init__(self, b=10):
                self.b = 100

        @spec_class
        class C(A, B):
            a_overridden: int = 10
            a_defaulted = 10
            c: int

        assert A().a_overridden == 100
        assert list(C().__spec_class_annotations__) == [
            "b",
            "a",
            "a_overridden",
            "a_defaulted",
            "c",
        ]
        assert C().a == 100
        assert C().a_overridden == 10
        assert C().a_defaulted == 100
        assert C().b == 100
        assert not hasattr(C(), "c")
        assert C(a=1).a == 100
        assert C(b=1).b == 100

    def test_special_types(self):
        @spec_class
        class Item:
            x: int
            y: int = AttrProxy("x")
            z: int = AttrProxy("x", transform=lambda x: x ** 2)
            w: int = AttrProxy("x", fallback=2)
            v: int = AttrProxy("x", passthrough=True, fallback=2)
            u: int = AttrProxy("u")

        assert Item(x=2).y == 2
        assert Item(x=2).z == 4
        assert Item().w == 2
        assert Item(x=4).w == 4
        assert Item().v == 2
        assert Item(x=4).v == 4

        item = Item()
        # Test passthrough mutation
        item.v = 1
        assert item.v == 1
        assert item.x == 1
        # Test local override
        item.w = 10
        assert item.w == 10
        assert item.x == 1

        assert Item(x=1, z=10).z == 10

        with pytest.raises(
            AttributeError, match=r"`Item\.x` has not yet been assigned a value\."
        ):
            Item(x=MISSING).x

        with pytest.raises(
            ValueError,
            match=r"AttrProxy for `Item\.u` appears to be self-referential\. Please change the `attr` argument to point to a different attribute\.",
        ):
            Item().u

        assert Item(x=1, y=10).x == 1
        assert Item(x=1, y=10).y == 10

        i = Item(x=2, y=10)
        del i.y
        assert i.y == 2

        with pytest.raises(
            AttributeError, match=r"`Item\.x` has not yet been assigned a value\."
        ):
            Item().y

    def test_class_attribute_masking(self):
        @spec_class
        class Item:
            a: List[int] = [1, 2, 3]

        assert Item().a == [1, 2, 3]

        item = Item()
        del item.__dict__["a"]
        item.a is Item.a

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

    def test_respect_new(self):
        @spec_class
        class MySpec:
            a: int

            def __new__(self, a=1):
                assert a == 2
                return "hi"

        assert MySpec(a=2) == "hi"

    def test_annotation_types(self):
        @spec_class
        class MySpec:

            ANNOTATION_TYPES = {"my_str": str}

            a: my_str  # noqa: F821; type defined by ANNOTATION_TYPES

        MySpec.__spec_class_bootstrap__()
        assert MySpec.__spec_class_annotations__["a"] is str

        @spec_class
        class MySpec2:
            @classmethod
            def ANNOTATION_TYPES(cls):
                return {
                    "my_str": str,
                }

            a: my_str  # noqa: F821; type defined by ANNOTATION_TYPES

        MySpec2.__spec_class_bootstrap__()
        assert MySpec2.__spec_class_annotations__["a"] is str


class TestScalarAttribute:
    def test_with(self, spec_cls):
        spec = spec_cls(scalar=3)
        assert set(inspect.Signature.from_callable(spec.with_scalar).parameters) == {
            "_new_value",
            "_inplace",
        }
        assert spec.with_scalar(4) is not spec
        assert spec.with_scalar(4).scalar == 4

        assert spec.with_scalar(4, _inplace=True) is spec
        assert spec.scalar == 4

    def test_transform(self, spec_cls):
        spec = spec_cls(scalar=3)
        assert set(
            inspect.Signature.from_callable(spec.transform_scalar).parameters
        ) == {"_transform", "_inplace"}
        assert spec.transform_scalar(lambda x: x * 2) is not spec
        assert spec.transform_scalar(lambda x: x * 2).scalar == 6

        assert spec.transform_scalar(lambda x: x * 2, _inplace=True) is spec
        assert spec.scalar == 6

    def test_reset(self, spec_cls):
        spec = spec_cls(scalar=3)

        with pytest.raises(
            AttributeError, match=r"`Spec\.scalar` has not yet been assigned a value\."
        ):
            spec.reset_scalar().scalar


class TestSpecAttribute:
    def test_get(self, spec_cls):
        spec = spec_cls()

        assert "scalar" not in spec.__dict__

        with pytest.raises(
            AttributeError, match=r"`Spec\.scalar` has not yet been assigned a value\."
        ):
            spec.scalar

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_spec).parameters) == {
            "_new_value",
            "_inplace",
            "nested_scalar",
            "nested_scalar2",
        }

        # Constructors
        assert "spec" not in spec.__dict__
        assert isinstance(spec.with_spec().spec, UnkeyedSpec)
        assert isinstance(spec.transform_spec(lambda x: x).spec, UnkeyedSpec)
        with pytest.raises(
            TypeError, match=r"Attempt to set `Spec\.spec` with an invalid type"
        ):
            spec.with_spec(None)

        # Assignments
        nested_spec = UnkeyedSpec()
        assert spec.with_spec(nested_spec).spec is nested_spec

        # Nested assignments
        assert spec.with_spec(nested_scalar=2) is not spec
        assert spec.with_spec(nested_scalar=2).spec.nested_scalar == 2
        assert (
            spec.with_spec(nested_scalar2="overridden").spec.nested_scalar2
            == "overridden"
        )
        assert (
            spec.with_spec(nested_scalar2="overridden").with_spec().spec.nested_scalar2
            == "original value"
        )

        assert spec.with_spec(nested_scalar=2, _inplace=True) is spec
        assert spec.spec.nested_scalar == 2

    def test_transform(self, spec_cls):
        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.transform_spec).parameters) == {
            "_transform",
            "_inplace",
            "nested_scalar",
            "nested_scalar2",
        }

        # Direct mutation
        assert spec.transform_spec(lambda x: x.with_nested_scalar(3)) is not spec
        assert (
            spec.transform_spec(lambda x: x.with_nested_scalar(3)).spec.nested_scalar
            == 3
        )

        # Nested mutations
        assert spec.transform_spec(nested_scalar=lambda x: 3) is not spec
        assert spec.transform_spec(nested_scalar=lambda x: 3).spec.nested_scalar == 3

        # Inplace operation
        assert spec.transform_spec(nested_scalar=lambda x: 3, _inplace=True) is spec
        assert spec.transform_spec(nested_scalar=lambda x: 3).spec.nested_scalar == 3

    def test_reset(self, spec_cls):
        spec = spec_cls()
        assert not hasattr(spec.with_spec().reset_spec(), "spec")

    def test_illegal_nested_update(self, spec_cls):
        base = spec_cls()
        with pytest.raises(
            TypeError,
            match=r"with_spec\(\) got unexpected keyword arguments: {'invalid'}.",
        ):
            base.with_spec(invalid=10)


class TestListAttribute:
    @pytest.fixture
    def list_spec(self):
        @spec_class
        class ListSpec:
            list_values: List[int]
            list_str_values: List[str]

        return ListSpec(list_values=[1, 2, 3], list_str_values=["a", "b", "c"])

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(
            inspect.Signature.from_callable(spec.with_list_value).parameters
        ) == {
            "_item",
            "_index",
            "_insert",
            "_inplace",
        }

        # Constructors
        assert "list_values" not in spec.__dict__
        assert spec.with_list_values().list_values == []
        assert spec.with_list_value().list_values == [0]
        assert spec.with_list_value(1).list_values == [1]

        # Pass through values
        assert spec.with_list_values([2, 3]).list_values == [2, 3]

        # append
        assert spec.with_list_value(3).with_list_value(3).with_list_value(
            4
        ).list_values == [3, 3, 4]

        # replace
        assert spec.with_list_value(1).with_list_value(2, _index=0).list_values == [2]
        assert spec.with_list_value(1).with_list_value(
            2, _index=0, _insert=False
        ).list_values == [2]

        # insert
        assert spec.with_list_values([1, 2, 3]).with_list_value(
            4, _index=0, _insert=True
        ).list_values == [4, 1, 2, 3]

        with pytest.raises(ValueError, match="Attempted to add an invalid item "):
            spec.with_list_value("string")

        spec.list_values = [1, 2, 3, 4]
        assert spec.list_values == [1, 2, 3, 4]

    def test_transform(self, list_spec):

        spec = list_spec.with_list_values([1]).with_list_str_values(["a"])
        assert set(
            inspect.Signature.from_callable(spec.transform_list_value).parameters
        ) == {
            "_value_or_index",
            "_transform",
            "_by_index",
            "_inplace",
        }

        # scalar form
        assert spec.transform_list_values(lambda x: x * 2).list_values == [1, 1]

        # by value
        assert spec.transform_list_value(1, lambda x: x * 2).list_values == [2]
        assert spec.transform_list_str_value("a", lambda x: x * 2).list_str_values == [
            "aa"
        ]

        # by index
        assert spec.transform_list_value(
            0, lambda x: x * 2, _by_index=True
        ).list_values == [2]
        assert spec.transform_list_str_value(0, lambda x: x * 2).list_str_values == [
            "aa"
        ]

        # check raises if value not in list to be transformed
        with pytest.raises(
            ValueError,
            match=r"Item `2` not found in collection `ListSpec.list_values`\.",
        ):
            spec.transform_list_value(2, lambda x: x)
        with pytest.raises(
            ValueError,
            match=r"Item `'b'` not found in collection `ListSpec.list_str_values`\.",
        ):
            spec.transform_list_str_value("b", lambda x: x)
        with pytest.raises(
            IndexError,
            match=r"Index `2` not found in collection `ListSpec.list_str_values`\.",
        ):
            spec.transform_list_str_value(2, lambda x: x)

    def test_without(self, list_spec):
        assert set(
            inspect.Signature.from_callable(list_spec.without_list_value).parameters
        ) == {
            "_value_or_index",
            "_by_index",
            "_inplace",
        }

        assert list_spec.without_list_value(1).list_values == [2, 3]
        assert list_spec.without_list_value(1, _by_index=True).list_values == [1, 3]

        assert list_spec.without_list_str_value("a").list_str_values == ["b", "c"]
        assert list_spec.without_list_str_value(1).list_str_values == ["a", "c"]
        assert list_spec.without_list_str_value(1, _by_index=True).list_str_values == [
            "a",
            "c",
        ]


class TestSpecListAttribute:
    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(
            inspect.Signature.from_callable(spec.with_spec_list_item).parameters
        ) == {
            "_item",
            "_index",
            "_insert",
            "_inplace",
            "nested_scalar",
            "nested_scalar2",
        }

        # Constructors
        assert "spec_list_items" not in spec.__dict__
        assert spec.with_spec_list_items().spec_list_items == []
        unkeyed = UnkeyedSpec()
        assert spec.with_spec_list_item(unkeyed).spec_list_items[0] is unkeyed
        assert isinstance(spec.with_spec_list_item().spec_list_items[0], UnkeyedSpec)

        # append
        assert (
            spec.with_spec_list_item(unkeyed)
            .with_spec_list_item(unkeyed)
            .with_spec_list_item(unkeyed)
            .spec_list_items
            == [unkeyed] * 3
        )

        # insert
        assert spec.with_spec_list_items(
            [unkeyed, unkeyed, unkeyed]
        ).with_spec_list_item(
            _index=1, _insert=True, nested_scalar=10
        ).spec_list_items == [
            unkeyed,
            UnkeyedSpec(nested_scalar=10),
            unkeyed,
            unkeyed,
        ]

        # replace
        assert spec.with_spec_list_items(
            [unkeyed, unkeyed, unkeyed]
        ).with_spec_list_item(
            _index=0, _insert=False, nested_scalar=10
        ).spec_list_items == [
            UnkeyedSpec(nested_scalar=10),
            unkeyed,
            unkeyed,
        ]

        # remove
        assert spec.with_spec_list_items(
            [unkeyed, unkeyed, unkeyed]
        ).without_spec_list_item(unkeyed).without_spec_list_item(
            -1
        ).spec_list_items == [
            unkeyed
        ]
        assert spec.with_spec_list_items(
            [unkeyed, unkeyed, unkeyed]
        ).without_spec_list_item(unkeyed).without_spec_list_item(
            -1, _by_index=True
        ).spec_list_items == [
            unkeyed
        ]

    def test_transform(self, spec_cls):

        spec = spec_cls(spec_list_items=[UnkeyedSpec(), UnkeyedSpec()])
        assert set(
            inspect.Signature.from_callable(spec.transform_spec_list_item).parameters
        ) == {
            "_value_or_index",
            "_transform",
            "_by_index",
            "_inplace",
            "nested_scalar",
            "nested_scalar2",
        }

        # scalar form
        assert (
            spec.transform_spec_list_items(lambda x: x * 2).spec_list_items
            == [UnkeyedSpec()] * 4
        )

        # by value
        assert spec.transform_spec_list_item(
            UnkeyedSpec(), lambda x: x.with_nested_scalar(3)
        ).spec_list_items == [
            UnkeyedSpec(nested_scalar=3),
            UnkeyedSpec(nested_scalar=1),
        ]  # TODO: transform all matches
        assert spec.transform_spec_list_item(
            UnkeyedSpec(), nested_scalar=lambda x: 3
        ).spec_list_items == [
            UnkeyedSpec(nested_scalar=3),
            UnkeyedSpec(nested_scalar=1),
        ]  # TODO: transform all matches

        # by index
        assert spec.transform_spec_list_item(
            0, lambda x: x.with_nested_scalar(3)
        ).spec_list_items == [
            UnkeyedSpec(nested_scalar=3),
            UnkeyedSpec(nested_scalar=1),
        ]
        assert spec.transform_spec_list_item(
            1, nested_scalar=lambda x: 3, _by_index=True
        ).spec_list_items == [
            UnkeyedSpec(nested_scalar=1),
            UnkeyedSpec(nested_scalar=3),
        ]

    def test_without(self, spec_cls):

        spec = spec_cls(
            spec_list_items=[UnkeyedSpec(nested_scalar=1), UnkeyedSpec(nested_scalar=2)]
        )
        assert set(
            inspect.Signature.from_callable(spec.without_spec_list_item).parameters
        ) == {
            "_value_or_index",
            "_by_index",
            "_inplace",
        }

        assert spec.without_spec_list_item(
            UnkeyedSpec(nested_scalar=1)
        ).spec_list_items == [UnkeyedSpec(nested_scalar=2)]
        assert spec.without_spec_list_item(1).spec_list_items == [
            UnkeyedSpec(nested_scalar=1)
        ]
        assert spec.without_spec_list_item(1, _by_index=True).spec_list_items == [
            UnkeyedSpec(nested_scalar=1)
        ]


class TestDictAttribute:
    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(
            inspect.Signature.from_callable(spec.with_dict_value).parameters
        ) == {
            "_key",
            "_value",
            "_inplace",
        }

        # constructors
        assert "dict_values" not in spec.__dict__
        assert spec.with_dict_values({}).dict_values == {}
        assert spec.with_dict_value("a", 1).dict_values == {"a": 1}

        # update dictionary
        assert spec.with_dict_values({"a": 1, "b": 2}) is not spec
        assert spec.with_dict_values({"a": 1, "b": 2}).with_dict_value(
            "c", 3
        ).dict_values == {"a": 1, "b": 2, "c": 3}
        assert spec.with_dict_values({"a": 1, "b": 2}).with_dict_value(
            "c", 3
        ).dict_values == {"a": 1, "b": 2, "c": 3}

        # inplace update
        assert (
            spec.with_dict_values({"a": 1, "b": 2}, _inplace=True).with_dict_value(
                "c", 3, _inplace=True
            )
            is spec
        )
        assert spec.dict_values == {"a": 1, "b": 2, "c": 3}

        # check for invalid types
        with pytest.raises(
            ValueError,
            match="Attempted to add an invalid item `'Hello World'` to `Spec.dict_values`",
        ):
            spec.with_dict_value("a", "Hello World")

        spec.dict_values = {"a": 1, "b": 2}
        assert spec.dict_values == {"a": 1, "b": 2}

    def test_transform(self, spec_cls):
        spec = spec_cls(dict_values={"a": 1})
        assert set(
            inspect.Signature.from_callable(spec.transform_dict_value).parameters
        ) == {
            "_key",
            "_transform",
            "_inplace",
        }

        assert spec.transform_dict_values(lambda x: {"a": 2}).dict_values == {"a": 2}
        assert spec.transform_dict_value("a", lambda x: x + 1).dict_values == {"a": 2}

    def test_without(self, spec_cls):
        spec = spec_cls(dict_values={"a": 1})
        assert set(
            inspect.Signature.from_callable(spec.without_dict_value).parameters
        ) == {
            "_key",
            "_inplace",
        }

        assert spec.without_dict_value("a").dict_values == {}


class TestSpecDictAttribute:
    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(
            inspect.Signature.from_callable(spec.with_spec_dict_item).parameters
        ) == {
            "_key",
            "_value",
            "_inplace",
            "nested_scalar",
            "nested_scalar2",
        }

        # Constructors
        assert "spec_dict_items" not in spec.__dict__
        unkeyed = UnkeyedSpec()
        assert spec.with_spec_dict_item("a", unkeyed).spec_dict_items["a"] is unkeyed
        assert isinstance(
            spec.with_spec_dict_item("a").spec_dict_items["a"], UnkeyedSpec
        )

        # Insert
        assert spec.with_spec_dict_item("a", unkeyed).with_spec_dict_item(
            "b", nested_scalar=3
        ).spec_dict_items == {"a": unkeyed, "b": UnkeyedSpec(nested_scalar=3)}
        assert spec.with_spec_dict_item("a", unkeyed).with_spec_dict_item(
            "a", nested_scalar=3
        ).spec_dict_items == {"a": UnkeyedSpec(nested_scalar=3)}

    def test_transform(self, spec_cls):

        spec = spec_cls(
            spec_dict_items={
                "a": UnkeyedSpec(nested_scalar=1),
                "b": UnkeyedSpec(nested_scalar=2),
            }
        )
        assert set(
            inspect.Signature.from_callable(spec.transform_spec_dict_item).parameters
        ) == {"_key", "_transform", "_inplace", "nested_scalar", "nested_scalar2"}

        # scalar form
        assert spec.transform_spec_dict_items(lambda x: {}).spec_dict_items == {}

        # by value
        assert spec.transform_spec_dict_item(
            "a", lambda x: x.with_nested_scalar(3)
        ).spec_dict_items == {
            "a": UnkeyedSpec(nested_scalar=3),
            "b": UnkeyedSpec(nested_scalar=2),
        }
        assert spec.transform_spec_dict_item(
            "a", nested_scalar=lambda x: 3
        ).spec_dict_items == {
            "a": UnkeyedSpec(nested_scalar=3),
            "b": UnkeyedSpec(nested_scalar=2),
        }

        # Check missing
        with pytest.raises(KeyError):
            spec.transform_spec_dict_item("c", nested_scalar=lambda x: 3)

    def test_without(self, spec_cls):

        spec = spec_cls(
            spec_dict_items={
                "a": UnkeyedSpec(nested_scalar=1),
                "b": UnkeyedSpec(nested_scalar=2),
            }
        )
        assert set(
            inspect.Signature.from_callable(spec.without_spec_dict_item).parameters
        ) == {
            "_key",
            "_inplace",
        }

        assert spec.without_spec_dict_item("a").spec_dict_items == {
            "b": UnkeyedSpec(nested_scalar=2)
        }


class TestSetAttribute:
    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_set_value).parameters) == {
            "_item",
            "_inplace",
        }

        # constructors
        assert "set_values" not in spec.__dict__
        assert spec.with_set_values().set_values == set()
        assert spec.with_set_value("a").set_values == {"a"}

        # update set
        assert spec.with_set_values({"a", "b"}) is not spec
        assert spec.with_set_values({"a", "b"}).with_set_value("c").set_values == {
            "a",
            "b",
            "c",
        }
        assert spec.with_set_values({"a", "b"}).with_set_value("b").set_values == {
            "a",
            "b",
        }

        # inplace update
        assert (
            spec.with_set_values({"a", "b"}, _inplace=True).with_set_value(
                "c", _inplace=True
            )
            is spec
        )
        assert spec.set_values == {"a", "b", "c"}

        # check for invalid types
        with pytest.raises(
            ValueError,
            match="Attempted to add an invalid item `1` to `Spec.set_values`. Expected item of type `<class 'str'>`",
        ):
            spec.with_set_value(1)

    def test_transform(self, spec_cls):
        spec = spec_cls(set_values={"a", "b"})
        assert set(
            inspect.Signature.from_callable(spec.transform_set_value).parameters
        ) == {
            "_item",
            "_transform",
            "_inplace",
        }

        assert spec.transform_set_values(lambda x: x | {"c"}).set_values == {
            "a",
            "b",
            "c",
        }
        assert spec.transform_set_value("a", lambda x: "c").set_values == {"b", "c"}

        with pytest.raises(ValueError):
            assert spec.transform_set_value("c", lambda x: "c")

    def test_without(self, spec_cls):
        spec = spec_cls(set_values={"a", "b"})
        assert set(
            inspect.Signature.from_callable(spec.without_set_value).parameters
        ) == {
            "_item",
            "_inplace",
        }

        assert spec.without_set_value("a").set_values == {"b"}
