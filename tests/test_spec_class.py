from __future__ import annotations

import inspect
import textwrap
from typing import Any, Callable, Dict, List, Set, Union

import pytest

from spec_classes import MISSING, spec_class, AttrProxy, FrozenInstanceError


@spec_class
class UnkeyedSpec:
    nested_scalar: int = 1
    nested_scalar2: str = 'original value'


@spec_class(_key='key')
class KeyedSpec:
    key: str = 'key'
    nested_scalar: int = 1
    nested_scalar2: str = 'original value'


@spec_class(_key='key')
class Spec:
    key: str = 'key'
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
    return Spec


class TestFramework:

    def test_key(self, spec_cls):
        assert spec_cls.__spec_class_key__ == 'key'

    def test_annotations(self, spec_cls):
        assert set(spec_cls.__annotations__) == {
            'dict_values',
            'key',
            'keyed_spec_dict_items',
            'keyed_spec_list_items',
            'list_values',
            'set_values',
            'scalar',
            'spec',
            'spec_dict_items',
            'spec_list_items',
            'recursive',
        }

    def test_spec_inheritance(self):

        @spec_class(_key='value')
        class Item:
            value: int

        @spec_class
        class ItemSub(Item):
            value2: int = 1

        assert set(ItemSub.__spec_class_annotations__) == {
            'value', 'value2'
        }
        assert ItemSub.__spec_class_key__ == 'value'

        @spec_class(_key=None)
        class ItemSubSub(ItemSub):
            value3: int = 1

        assert set(ItemSubSub.__spec_class_annotations__) == {
            'value', 'value2', 'value3'
        }
        assert ItemSubSub.__spec_class_key__ is None

    def test_spec_arguments(self):

        @spec_class('value', items=List[str])
        class Item:
            pass

        assert hasattr(Item, 'with_value')
        assert hasattr(Item, 'transform_value')
        assert hasattr(Item, 'with_items')
        assert hasattr(Item, 'with_item')
        assert hasattr(Item, 'without_item')
        assert hasattr(Item, 'transform_item')

        @spec_class(_key='key', key=str)
        class Item:
            pass

        assert Item.__annotations__ == {'key': str}

        with pytest.raises(ValueError, match='`spec_cls` cannot be used to generate helper methods for private attributes'):
            @spec_class('_private')
            class Item:
                pass

    def test_annotation_overrides(self):

        @spec_class(x=int)
        class Item:
            x: str

        assert Item.__annotations__ == {'x': 'str'}
        assert Item.__spec_class_annotations__ == {'x': int}

        with pytest.raises(TypeError):
            Item().x = 'invalid type'

    def test_spec_methods(self):

        assert hasattr(Spec, '__init__')
        assert hasattr(Spec, '__repr__')
        assert hasattr(Spec, '__eq__')

        assert set(inspect.Signature.from_callable(Spec.__init__).parameters) == {
            'dict_values',
            'key',
            'keyed_spec_dict_items',
            'keyed_spec_list_items',
            'list_values',
            'recursive',
            'scalar',
            'self',
            'set_values',
            'spec',
            'spec_dict_items',
            'spec_list_items'
        }
        assert inspect.Signature.from_callable(Spec.__init__).parameters['key'].default == 'key'
        for attr, param in inspect.Signature.from_callable(Spec.__init__).parameters.items():
            if attr not in {'self', 'key'}:
                assert param.default is MISSING

        assert Spec(key="key").key == "key"
        assert repr(Spec(
            key="key", list_values=[1, 2, 3], dict_values={'a': 1, 'b': 2},
            recursive=Spec(key="nested"), set_values={'a'},  # sets are unordered, so we use one item to guarantee order
        )) == textwrap.dedent("""
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
        """).strip()

        assert Spec(
            key="key", list_values=[1, 2, 3], dict_values={'a': 1, 'b': 2},
            recursive=Spec(key="nested"), set_values={'a'},  # sets are unordered, so we use one item to guarantee order
        ).__repr__(indent=False) == (
            "Spec(key='key', scalar=MISSING, list_values=[1, 2, 3], dict_values={'a': 1, 'b': 2}, set_values={'a'}, "
            "spec=MISSING, spec_list_items=MISSING, spec_dict_items=MISSING, keyed_spec_list_items=MISSING, keyed_spec_dict_items=MISSING, "
            "recursive=Spec(key='nested', scalar=MISSING, list_values=MISSING, dict_values=MISSING, set_values=MISSING, spec=MISSING, "
            "spec_list_items=MISSING, spec_dict_items=MISSING, keyed_spec_list_items=MISSING, keyed_spec_dict_items=MISSING, recursive=MISSING))"
        )

        # Check that type checking works during direct mutation of elements
        s = Spec(key="key")
        s.scalar = 10
        assert s.scalar == 10

        with pytest.raises(TypeError, match=r"Attempt to set `Spec\.scalar` with an invalid type \[got `'string'`; expecting `<class 'int'>`\]."):
            s.scalar = 'string'

        # Check that attribute deletion works
        del s.scalar
        assert 'scalar' not in s.__dict__

        # Test empty containers
        assert Spec(
            key="key", list_values=[], dict_values={}, set_values=set(),  # sets are unordered, so we use one item to guarantee order
        ).__repr__(indent=True) == textwrap.dedent("""
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
        """).strip()

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

        assert hasattr(Item, '__init__')
        assert hasattr(Item, '__repr__')
        assert hasattr(Item, '__eq__')

        assert set(inspect.Signature.from_callable(Item.__init__).parameters) == {'self', 'x', 'f', 'g'}
        assert inspect.Signature.from_callable(Item.__init__).parameters['x'].default == 1

        assert repr(Item()) == "Item(x=1, f=<bound method f of self>, g=MISSING)"

        def f(x):
            return x
        assert Item().with_f(f).f is f
        assert Item().with_g(Item).g is Item

        assert Item() == Item()
        assert Item().with_f(f) != Item()

        # Test that key default properly unset when it is a method or property
        @spec_class(_key='key')
        class Item:

            @property
            def key(self):
                return 'key'

        assert set(inspect.Signature.from_callable(Item.__init__).parameters) == {'self', 'key'}
        assert inspect.Signature.from_callable(Item.__init__).parameters['key'].default is MISSING

    def test_attr_deletion(self):
        @spec_class
        class MyClass:
            mylist: list = []

        m = MyClass()
        del m.mylist
        assert m.mylist is not MyClass.mylist
        assert m.mylist == []

    def test_shallowcopy(self):

        @spec_class(_shallowcopy=['shallow_list'])
        class Item:
            value: str
            deep_list: list
            shallow_list: object

        assert Item.__spec_class_shallowcopy__ == {'shallow_list'}

        list_obj = []
        assert Item().with_deep_list(list_obj).with_shallow_list(list_obj).with_value('x').deep_list is not list_obj
        assert Item().with_deep_list(list_obj).with_shallow_list(list_obj).with_value('x').shallow_list is list_obj

        @spec_class(_shallowcopy=True)
        class ShallowItem:
            value: str
            deep_list: list
            shallow_list: object

        assert ShallowItem.__spec_class_shallowcopy__ == {'value', 'deep_list', 'shallow_list'}

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

        assert set(inspect.Signature.from_callable(Item.__init__).parameters) == {'self'}
        assert isinstance(Item(), Item)

        @spec_class
        class Item2:
            x: int

            @property
            def x(self):
                return getattr(self, '_x', 1)

            @x.setter
            def x(self, x):
                self._x = x

        assert set(inspect.Signature.from_callable(Item2.__init__).parameters) == {'self', 'x'}
        assert inspect.Signature.from_callable(Item2.__init__).parameters['x'].default is MISSING
        assert Item2().x == 1
        assert Item2(x=10).x == 10

        @spec_class('x')
        class Item3:
            x: int

            @property
            def x(self):
                return 1

        assert set(inspect.Signature.from_callable(Item3.__init__).parameters) == {'self', 'x'}
        assert inspect.Signature.from_callable(Item3.__init__).parameters['x'].default is MISSING

        with pytest.raises(AttributeError, match="Cannot set `Item3.x` to `1`. Is this a property without a setter?"):
            assert Item3(x=1)

    def test_spec_validation(self):

        with pytest.raises(ValueError, match="is missing required arguments to populate attributes"):
            @spec_class(_init=False)
            class Item:
                x: int = 1

    def test_singularisation(self):
        assert spec_class._get_singular_form('values') == 'value'
        assert spec_class._get_singular_form('classes') == 'class'
        assert spec_class._get_singular_form('collection') == 'collection_item'

    def test_frozen(self):
        @spec_class(_frozen=True)
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

    def test_special_types(self):
        @spec_class
        class Item:
            x: int
            y: int = AttrProxy('x', host_attr='y')
            z: int = AttrProxy('x', transform=lambda x: x ** 2)

        assert Item(x=2).y == 2
        assert Item(x=2).z == 4

        with pytest.raises(AttributeError, match=r"`Item\.x` has not yet been assigned a value\."):
            Item(x=MISSING).x

        with pytest.raises(AttributeError, match=r"Cannot set `Item\.z` to `10`\. Is this a property without a setter\?"):
            Item(x=1, z=10)

        assert Item(x=1, y=10).x == 1
        assert Item(x=1, y=10).y == 10

        i = Item(x=2, y=10)
        del i.y
        assert i.y == 2

        with pytest.raises(AttributeError, match=r"`Item\.y` has not yet been assigned a value\."):
            Item().y


