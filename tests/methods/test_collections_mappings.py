import inspect

import pytest


class TestDictAttribute:
    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(
            inspect.Signature.from_callable(spec.with_dict_value).parameters
        ) == {
            "_key",
            "_value",
            "_inplace",
            "_if",
        }

        # constructors
        assert "dict_values" not in spec.__dict__
        assert spec.with_dict_values({}).dict_values == {}
        assert spec.with_dict_value("a", 1).dict_values == {"a": 1}
        assert (
            spec.with_dict_values({}).with_dict_value("a", 1, _if=False).dict_values
            == {}
        )

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
            "_if",
        }

        assert spec.transform_dict_values(lambda x: {"a": 2}).dict_values == {"a": 2}
        assert spec.transform_dict_value("a", lambda x: x + 1).dict_values == {"a": 2}
        assert spec.transform_dict_value(
            "a", lambda x: x + 1, _if=False
        ).dict_values == {"a": 1}

    def test_without(self, spec_cls):
        spec = spec_cls(dict_values={"a": 1})
        assert set(
            inspect.Signature.from_callable(spec.without_dict_value).parameters
        ) == {
            "_key",
            "_inplace",
            "_if",
        }

        assert spec.without_dict_value("a").dict_values == {}
        assert spec.without_dict_value("a", _if=False).dict_values == {"a": 1}


class TestSpecDictAttribute:
    def test_with(self, spec_cls, unkeyed_spec_cls, keyed_spec_cls):

        spec = spec_cls()
        assert set(
            inspect.Signature.from_callable(spec.with_spec_dict_item).parameters
        ) == {
            "_key",
            "_value",
            "_inplace",
            "_if",
            "nested_scalar",
            "nested_scalar2",
        }

        # Constructors
        assert "spec_dict_items" not in spec.__dict__
        unkeyed = unkeyed_spec_cls()
        assert spec.with_spec_dict_item("a", unkeyed).spec_dict_items["a"] is unkeyed
        assert isinstance(
            spec.with_spec_dict_item("a").spec_dict_items["a"], unkeyed_spec_cls
        )
        assert (
            spec.with_spec_dict_item("a", {"nested_scalar": 10})
            .spec_dict_items["a"]
            .nested_scalar
            == 10
        )

        # Insert
        assert spec.with_spec_dict_item("a", unkeyed).with_spec_dict_item(
            "b", nested_scalar=3
        ).spec_dict_items == {"a": unkeyed, "b": unkeyed_spec_cls(nested_scalar=3)}
        assert spec.with_spec_dict_item("a", unkeyed).with_spec_dict_item(
            "a", nested_scalar=3
        ).spec_dict_items == {"a": unkeyed_spec_cls(nested_scalar=3)}

        # Test keyed spec classes
        assert spec.with_keyed_spec_dict_item("a", "a").keyed_spec_dict_items == {
            "a": keyed_spec_cls("a")
        }
        assert spec.with_keyed_spec_dict_item(
            "a", "a", nested_scalar=10
        ).keyed_spec_dict_items == {"a": keyed_spec_cls("a", nested_scalar=10)}
        assert spec.with_keyed_spec_dict_item("a").keyed_spec_dict_items == {
            "a": keyed_spec_cls()
        }

    def test_update(self, spec_cls, unkeyed_spec_cls):
        spec = spec_cls(
            spec_dict_items={
                "a": unkeyed_spec_cls(nested_scalar=1),
                "b": unkeyed_spec_cls(nested_scalar=2),
            }
        )
        assert set(
            inspect.Signature.from_callable(spec.update_spec_dict_item).parameters
        ) == {
            "_key",
            "_new_item",
            "_inplace",
            "_if",
            "nested_scalar",
            "nested_scalar2",
        }

        assert spec.update_spec_dict_item("a") is not spec
        assert spec.update_spec_dict_item("a").spec_dict_items["a"].nested_scalar == 1
        assert (
            spec.update_spec_dict_item("a", nested_scalar=10)
            .spec_dict_items["a"]
            .nested_scalar
            == 10
        )
        assert (
            spec.update_spec_dict_item("a", nested_scalar=10, _if=False)
            .spec_dict_items["a"]
            .nested_scalar
            == 1
        )

        # Check that new items are not created when missing
        with pytest.raises(KeyError):
            spec.update_spec_dict_item("d")

    def test_transform(self, spec_cls, unkeyed_spec_cls):

        spec = spec_cls(
            spec_dict_items={
                "a": unkeyed_spec_cls(nested_scalar=1),
                "b": unkeyed_spec_cls(nested_scalar=2),
            }
        )
        assert set(
            inspect.Signature.from_callable(spec.transform_spec_dict_item).parameters
        ) == {
            "_key",
            "_transform",
            "_inplace",
            "nested_scalar",
            "nested_scalar2",
            "_if",
        }

        # scalar form
        assert spec.transform_spec_dict_items(lambda x: {}).spec_dict_items == {}

        # by value
        assert spec.transform_spec_dict_item(
            "a", lambda x: x.with_nested_scalar(3)
        ).spec_dict_items == {
            "a": unkeyed_spec_cls(nested_scalar=3),
            "b": unkeyed_spec_cls(nested_scalar=2),
        }
        assert spec.transform_spec_dict_item(
            "a", nested_scalar=lambda x: 3
        ).spec_dict_items == {
            "a": unkeyed_spec_cls(nested_scalar=3),
            "b": unkeyed_spec_cls(nested_scalar=2),
        }

        # Check missing
        with pytest.raises(KeyError):
            spec.transform_spec_dict_item("c", nested_scalar=lambda x: 3)

    def test_without(self, spec_cls, unkeyed_spec_cls):

        spec = spec_cls(
            spec_dict_items={
                "a": unkeyed_spec_cls(nested_scalar=1),
                "b": unkeyed_spec_cls(nested_scalar=2),
            }
        )
        assert set(
            inspect.Signature.from_callable(spec.without_spec_dict_item).parameters
        ) == {
            "_key",
            "_inplace",
            "_if",
        }

        assert spec.without_spec_dict_item("a").spec_dict_items == {
            "b": unkeyed_spec_cls(nested_scalar=2)
        }
