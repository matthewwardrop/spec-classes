import inspect
from typing import List

import pytest

from spec_classes import spec_class


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
            "_if",
        }

        # Constructors
        assert "list_values" not in spec.__dict__
        assert spec.with_list_values().list_values == []
        assert spec.with_list_value().list_values == [0]
        assert spec.with_list_value(1).list_values == [1]
        assert spec.with_list_value(1).with_list_value(2, _if=False).list_values == [1]

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
            "_if",
        }

        # scalar form
        assert spec.transform_list_values(lambda x: x * 2).list_values == [1, 1]

        # by value
        assert spec.transform_list_value(1, lambda x: x * 2).list_values == [2]
        assert spec.transform_list_value(1, lambda x: x * 2, _if=False).list_values == [
            1
        ]
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
            "_if",
        }

        assert list_spec.without_list_value(1).list_values == [2, 3]
        assert list_spec.without_list_value(1, _by_index=True).list_values == [1, 3]
        assert list_spec.without_list_value(1, _if=False).list_values == [1, 2, 3]

        assert list_spec.without_list_str_value("a").list_str_values == ["b", "c"]
        assert list_spec.without_list_str_value(1).list_str_values == ["a", "c"]
        assert list_spec.without_list_str_value(1, _by_index=True).list_str_values == [
            "a",
            "c",
        ]