class TestTypeChecking:

    def test_type_checking(self):

        assert spec_class._check_type("string", str)
        assert spec_class._check_type([], list)

        assert spec_class._check_type([], List)
        assert not spec_class._check_type('a', List)
        assert spec_class._check_type(['a', 'b'], List[str])
        assert not spec_class._check_type([1, 2], List[str])

        assert spec_class._check_type({}, Dict)
        assert not spec_class._check_type('a', Dict)
        assert spec_class._check_type({'a': 1, 'b': 2}, Dict[str, int])
        assert not spec_class._check_type({'a': '1', 'b': '2'}, Dict[str, int])
        assert not spec_class._check_type({1: 'a', 2: 'b'}, Dict[str, int])

        assert spec_class._check_type(set(), Set)
        assert not spec_class._check_type('a', Set)
        assert spec_class._check_type({'a', 'b'}, Set[str])
        assert not spec_class._check_type({1, 2}, Set[str])

        assert spec_class._check_type(lambda x: x, Callable)

        assert spec_class._check_type([1, 'a'], List[Union[str, int]])

    def test_get_collection_item_type(self):
        assert spec_class._get_collection_item_type(list) is Any
        assert spec_class._get_collection_item_type(List) is Any
        assert spec_class._get_collection_item_type(List[str]) is str
        assert spec_class._get_collection_item_type(Dict[str, int]) is int
        assert spec_class._get_collection_item_type(Set[str]) is str

    def test_get_spec_class_for_type(self):
        assert spec_class._get_spec_class_for_type(Spec) is Spec
        assert spec_class._get_spec_class_for_type(Union[str, Spec]) is None
        assert spec_class._get_spec_class_for_type(Union[str, Spec], allow_polymorphic=True) is Spec
        assert spec_class._get_spec_class_for_type(Union[str, Spec, UnkeyedSpec]) is None

        assert spec_class._get_spec_class_for_type(list) is None
        assert spec_class._get_spec_class_for_type(List) is None
        assert spec_class._get_spec_class_for_type(List[Spec]) is None

    def test_attr_type_label(self):
        assert spec_class._attr_type_label(str) == "str"
        assert spec_class._attr_type_label(object) == "object"
        assert spec_class._attr_type_label(Spec) == "Spec"
        assert spec_class._attr_type_label(List[str]) == "object"


