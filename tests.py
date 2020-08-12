from __future__ import annotations

import inspect
from typing import Dict, List, Set

import pytest

from spec_classes import spec_class


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
    key: str = None
    scalar: int = None
    list_values: List[int] = None
    dict_values: Dict[str, int] = None
    set_values: Set[str] = None
    spec: UnkeyedSpec = None
    spec_list_items: List[UnkeyedSpec] = None
    spec_dict_items: Dict[str, UnkeyedSpec] = None
    keyed_spec_list_items: List[KeyedSpec] = None
    keyed_spec_dict_items: Dict[str, KeyedSpec] = None
    recursive: Spec = None


@pytest.fixture
def spec_cls():
    return Spec


class TestSpecMetadata:

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

        @spec_class
        class Item:
            value: int

        @spec_class
        class ItemSub(Item):
            value2: int = 1

        assert set(ItemSub.__spec_class_annotations__) == {
            'value', 'value2'
        }


class TestSpecScalar:

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


class TestSpecNested:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_spec).parameters) == {
            '_new_value', '_replace', '_inplace', 'nested_scalar', 'nested_scalar2'
        }

        # Constructors
        assert spec.spec is None
        assert isinstance(spec.with_spec().spec, UnkeyedSpec)
        assert isinstance(spec.with_spec(None).spec, UnkeyedSpec)
        assert isinstance(spec.transform_spec(lambda x: x).spec, UnkeyedSpec)

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

#     def test_illegal_nested_update(self, spec_cls):
#         base = spec_cls()
#         with pytest.raises(TypeError) as exc:
#             base.with_item(invalid=10, invalid2=20)
#         # assert exc.value.args[0] == "Attempting to pass invalid nested attributes: ['invalid', 'invalid2']"


class TestSpecList:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_list_value).parameters) == {
            '_item', '_index', '_insert', '_inplace',
        }

        # Constructors
        assert spec.list_values is None
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


class TestSpecListUnkeyed:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_spec_list_item).parameters) == {
            '_item', '_index', '_insert', '_replace', '_inplace', 'nested_scalar', 'nested_scalar2'
        }

        # Constructors
        assert spec.spec_list_items is None
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


class TestSpecListKeyed:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_keyed_spec_list_item).parameters) == {
            '_item', '_index', '_insert', '_replace', '_inplace', 'key', 'nested_scalar', 'nested_scalar2'
        }

        # Constructors
        assert spec.spec_list_items is None
        assert spec.with_keyed_spec_list_items().keyed_spec_list_items == []
        keyed = KeyedSpec()
        assert spec.with_keyed_spec_list_item(keyed).keyed_spec_list_items[0] is keyed
        assert isinstance(spec.with_keyed_spec_list_item().keyed_spec_list_items[0], KeyedSpec)

        # append
        assert spec.with_keyed_spec_list_item(key='1').with_keyed_spec_list_item(key='2').with_keyed_spec_list_item(key='3').keyed_spec_list_items == [
            KeyedSpec('1'), KeyedSpec('2'), KeyedSpec('3')
        ]

        # insert
        assert spec.with_keyed_spec_list_items([KeyedSpec('1')]).with_keyed_spec_list_item(_index=1, _insert=True, key='2', nested_scalar=10).keyed_spec_list_items == [KeyedSpec('1'), KeyedSpec(key='2', nested_scalar=10)]

        # replace
        assert spec.with_keyed_spec_list_items([KeyedSpec('1')]).with_keyed_spec_list_item(_index='1', _insert=False, nested_scalar=10).keyed_spec_list_items == [KeyedSpec(key='1', nested_scalar=10)]
        assert spec.with_keyed_spec_list_items([KeyedSpec('1')]).with_keyed_spec_list_item(_index=0, _insert=False, nested_scalar=10).keyed_spec_list_items == [KeyedSpec(key='1', nested_scalar=10)]
        assert spec.with_keyed_spec_list_items([KeyedSpec('1')]).with_keyed_spec_list_item(_index=0, _insert=False, _replace=True, nested_scalar=10).keyed_spec_list_items == [KeyedSpec(key='key', nested_scalar=10)]

    def test_transform(self, spec_cls):

        spec = spec_cls(keyed_spec_list_items=[KeyedSpec(key='a'), KeyedSpec(key='b')])
        assert set(inspect.Signature.from_callable(spec.transform_keyed_spec_list_item).parameters) == {
            '_value_or_index', '_transform', '_by_index', '_inplace', 'key', 'nested_scalar', 'nested_scalar2'
        }

        # scalar form
        # assert spec.transform_spec_list_items(lambda x: x * 2).spec_list_items == [UnkeyedSpec()] * 4  # TODO: FAIL

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


class TestSpecDict:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_dict_value).parameters) == {
            '_key', '_value', '_inplace',
        }

        # constructors
        assert spec.dict_values is None
        assert spec.with_dict_values({}).dict_values == {}
        assert spec.with_dict_value('a', 1).dict_values == {'a': 1}

        # update dictionary
        assert spec.with_dict_values({'a': 1, 'b': 2}) is not spec
        assert spec.with_dict_values({'a': 1, 'b': 2}).with_dict_value('c', 3).dict_values == {'a': 1, 'b': 2, 'c': 3}
        assert spec.with_dict_values({'a': 1, 'b': 2}).with_dict_value('c', 3).dict_values == {'a': 1, 'b': 2, 'c': 3}

        # inplace update
        assert spec.with_dict_values({'a': 1, 'b': 2}, _inplace=True).with_dict_value('c', 3, _inplace=True) is spec
        assert spec.dict_values == {'a': 1, 'b': 2, 'c': 3}

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


class TestSpecDictUnkeyed:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_spec_dict_item).parameters) == {
            '_key', '_value', '_replace', '_inplace', 'nested_scalar', 'nested_scalar2'
        }

        # Constructors
        assert spec.spec_dict_items is None
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


class TestSpecDictKeyed:

    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_keyed_spec_dict_item).parameters) == {
            '_value', '_replace', '_inplace', 'key', 'nested_scalar', 'nested_scalar2'
        }

        # Constructors
        assert spec.keyed_spec_dict_items is None
        keyed = KeyedSpec('key')
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

    def test_without(self, spec_cls):

        spec = spec_cls(keyed_spec_dict_items={'a': KeyedSpec('a', nested_scalar=1), 'b': KeyedSpec('b', nested_scalar=2)})
        assert set(inspect.Signature.from_callable(spec.without_keyed_spec_dict_item).parameters) == {
            '_key', '_inplace',
        }

        assert spec.without_keyed_spec_dict_item('a').keyed_spec_dict_items == {'b': KeyedSpec('b', nested_scalar=2)}
        assert spec.without_keyed_spec_dict_item(KeyedSpec('a')).keyed_spec_dict_items == {'b': KeyedSpec('b', nested_scalar=2)}