class TestSpecListAttribute:
    def test_with(self, spec_cls, unkeyed_spec_cls):

        spec = spec_cls()
        assert set(
            inspect.Signature.from_callable(spec.with_spec_list_item).parameters
        ) == {
            "_item",
            "_index",
            "_insert",
            "_inplace",
            "_if",
            "nested_scalar",
            "nested_scalar2",
        }

        # Constructors
        assert "spec_list_items" not in spec.__dict__
        assert spec.with_spec_list_items().spec_list_items == []
        unkeyed = unkeyed_spec_cls()
        assert spec.with_spec_list_item(unkeyed).spec_list_items[0] is unkeyed
        assert isinstance(
            spec.with_spec_list_item().spec_list_items[0], unkeyed_spec_cls
        )
        assert (
            spec.with_spec_list_item({"nested_scalar": 10})
            .spec_list_items[0]
            .nested_scalar
            == 10
        )

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
            unkeyed_spec_cls(nested_scalar=10),
            unkeyed,
            unkeyed,
        ]

        # replace
        assert spec.with_spec_list_items(
            [unkeyed, unkeyed, unkeyed]
        ).with_spec_list_item(
            _index=0, _insert=False, nested_scalar=10
        ).spec_list_items == [
            unkeyed_spec_cls(nested_scalar=10),
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

    def test_update(self, spec_cls, unkeyed_spec_cls, keyed_spec_cls):
        spec = spec_cls(
            spec_list_items=[unkeyed_spec_cls(), unkeyed_spec_cls()],
            keyed_spec_list_items=[keyed_spec_cls("a"), keyed_spec_cls("b")],
        )
        assert set(
            inspect.Signature.from_callable(spec.update_spec_list_item).parameters
        ) == {
            "_value_or_index",
            "_new_item",
            "_by_index",
            "_inplace",
            "_if",
            "nested_scalar",
            "nested_scalar2",
        }

        assert spec.update_spec_list_item(0) is not spec
        assert spec.update_spec_list_item(0).spec_list_items[0].nested_scalar == 1
        assert (
            spec.update_spec_list_item(0, unkeyed_spec_cls(nested_scalar=100))
            .spec_list_items[0]
            .nested_scalar
            == 100
        )
        assert (
            spec.update_spec_list_item(0, nested_scalar=100, _if=False)
            .spec_list_items[0]
            .nested_scalar
            == 1
        )
        assert (
            spec.update_spec_list_item(0, nested_scalar=100)
            .spec_list_items[0]
            .nested_scalar
            == 100
        )

        assert (
            spec.update_keyed_spec_list_item(0).keyed_spec_list_items[0].nested_scalar
            == 1
        )
        assert (
            spec.update_keyed_spec_list_item("a", keyed_spec_cls("c"))
            .keyed_spec_list_items[0]
            .key
            == "c"
        )
        assert (
            spec.update_keyed_spec_list_item(0, keyed_spec_cls("c"))
            .keyed_spec_list_items[0]
            .key
            == "c"
        )
        assert (
            spec.update_keyed_spec_list_item(keyed_spec_cls("a"), keyed_spec_cls("c"))
            .keyed_spec_list_items[0]
            .key
            == "c"
        )
        assert (
            spec.update_keyed_spec_list_item("a", nested_scalar=100)
            .keyed_spec_list_items[0]
            .nested_scalar
            == 100
        )
        assert (
            spec.update_keyed_spec_list_item(0, nested_scalar=100)
            .keyed_spec_list_items[0]
            .nested_scalar
            == 100
        )

        # Check that mutations in key work fine
        assert set(
            spec.update_keyed_spec_list_item("b", key="c").keyed_spec_list_items.keys()
        ) == {"a", "c"}

        # Check that new items are not created when missing
        with pytest.raises(IndexError):
            spec.update_keyed_spec_list_item(10)
        with pytest.raises(KeyError):
            spec.update_keyed_spec_list_item("c")
        with pytest.raises(ValueError):
            spec.update_keyed_spec_list_item(keyed_spec_cls("c"))

    def test_transform(self, spec_cls, unkeyed_spec_cls):

        spec = spec_cls(spec_list_items=[unkeyed_spec_cls(), unkeyed_spec_cls()])
        assert set(
            inspect.Signature.from_callable(spec.transform_spec_list_item).parameters
        ) == {
            "_value_or_index",
            "_transform",
            "_by_index",
            "_inplace",
            "_if",
            "nested_scalar",
            "nested_scalar2",
        }

        # scalar form
        assert (
            spec.transform_spec_list_items(lambda x: x * 2).spec_list_items
            == [unkeyed_spec_cls()] * 4
        )

        # by value
        assert spec.transform_spec_list_item(
            unkeyed_spec_cls(), lambda x: x.with_nested_scalar(3)
        ).spec_list_items == [
            unkeyed_spec_cls(nested_scalar=3),
            unkeyed_spec_cls(nested_scalar=1),
        ]  # TODO: transform all matches
        assert spec.transform_spec_list_item(
            unkeyed_spec_cls(), nested_scalar=lambda x: 3
        ).spec_list_items == [
            unkeyed_spec_cls(nested_scalar=3),
            unkeyed_spec_cls(nested_scalar=1),
        ]  # TODO: transform all matches

        # by index
        assert spec.transform_spec_list_item(
            0, lambda x: x.with_nested_scalar(3)
        ).spec_list_items == [
            unkeyed_spec_cls(nested_scalar=3),
            unkeyed_spec_cls(nested_scalar=1),
        ]
        assert spec.transform_spec_list_item(
            1, nested_scalar=lambda x: 3, _by_index=True
        ).spec_list_items == [
            unkeyed_spec_cls(nested_scalar=1),
            unkeyed_spec_cls(nested_scalar=3),
        ]

    def test_without(self, spec_cls, unkeyed_spec_cls):

        spec = spec_cls(
            spec_list_items=[
                unkeyed_spec_cls(nested_scalar=1),
                unkeyed_spec_cls(nested_scalar=2),
            ]
        )
        assert set(
            inspect.Signature.from_callable(spec.without_spec_list_item).parameters
        ) == {
            "_value_or_index",
            "_by_index",
            "_inplace",
            "_if",
        }

        assert spec.without_spec_list_item(
            unkeyed_spec_cls(nested_scalar=1)
        ).spec_list_items == [unkeyed_spec_cls(nested_scalar=2)]
        assert spec.without_spec_list_item(1).spec_list_items == [
            unkeyed_spec_cls(nested_scalar=1)
        ]
        assert spec.without_spec_list_item(1, _by_index=True).spec_list_items == [
            unkeyed_spec_cls(nested_scalar=1)
        ]