class TestMutationHelpers:

    def test__with_attr(self):
        @spec_class
        class Item:
            attr: str

        item = Item()

        with pytest.raises(AttributeError, match=r"`Item\.attr` has not yet been assigned a value\."):
            item.attr
        with pytest.raises(AttributeError, match=r"`Item\.attr` has not yet been assigned a value\."):
            spec_class._with_attr(item, 'attr', MISSING).attr
        assert spec_class._with_attr(item, 'attr', 'string') is not item
        assert spec_class._with_attr(item, 'attr', 'string').attr == 'string'

        with pytest.raises(TypeError, match="Attempt to set `Item.attr` with an invalid type"):
            assert spec_class._with_attr(item, 'attr', 1)

    def test__get_updated_value(self):
        # Simple update
        assert spec_class._get_updated_value(MISSING, new_value="value") == "value"
        assert spec_class._get_updated_value("old_value", new_value="value") == "value"

        # Via constructor
        assert spec_class._get_updated_value(MISSING, constructor=str) == ''
        assert spec_class._get_updated_value(MISSING, constructor=list) == []

        # Via transform
        assert spec_class._get_updated_value("old_value", transform=lambda x: x + "_renewed") == "old_value_renewed"

        # Nested types
        class Object:
            attr = 'default'
        assert spec_class._get_updated_value(MISSING, constructor=Object, attrs={'attr': 'value'}).attr == 'value'
        assert spec_class._get_updated_value(MISSING, constructor=Object, attr_transforms={'attr': lambda x: f'{x}-transformed!'}).attr == 'default-transformed!'
        with pytest.raises(AttributeError, match="'Object' object has no attribute 'missing_attr'"):
            assert spec_class._get_updated_value(MISSING, constructor=Object, attr_transforms={'missing_attr': lambda x: x})

        assert spec_class._get_updated_value(MISSING, constructor=Spec, attrs={'key': 'key', 'scalar': 10}).key == 'key'
        assert spec_class._get_updated_value(MISSING, constructor=Spec, attrs={'key': 'key', 'scalar': 10}).scalar == 10
        assert spec_class._get_updated_value(Spec(key='key', scalar=10), constructor=Spec, attrs={'list_values': [20]}).key == 'key'
        assert spec_class._get_updated_value(Spec(key='key', scalar=10), constructor=Spec, attrs={'list_values': [20]}).scalar == 10
        assert spec_class._get_updated_value(Spec(key='key', scalar=10), constructor=Spec, attrs={'list_values': [20]}).list_values == [20]
        with pytest.raises(TypeError, match="Invalid attribute `invalid_attr` for spec class"):
            assert spec_class._get_updated_value(MISSING, constructor=Spec, attrs={'invalid_attr': 'value'})
        assert spec_class._get_updated_value(MISSING, constructor=Spec, attr_transforms={'key': lambda x: 'override'}).key == 'override'
        with pytest.raises(TypeError, match="Invalid attribute `invalid_attr` for spec class"):
            assert spec_class._get_updated_value(MISSING, constructor=Spec, attr_transforms={'invalid_attr': 'value'})
        assert spec_class._get_updated_value(Spec(key='my_key'), constructor=Spec, replace=True).key == 'key'

        with pytest.raises(ValueError, match="Cannot use attrs on a missing value without a constructor."):
            assert spec_class._get_updated_value(MISSING, attrs={'invalid_attr': 'value'})


