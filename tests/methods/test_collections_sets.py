import inspect

import pytest


class TestSetAttribute:
    def test_with(self, spec_cls):

        spec = spec_cls()
        assert set(inspect.Signature.from_callable(spec.with_set_value).parameters) == {
            "_item",
            "_inplace",
            "_if",
        }

        # constructors
        assert "set_values" not in spec.__dict__
        assert spec.with_set_values().set_values == set()
        assert spec.with_set_value("a").set_values == {"a"}
        assert spec.with_set_values().with_set_value("a", _if=False).set_values == set()

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
            match="Attempted to add an invalid item `1` to `Spec.set_values`. Expected item of type `str`.",
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
            "_if",
        }

        assert spec.transform_set_values(lambda x: x | {"c"}).set_values == {
            "a",
            "b",
            "c",
        }
        assert spec.transform_set_value("a", lambda x: "c").set_values == {"b", "c"}
        assert spec.transform_set_value("a", lambda x: "c", _if=False).set_values == {
            "a",
            "b",
        }

        with pytest.raises(ValueError):
            assert spec.transform_set_value("c", lambda x: "c")

    def test_without(self, spec_cls):
        spec = spec_cls(set_values={"a", "b"})
        assert set(
            inspect.Signature.from_callable(spec.without_set_value).parameters
        ) == {
            "_item",
            "_inplace",
            "_if",
        }

        assert spec.without_set_value("a").set_values == {"b"}
        assert spec.without_set_value("a", _if=False).set_values == {"a", "b"}


class TestSpecSetAttribute:
    def test_with(self, spec_cls, keyed_spec_cls):

        spec = spec_cls()
        assert set(
            inspect.Signature.from_callable(spec.with_keyed_spec_set_item).parameters
        ) == {
            "_item",
            "_inplace",
            "_if",
            "key",
            "nested_scalar",
            "nested_scalar2",
        }

        # Constructors
        assert "spec_dict_items" not in spec.__dict__
        keyed = keyed_spec_cls()
        assert keyed in spec.with_keyed_spec_set_item(keyed).keyed_spec_set_items

        # Insert
        assert sorted(
            spec.with_keyed_spec_set_item(keyed)
            .with_keyed_spec_set_item("b", nested_scalar=3)
            .keyed_spec_set_items,
            key=lambda x: x.key,
        ) == [keyed_spec_cls("b", nested_scalar=3), keyed]
        assert sorted(
            spec.with_keyed_spec_set_item("b", nested_scalar=3)
            .with_keyed_spec_set_item("b", nested_scalar=10)
            .keyed_spec_set_items,
            key=lambda x: x.key,
        ) == [keyed_spec_cls("b", nested_scalar=10)]

    def test_update(self, spec_cls, keyed_spec_cls):
        spec = spec_cls(
            keyed_spec_set_items=[keyed_spec_cls("a"), keyed_spec_cls("b")],
        )
        assert set(
            inspect.Signature.from_callable(spec.update_keyed_spec_set_item).parameters
        ) == {
            "_item",
            "_new_item",
            "_inplace",
            "_if",
            "key",
            "nested_scalar",
            "nested_scalar2",
        }

        a = keyed_spec_cls("a")

        assert spec.update_keyed_spec_set_item(a) is not spec
        assert (
            spec.update_keyed_spec_set_item(a).keyed_spec_set_items[a].nested_scalar
            == 1
        )
        assert (
            spec.update_keyed_spec_set_item("a", keyed_spec_cls("c"))
            .keyed_spec_set_items["c"]
            .key
            == "c"
        )
        assert (
            spec.update_keyed_spec_set_item(a, keyed_spec_cls("c"))
            .keyed_spec_set_items["c"]
            .key
            == "c"
        )
        with pytest.raises(KeyError):
            spec.update_keyed_spec_set_item(
                "a", keyed_spec_cls("c")
            ).keyed_spec_set_items["a"]
        spec.update_keyed_spec_set_item("a", nested_scalar=100).keyed_spec_set_items[
            "a"
        ].nested_scalar == 100
        spec.update_keyed_spec_set_item(
            "a", nested_scalar=100, _if=False
        ).keyed_spec_set_items["a"].nested_scalar == 1

        # Check that mutations in key work fine
        assert set(
            spec.update_keyed_spec_set_item("b", key="c").keyed_spec_set_items.keys()
        ) == {"a", "c"}

        # Check that new items are not created when missing
        with pytest.raises(ValueError):
            spec.update_keyed_spec_set_item("c")
        with pytest.raises(ValueError):
            spec.update_keyed_spec_set_item(keyed_spec_cls("c"))

    # The rest of the set-container behavior is covered already in `keyed_spec_cls`
    # tests and in `TestSetAttribute`.