class TestScalarAttribute:

    def test_with(self, spec_cls):
        spec = spec_cls(scalar=3)
        assert set(inspect.Signature.from_callable(spec.with_scalar).parameters) == {
            '_new_value', '_inplace'
        }
        assert spec.with_scalar(4) is not spec
        assert spec.with_scalar(4).scalar == 4

        assert spec.with_scalar(4, _inplace=True) is spec
        assert spec.scalar == 4

    def test_transform(self, spec_cls):
        spec = spec_cls(scalar=3)
        assert set(inspect.Signature.from_callable(spec.transform_scalar).parameters) == {
            '_transform', '_inplace'
        }
        assert spec.transform_scalar(lambda x: x * 2) is not spec
        assert spec.transform_scalar(lambda x: x * 2).scalar == 6

        assert spec.transform_scalar(lambda x: x * 2, _inplace=True) is spec
        assert spec.scalar == 6


class TestSpecAttribute:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_spec).parameters) == {
            '_new_value', '_replace', '_inplace', 'nested_scalar', 'nested_scalar2'
        }

        # Constructors
        assert 'spec' not in spec.__dict__
        assert isinstance(spec.with_spec().spec, UnkeyedSpec)
        assert isinstance(spec.transform_spec(lambda x: x).spec, UnkeyedSpec)
        with pytest.raises(TypeError, match=r"Attempt to set `Spec\.spec` with an invalid type"):
            spec.with_spec(None)

        # Assignments
        nested_spec = UnkeyedSpec()
        assert spec.with_spec(nested_spec).spec is nested_spec

        # Nested assignments
        assert spec.with_spec(nested_scalar=2) is not spec
        assert spec.with_spec(nested_scalar=2).spec.nested_scalar == 2
        assert spec.with_spec(nested_scalar2='overridden').spec.nested_scalar2 == 'overridden'
        assert spec.with_spec(nested_scalar2='overridden').with_spec(_replace=True).spec.nested_scalar2 == 'original value'

        assert spec.with_spec(nested_scalar=2, _inplace=True) is spec
        assert spec.spec.nested_scalar == 2

    def test_transform(self, spec_cls):
        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.transform_spec).parameters) == {
            '_transform', '_inplace', 'nested_scalar', 'nested_scalar2'
        }

        # Direct mutation
        assert spec.transform_spec(lambda x: x.with_nested_scalar(3)) is not spec
        assert spec.transform_spec(lambda x: x.with_nested_scalar(3)).spec.nested_scalar == 3

        # Nested mutations
        assert spec.transform_spec(nested_scalar=lambda x: 3) is not spec
        assert spec.transform_spec(nested_scalar=lambda x: 3).spec.nested_scalar == 3

        # Inplace operation
        assert spec.transform_spec(nested_scalar=lambda x: 3, _inplace=True) is spec
        assert spec.transform_spec(nested_scalar=lambda x: 3).spec.nested_scalar == 3

    def test_illegal_nested_update(self, spec_cls):
        base = spec_cls()
        with pytest.raises(TypeError, match=r"with_spec\(\) got unexpected keyword arguments: {'invalid'}."):
            base.with_spec(invalid=10)


class TestListAttribute:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_list_value).parameters) == {
            '_item', '_index', '_insert', '_inplace',
        }

        # Constructors
        assert 'list_values' not in spec.__dict__
        assert spec.with_list_values().list_values == []
        assert spec.with_list_value(1).list_values == [1]

        # Pass through values
        assert spec.with_list_values([2, 3]).list_values == [2, 3]

        # append
        assert spec.with_list_value(3).with_list_value(3).with_list_value(4).list_values == [3, 3, 4]

        # insert
        assert spec.with_list_values([1, 2, 3]).with_list_value(4, _index=0, _insert=True).list_values == [4, 1, 2, 3]

        # replace
        assert spec.with_list_value(1).with_list_value(2, _index=0, _insert=False).list_values == [2]

        # remove
        assert spec.with_list_values([1, 2, 3]).without_list_value(1).without_list_value(-1, _by_index=True).list_values == [2]

        with pytest.raises(ValueError, match="Attempted to add an invalid item "):
            spec.with_list_value('string')

    def test_transform(self, spec_cls):

        spec = spec_cls(list_values=[1])
        assert set(inspect.Signature.from_callable(spec.transform_list_value).parameters) == {
            '_value_or_index', '_transform', '_by_index', '_inplace',
        }

        # scalar form
        assert spec.transform_list_values(lambda x: x * 2).list_values == [1, 1]

        # by value
        assert spec.transform_list_value(1, lambda x: x * 2).list_values == [2]

        # by index
        assert spec.transform_list_value(0, lambda x: x * 2, _by_index=True).list_values == [2]

    def test_without(self, spec_cls):

        spec = spec_cls(list_values=[1, 2, 3])
        assert set(inspect.Signature.from_callable(spec.without_list_value).parameters) == {
            '_value_or_index', '_by_index', '_inplace',
        }

        assert spec.without_list_value(1).list_values == [2, 3]
        assert spec.without_list_value(1, _by_index=True).list_values == [1, 3]


class TestUnkeyedSpecListAttribute:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_spec_list_item).parameters) == {
            '_item', '_index', '_insert', '_replace', '_inplace', 'nested_scalar', 'nested_scalar2'
        }

        # Constructors
        assert 'spec_list_items' not in spec.__dict__
        assert spec.with_spec_list_items().spec_list_items == []
        unkeyed = UnkeyedSpec()
        assert spec.with_spec_list_item(unkeyed).spec_list_items[0] is unkeyed
        assert isinstance(spec.with_spec_list_item().spec_list_items[0], UnkeyedSpec)

        # append
        assert spec.with_spec_list_item(unkeyed).with_spec_list_item(unkeyed).with_spec_list_item(unkeyed).spec_list_items == [unkeyed] * 3

        # insert
        assert spec.with_spec_list_items([unkeyed, unkeyed, unkeyed]).with_spec_list_item(_index=1, _insert=True, nested_scalar=10).spec_list_items == [unkeyed, UnkeyedSpec(nested_scalar=10), unkeyed, unkeyed]

        # replace
        assert spec.with_spec_list_items([unkeyed, unkeyed, unkeyed]).with_spec_list_item(_index=0, _insert=False, nested_scalar=10).spec_list_items == [UnkeyedSpec(nested_scalar=10), unkeyed, unkeyed]

        # remove
        assert spec.with_spec_list_items([unkeyed, unkeyed, unkeyed]).without_spec_list_item(unkeyed).without_spec_list_item(-1, _by_index=True).spec_list_items == [unkeyed]

    def test_transform(self, spec_cls):

        spec = spec_cls(spec_list_items=[UnkeyedSpec(), UnkeyedSpec()])
        assert set(inspect.Signature.from_callable(spec.transform_spec_list_item).parameters) == {
            '_value_or_index', '_transform', '_by_index', '_inplace', 'nested_scalar', 'nested_scalar2'
        }

        # scalar form
        assert spec.transform_spec_list_items(lambda x: x * 2).spec_list_items == [UnkeyedSpec()] * 4

        # by value
        assert spec.transform_spec_list_item(UnkeyedSpec(), lambda x: x.with_nested_scalar(3)).spec_list_items == [UnkeyedSpec(nested_scalar=3), UnkeyedSpec(nested_scalar=1)]  # TODO: transform all matches
        assert spec.transform_spec_list_item(UnkeyedSpec(), nested_scalar=lambda x: 3).spec_list_items == [UnkeyedSpec(nested_scalar=3), UnkeyedSpec(nested_scalar=1)]  # TODO: transform all matches

        # by index
        assert spec.transform_spec_list_item(0, lambda x: x.with_nested_scalar(3), _by_index=True).spec_list_items == [UnkeyedSpec(nested_scalar=3), UnkeyedSpec(nested_scalar=1)]
        assert spec.transform_spec_list_item(1, nested_scalar=lambda x: 3, _by_index=True).spec_list_items == [UnkeyedSpec(nested_scalar=1), UnkeyedSpec(nested_scalar=3)]

    def test_without(self, spec_cls):

        spec = spec_cls(spec_list_items=[UnkeyedSpec(nested_scalar=1), UnkeyedSpec(nested_scalar=2)])
        assert set(inspect.Signature.from_callable(spec.without_spec_list_item).parameters) == {
            '_value_or_index', '_by_index', '_inplace',
        }

        assert spec.without_spec_list_item(UnkeyedSpec(nested_scalar=1)).spec_list_items == [UnkeyedSpec(nested_scalar=2)]
        assert spec.without_spec_list_item(1, _by_index=True).spec_list_items == [UnkeyedSpec(nested_scalar=1)]


class TestKeyedSpecListAttribute:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_keyed_spec_list_item).parameters) == {
            '_item', '_index', '_insert', '_replace', '_inplace', 'key', 'nested_scalar', 'nested_scalar2'
        }

        # Constructors
        assert 'keyed_spec_list_items' not in spec.__dict__
        assert spec.with_keyed_spec_list_items().keyed_spec_list_items == []
        keyed = KeyedSpec()
        assert spec.with_keyed_spec_list_item(keyed).keyed_spec_list_items[0] is keyed
        assert isinstance(spec.with_keyed_spec_list_item().keyed_spec_list_items[0], KeyedSpec)
        assert spec.with_keyed_spec_list_item('mykey').keyed_spec_list_items == [KeyedSpec('mykey')]

        # append
        assert spec.with_keyed_spec_list_item(key='1').with_keyed_spec_list_item('2').keyed_spec_list_items == [
            KeyedSpec('1'), KeyedSpec('2')
        ]

        # insert
        assert spec.with_keyed_spec_list_items([KeyedSpec('1')]).with_keyed_spec_list_item(_index=1, _insert=True, key='2', nested_scalar=10).keyed_spec_list_items == [KeyedSpec('1'), KeyedSpec(key='2', nested_scalar=10)]
        assert spec.with_keyed_spec_list_items([KeyedSpec('1')]).with_keyed_spec_list_item('2', _index=0, _insert=True).keyed_spec_list_items == [KeyedSpec(key='2'), KeyedSpec(key='1')]
        with pytest.raises(ValueError, match=r"Adding .* to list would result in more than instance with the same key: '1'"):
            assert spec.with_keyed_spec_list_item('1').with_keyed_spec_list_item(KeyedSpec(key='1'), _insert=True).keyed_spec_list_items

        # replace / update
        assert spec.with_keyed_spec_list_items([KeyedSpec('1', nested_scalar2="value")]).with_keyed_spec_list_item('1', nested_scalar=10).keyed_spec_list_items == [KeyedSpec(key='1', nested_scalar=10, nested_scalar2="value")]
        assert spec.with_keyed_spec_list_items([KeyedSpec('1', nested_scalar2="value")]).with_keyed_spec_list_item(_index='1', _insert=False, nested_scalar=10).keyed_spec_list_items == [KeyedSpec(key='1', nested_scalar=10, nested_scalar2="value")]
        assert spec.with_keyed_spec_list_items([KeyedSpec('1', nested_scalar2="value")]).with_keyed_spec_list_item(_index=0, _insert=False, nested_scalar=10).keyed_spec_list_items == [KeyedSpec(key='1', nested_scalar=10, nested_scalar2="value")]
        assert spec.with_keyed_spec_list_items([KeyedSpec('1', nested_scalar2="value")]).with_keyed_spec_list_item('1', _index=0, _insert=False, nested_scalar=10).keyed_spec_list_items == [KeyedSpec(key='1', nested_scalar=10, nested_scalar2="value")]
        assert spec.with_keyed_spec_list_items([KeyedSpec('1', nested_scalar2="value")]).with_keyed_spec_list_item(_index=0, _insert=False, _replace=True, nested_scalar=10).keyed_spec_list_items == [KeyedSpec(key='key', nested_scalar=10, nested_scalar2="original value")]

    def test_transform(self, spec_cls):

        spec = spec_cls(keyed_spec_list_items=[KeyedSpec(key='a'), KeyedSpec(key='b')])
        assert set(inspect.Signature.from_callable(spec.transform_keyed_spec_list_item).parameters) == {
            '_value_or_index', '_transform', '_by_index', '_inplace', 'key', 'nested_scalar', 'nested_scalar2'
        }

        assert spec.transform_keyed_spec_list_item('c', lambda x: x).keyed_spec_list_items == [KeyedSpec(key='a'), KeyedSpec(key='b'), KeyedSpec(key='c')]

        # by value
        assert spec.transform_keyed_spec_list_item('a', lambda x: x.with_nested_scalar(3)).keyed_spec_list_items == [KeyedSpec(key='a', nested_scalar=3), KeyedSpec(key='b')]
        assert spec.transform_keyed_spec_list_item(KeyedSpec(key='a'), lambda x: x.with_nested_scalar(3)).keyed_spec_list_items == [KeyedSpec(key='a', nested_scalar=3), KeyedSpec(key='b')]

        # by index
        assert spec.transform_keyed_spec_list_item('a', lambda x: x.with_nested_scalar(3), _by_index=True).keyed_spec_list_items == [KeyedSpec(key='a', nested_scalar=3), KeyedSpec(key='b')]
        assert spec.transform_keyed_spec_list_item(0, lambda x: x.with_nested_scalar(3), _by_index=True).keyed_spec_list_items == [KeyedSpec(key='a', nested_scalar=3), KeyedSpec(key='b')]

    def test_without(self, spec_cls):

        spec = spec_cls(keyed_spec_list_items=[KeyedSpec(key='a'), KeyedSpec(key='b')])
        assert set(inspect.Signature.from_callable(spec.without_keyed_spec_list_item).parameters) == {
            '_value_or_index', '_by_index', '_inplace',
        }

        assert spec.without_keyed_spec_list_item(KeyedSpec(key='a')).keyed_spec_list_items == [KeyedSpec(key='b')]
        assert spec.without_keyed_spec_list_item('a').keyed_spec_list_items == [KeyedSpec(key='b')]
        assert spec.without_keyed_spec_list_item('a', _by_index=True).keyed_spec_list_items == [KeyedSpec(key='b')]
        assert spec.without_keyed_spec_list_item(0, _by_index=True).keyed_spec_list_items == [KeyedSpec(key='b')]

    def test_edge_cases(self):
        # Test that two spec classes with the same key cannot be added.
        assert Spec().with_keyed_spec_list_item('a').with_keyed_spec_list_item('b').with_keyed_spec_list_item('a', _index=0, _insert=0).keyed_spec_list_items == [
            KeyedSpec('a'), KeyedSpec('b')
        ]

        with pytest.raises(ValueError, match=r"Adding KeyedSpec\(key='a', nested_scalar=1, nested_scalar2='original value'\) to list would result in more than instance with the same key: 'a'"):
            Spec().with_keyed_spec_list_item('a').with_keyed_spec_list_item('c').transform_keyed_spec_list_item('c', key=lambda x: 'a')

        # Test that spec classes with integer keys raise an error.
        with pytest.raises(ValueError, match="List containers do not support keyed spec classes with integral keys."):
            @spec_class(_key='key')
            class MySpec:
                key: int
                children: List[MySpec]

        # Test that spec classes that happen to have integer key values also fail
        @spec_class(_key='key')
        class MySpec2:
            key: Any
            children: List[MySpec2]

        with pytest.raises(ValueError, match='List containers do not support keyed spec classes with integral keys'):
            MySpec2(None).with_child(1)

        with pytest.raises(ValueError, match='List containers do not support keyed spec classes with integral keys'):
            MySpec2(None).with_child(MySpec2(1))

        # Test that float keys work fine.
        @spec_class(_key='key')
        class MySpec3:
            key: float
            children: List[MySpec3]

        assert MySpec3(1.0).with_child(1.0).children == [MySpec3(1.0)]


class TestDictAttribute:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_dict_value).parameters) == {
            '_key', '_value', '_inplace',
        }

        # constructors
        assert 'dict_values' not in spec.__dict__
        assert spec.with_dict_values({}).dict_values == {}
        assert spec.with_dict_value('a', 1).dict_values == {'a': 1}

        # update dictionary
        assert spec.with_dict_values({'a': 1, 'b': 2}) is not spec
        assert spec.with_dict_values({'a': 1, 'b': 2}).with_dict_value('c', 3).dict_values == {'a': 1, 'b': 2, 'c': 3}
        assert spec.with_dict_values({'a': 1, 'b': 2}).with_dict_value('c', 3).dict_values == {'a': 1, 'b': 2, 'c': 3}

        # inplace update
        assert spec.with_dict_values({'a': 1, 'b': 2}, _inplace=True).with_dict_value('c', 3, _inplace=True) is spec
        assert spec.dict_values == {'a': 1, 'b': 2, 'c': 3}

        # check for invalid types
        with pytest.raises(ValueError, match="Attempted to add an invalid item `'Hello World'` to `Spec.dict_values`"):
            spec.with_dict_value('a', "Hello World")

    def test_transform(self, spec_cls):
        spec = spec_cls(dict_values={'a': 1})
        assert set(inspect.Signature.from_callable(spec.transform_dict_value).parameters) == {
            '_key', '_transform', '_inplace',
        }

        assert spec.transform_dict_values(lambda x: {'a': 2}).dict_values == {'a': 2}
        assert spec.transform_dict_value('a', lambda x: x + 1).dict_values == {'a': 2}

    def test_without(self, spec_cls):
        spec = spec_cls(dict_values={'a': 1})
        assert set(inspect.Signature.from_callable(spec.without_dict_value).parameters) == {
            '_key', '_inplace',
        }

        assert spec.without_dict_value('a').dict_values == {}


class TestUnkeyedSpecDictAttribute:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_spec_dict_item).parameters) == {
            '_key', '_value', '_replace', '_inplace', 'nested_scalar', 'nested_scalar2'
        }

        # Constructors
        assert 'spec_dict_items' not in spec.__dict__
        unkeyed = UnkeyedSpec()
        assert spec.with_spec_dict_item('a', unkeyed).spec_dict_items['a'] is unkeyed
        assert isinstance(spec.with_spec_dict_item('a').spec_dict_items['a'], UnkeyedSpec)

        # Insert
        assert spec.with_spec_dict_item('a', unkeyed).with_spec_dict_item('b', nested_scalar=3).spec_dict_items == {'a': unkeyed, 'b': UnkeyedSpec(nested_scalar=3)}

    def test_transform(self, spec_cls):

        spec = spec_cls(spec_dict_items={'a': UnkeyedSpec(nested_scalar=1), 'b': UnkeyedSpec(nested_scalar=2)})
        assert set(inspect.Signature.from_callable(spec.transform_spec_dict_item).parameters) == {
            '_key', '_transform', '_inplace', 'nested_scalar', 'nested_scalar2'
        }

        # scalar form
        assert spec.transform_spec_dict_items(lambda x: {}).spec_dict_items == {}

        # by value
        assert spec.transform_spec_dict_item('a', lambda x: x.with_nested_scalar(3)).spec_dict_items == {'a': UnkeyedSpec(nested_scalar=3), 'b': UnkeyedSpec(nested_scalar=2)}
        assert spec.transform_spec_dict_item('a', nested_scalar=lambda x: 3).spec_dict_items == {'a': UnkeyedSpec(nested_scalar=3), 'b': UnkeyedSpec(nested_scalar=2)}

    def test_without(self, spec_cls):

        spec = spec_cls(spec_dict_items={'a': UnkeyedSpec(nested_scalar=1), 'b': UnkeyedSpec(nested_scalar=2)})
        assert set(inspect.Signature.from_callable(spec.without_spec_dict_item).parameters) == {
            '_key', '_inplace',
        }

        assert spec.without_spec_dict_item('a').spec_dict_items == {'b': UnkeyedSpec(nested_scalar=2)}


class TestKeyedSpecDictAttribute:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_keyed_spec_dict_item).parameters) == {
            '_value', '_replace', '_inplace', 'key', 'nested_scalar', 'nested_scalar2'
        }

        # Constructors
        assert 'keyed_spec_dict_items' not in spec.__dict__
        keyed = KeyedSpec('key')
        assert spec.with_keyed_spec_dict_items([keyed]).keyed_spec_dict_items['key'] is keyed
        assert spec.with_keyed_spec_dict_item(keyed).keyed_spec_dict_items['key'] is keyed
        assert spec.with_keyed_spec_dict_item('a').keyed_spec_dict_items['a'] == KeyedSpec('a')

        # Insert
        assert spec.with_keyed_spec_dict_item('a', nested_scalar=10).keyed_spec_dict_items == {'a': KeyedSpec('a', nested_scalar=10)}

        # Mutate existing
        assert spec.with_keyed_spec_dict_item('a', nested_scalar=10).with_keyed_spec_dict_item('a', nested_scalar2='overridden').keyed_spec_dict_items == {'a': KeyedSpec('a', nested_scalar=10, nested_scalar2='overridden')}

    def test_transform(self, spec_cls):

        spec = spec_cls(keyed_spec_dict_items={'a': KeyedSpec('a', nested_scalar=1), 'b': KeyedSpec('b', nested_scalar=2)})
        assert set(inspect.Signature.from_callable(spec.transform_keyed_spec_dict_item).parameters) == {
            '_key', '_transform', '_inplace', 'key', 'nested_scalar', 'nested_scalar2'
        }

        # scalar form
        assert spec.transform_keyed_spec_dict_items(lambda x: {}).keyed_spec_dict_items == {}

        # by value
        assert spec.transform_keyed_spec_dict_item('a', lambda x: x.with_nested_scalar(3)).keyed_spec_dict_items == {'a': KeyedSpec('a', nested_scalar=3), 'b': KeyedSpec('b', nested_scalar=2)}
        assert spec.transform_keyed_spec_dict_item(KeyedSpec('a'), nested_scalar=lambda x: 3).keyed_spec_dict_items == {'a': KeyedSpec('a', nested_scalar=3), 'b': KeyedSpec('b', nested_scalar=2)}

        # construction of new instance on the fly
        assert spec.transform_keyed_spec_dict_item('c', lambda x: x.with_nested_scalar(3)).keyed_spec_dict_items == {'a': KeyedSpec('a', nested_scalar=1), 'b': KeyedSpec('b', nested_scalar=2), 'c': KeyedSpec('c', nested_scalar=3)}

    def test_without(self, spec_cls):

        spec = spec_cls(keyed_spec_dict_items={'a': KeyedSpec('a', nested_scalar=1), 'b': KeyedSpec('b', nested_scalar=2)})
        assert set(inspect.Signature.from_callable(spec.without_keyed_spec_dict_item).parameters) == {
            '_key', '_inplace',
        }

        assert spec.without_keyed_spec_dict_item('a').keyed_spec_dict_items == {'b': KeyedSpec('b', nested_scalar=2)}
        assert spec.without_keyed_spec_dict_item(KeyedSpec('a')).keyed_spec_dict_items == {'b': KeyedSpec('b', nested_scalar=2)}


class TestSetAttribute:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_set_value).parameters) == {
            '_item', '_inplace',
        }

        # constructors
        assert 'set_values' not in spec.__dict__
        assert spec.with_set_values().set_values == set()
        assert spec.with_set_value('a').set_values == {'a'}

        # update set
        assert spec.with_set_values({'a', 'b'}) is not spec
        assert spec.with_set_values({'a', 'b'}).with_set_value('c').set_values == {'a', 'b', 'c'}

        # inplace update
        assert spec.with_set_values({'a', 'b'}, _inplace=True).with_set_value('c', _inplace=True) is spec
        assert spec.set_values == {'a', 'b', 'c'}

        # check for invalid types
        with pytest.raises(ValueError, match="Attempted to add an invalid item `1` to `Spec.set_values`. Expected item of type `<class 'str'>`"):
            spec.with_set_value(1)

    def test_transform(self, spec_cls):
        spec = spec_cls(set_values={'a', 'b'})
        assert set(inspect.Signature.from_callable(spec.transform_set_value).parameters) == {
            '_item', '_transform', '_inplace',
        }

        assert spec.transform_set_values(lambda x: x | {'c'}).set_values == {'a', 'b', 'c'}
        assert spec.transform_set_value('a', lambda x: 'c').set_values == {'b', 'c'}

    def test_without(self, spec_cls):
        spec = spec_cls(set_values={'a', 'b'})
        assert set(inspect.Signature.from_callable(spec.without_set_value).parameters) == {
            '_item', '_inplace',
        }

        assert spec.without_set_value('a').set_values == {'b'}
