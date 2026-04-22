"""Tests for the spec_classes.mypy plugin.

Each test calls mypy programmatically with the plugin enabled and asserts on
the error output.  The helper `mypy_errors` strips location prefixes so tests
only assert on the message text and error code.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

try:
    from mypy.api import run as mypy_run
except ImportError:
    pytest.skip("mypy not installed", allow_module_level=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLUGIN_INI = "[mypy]\nplugins = spec_classes.mypy_plugin\n"
_MYPY_CACHE = Path(__file__).parent / ".mypy_plugin_cache"


def mypy_errors(source: str) -> list[str]:
    """Run mypy on *source* with the plugin and return a list of error lines.

    Each entry has the form ``"<message>  [<code>]"``, with the file/line
    prefix stripped so tests are not fragile.
    """
    ini = Path(__file__).parent / "_mypy_plugin_test.ini"
    ini.write_text(_PLUGIN_INI)
    try:
        stdout, _stderr, _rc = mypy_run(
            [
                "--no-error-summary",
                "--show-error-codes",
                "--no-strict-optional",
                "--config-file",
                str(ini),
                "--cache-dir",
                str(_MYPY_CACHE),
                "-c",
                textwrap.dedent(source),
            ]
        )
    finally:
        ini.unlink(missing_ok=True)

    errors = []
    for line in stdout.splitlines():
        # Drop "<stdin>:NN: error: " / note: prefixes; keep message + code
        if ": error: " in line:
            errors.append(line.split(": error: ", 1)[1])
        elif ": note: " in line:
            pass  # ignore notes
    return errors


# ---------------------------------------------------------------------------
# __init__ semantics
# ---------------------------------------------------------------------------


class TestInit:
    def test_all_attrs_optional(self) -> None:
        """All non-key attributes should be keyword-only optional."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int
                y: str

            Foo()           # OK: all optional
            Foo(x=1)        # OK: partial
            Foo(x=1, y="a") # OK: all provided
            """
        )
        assert errors == [], errors

    def test_key_attr_positional_required(self) -> None:
        """Key attribute without a default must be provided positionally."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class(key="id")
            class Foo:
                id: str
                x: int

            Foo("hello")       # OK: key positional
            Foo(id="hello")    # OK: key as keyword
            Foo()              # Error: missing id
            """
        )
        assert len(errors) == 1
        assert "Missing positional argument" in errors[0] or "call-arg" in errors[0]

    def test_key_attr_optional_when_has_default(self) -> None:
        """Key attribute with a default should be optional."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class(key="id")
            class Foo:
                id: str = "default"
                x: int

            Foo()             # OK: key has default
            Foo("explicit")   # OK: key positional
            """
        )
        assert errors == [], errors

    def test_non_key_attrs_are_keyword_only(self) -> None:
        """Non-key attributes cannot be passed positionally."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int
                y: str

            Foo(1, "a")  # Error: positional args not allowed for non-key attrs
            """
        )
        assert len(errors) >= 1

    def test_attrs_with_defaults_can_come_before_without(self) -> None:
        """Attrs with defaults may be declared before attrs without (keyword-only)."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int = 0   # has default
                y: str       # no default - fine in spec_class, error in dataclass

            Foo(y="hello")   # OK
            """
        )
        assert errors == [], errors

    def test_init_false_attr_excluded(self) -> None:
        """Attributes with Attr(init=False) should not appear in __init__."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class, Attr

            @spec_class
            class Foo:
                x: int
                y: str = Attr(init=False, default="hidden")

            Foo(x=1, y="oops")  # Error: y not in __init__
            """
        )
        assert any(
            "Unexpected keyword argument" in e
            or "no parameter named" in e.lower()
            or "call-arg" in e
            for e in errors
        )

    def test_inherited_attrs_in_child_init(self) -> None:
        """Child spec-class __init__ should include inherited attrs."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Parent:
                x: int

            @spec_class
            class Child(Parent):
                y: str

            Child(x=1, y="hello")  # OK: both attrs accessible
            Child(x=1)             # OK: y optional
            """
        )
        assert errors == [], errors


# ---------------------------------------------------------------------------
# Scalar methods
# ---------------------------------------------------------------------------


class TestScalarMethods:
    def test_with_attr_returns_self(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            result: Foo = f.with_x(1)  # OK
            """
        )
        assert errors == [], errors

    def test_with_attr_wrong_return_type(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            result: int = f.with_x(1)  # Error: returns Foo not int
            """
        )
        assert len(errors) == 1
        assert "assignment" in errors[0]

    def test_with_attr_wrong_arg_type(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            f.with_x("not_an_int")  # Error: str not int
            """
        )
        assert len(errors) == 1
        assert "arg-type" in errors[0]

    def test_update_attr_exists(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            result: Foo = f.update_x(1)  # OK
            """
        )
        assert errors == [], errors

    def test_transform_attr_callable(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            result: Foo = f.transform_x(lambda v: v + 1)  # OK
            """
        )
        assert errors == [], errors

    def test_transform_attr_wrong_callable_type(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            f.transform_x("not_a_callable")  # Error
            """
        )
        assert len(errors) >= 1

    def test_reset_attr_exists(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            result: Foo = f.reset_x()  # OK
            """
        )
        assert errors == [], errors

    def test_nested_spec_class_kwargs(self) -> None:
        """with_<attr> for a spec-class-typed attr should accept nested attrs."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Inner:
                a: int
                b: str

            @spec_class
            class Outer:
                inner: Inner

            o = Outer()
            o.with_inner(Inner())        # OK: pass full value
            o.with_inner(a=1, b="x")    # OK: nested kwargs
            o.with_inner(a=1)           # OK: partial nested kwargs
            """
        )
        assert errors == [], errors

    def test_inplace_and_if_params(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            f.with_x(1, _inplace=True)   # OK
            f.with_x(1, _if=False)        # OK
            """
        )
        assert errors == [], errors


# ---------------------------------------------------------------------------
# Inheritance and Self return type
# ---------------------------------------------------------------------------


class TestInheritance:
    def test_inherited_method_narrows_to_child(self) -> None:
        """with_x on a Child instance should return Child, not Parent."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Parent:
                x: int

            @spec_class
            class Child(Parent):
                y: str

            c: Child = Child()
            result: Child = c.with_x(1)  # OK: TypeVar unifies to Child
            """
        )
        assert errors == [], errors

    def test_parent_method_returns_parent(self) -> None:
        """with_x on a Parent instance returns Parent, not Child."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Parent:
                x: int

            @spec_class
            class Child(Parent):
                y: str

            p: Parent = Parent()
            result: Child = p.with_x(1)  # Error: returns Parent not Child
            """
        )
        assert len(errors) == 1
        assert "assignment" in errors[0]

    def test_child_own_attr_method(self) -> None:
        """Child's own attribute gets its method."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Parent:
                x: int

            @spec_class
            class Child(Parent):
                y: str

            c: Child = Child()
            result: Child = c.with_y("hello")  # OK
            """
        )
        assert errors == [], errors

    def test_no_lsp_override_errors(self) -> None:
        """Inheriting spec-class should not cause LSP override errors."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class A:
                x: int

            @spec_class
            class B(A):
                y: str

            @spec_class
            class C(B):
                z: float
            """
        )
        assert errors == [], errors


# ---------------------------------------------------------------------------
# Collection methods
# ---------------------------------------------------------------------------


class TestCollectionMethods:
    def test_list_with_item(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                items: list[int]

            f = Foo()
            result: Foo = f.with_item(5)          # OK
            result2: Foo = f.with_item(5, _index=0)  # OK
            """
        )
        assert errors == [], errors

    def test_list_wrong_item_type(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                items: list[int]

            f = Foo()
            f.with_item("not_an_int")  # Error
            """
        )
        assert len(errors) >= 1
        assert "arg-type" in errors[0]

    def test_list_update_item(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                items: list[int]

            f = Foo()
            result: Foo = f.update_item(0, 99)  # OK: index, new_value
            """
        )
        assert errors == [], errors

    def test_list_without_item(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                items: list[int]

            f = Foo()
            result: Foo = f.without_item(5)  # OK
            """
        )
        assert errors == [], errors

    def test_dict_with_item_required_key(self) -> None:
        """For dict collections, the key arg is required (no default)."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                tags: dict[str, int]

            f = Foo()
            f.with_tag("k", 1)    # OK
            f.with_tag("k")       # OK: value optional
            f.with_tag()          # Error: key required
            """
        )
        assert len(errors) == 1
        assert "call-arg" in errors[0] or "Missing" in errors[0]

    def test_dict_key_type_checked(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                tags: dict[str, int]

            f = Foo()
            f.with_tag(42, 1)  # Error: key must be str
            """
        )
        assert len(errors) >= 1
        assert "arg-type" in errors[0]

    def test_dict_without_item(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                tags: dict[str, int]

            f = Foo()
            result: Foo = f.without_tag("k")  # OK
            """
        )
        assert errors == [], errors

    def test_set_with_item(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                labels: set[str]

            f = Foo()
            result: Foo = f.with_label("hello")  # OK
            """
        )
        assert errors == [], errors

    def test_set_without_item(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                labels: set[str]

            f = Foo()
            result: Foo = f.without_label("hello")  # OK
            """
        )
        assert errors == [], errors


# ---------------------------------------------------------------------------
# Top-level methods
# ---------------------------------------------------------------------------


class TestToplevelMethods:
    def test_update_returns_self(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            result: Foo = f.update(x=1)  # OK
            """
        )
        assert errors == [], errors

    def test_transform_returns_self(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            result: Foo = f.transform(lambda o: o)  # OK
            """
        )
        assert errors == [], errors

    def test_reset_returns_self(self) -> None:
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

            f = Foo()
            result: Foo = f.reset()  # OK
            """
        )
        assert errors == [], errors

    def test_toplevel_inherited_by_child(self) -> None:
        """Child should inherit top-level methods from parent spec-class."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Parent:
                x: int

            @spec_class
            class Child(Parent):
                y: str

            c: Child = Child()
            result: Child = c.reset()    # OK: inherited, returns Child via TypeVar
            result2: Child = c.update(x=1)  # OK
            """
        )
        assert errors == [], errors


# ---------------------------------------------------------------------------
# _prepare_* methods
# ---------------------------------------------------------------------------


class TestPreparers:
    def test_attr_preparer_widens_input_to_any(self) -> None:
        """with_<attr> / update_<attr> should accept Any when _prepare_<attr> exists."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

                def _prepare_x(self, value: object) -> int:
                    return 0

            f = Foo()
            f.with_x("not_an_int")   # OK: preparer accepts anything
            f.with_x([1, 2, 3])      # OK: preparer accepts anything
            f.update_x("hello")      # OK: preparer accepts anything
            """
        )
        assert errors == [], errors

    def test_attr_preparer_bad_return_type_flagged(self) -> None:
        """_prepare_<attr> with a return type incompatible with the attr should error."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

                def _prepare_x(self, value: object) -> str:  # wrong: should return int
                    return str(value)
            """
        )
        assert len(errors) == 1
        assert "preparer" in errors[0].lower() or "incompatible" in errors[0].lower()

    def test_attr_preparer_any_return_skips_check(self) -> None:
        """_prepare_<attr> returning Any should not produce an error."""
        errors = mypy_errors(
            """
            from typing import Any
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int

                def _prepare_x(self, value: object) -> Any:
                    return value
            """
        )
        assert errors == [], errors

    def test_item_preparer_widens_collection_input(self) -> None:
        """with_<item> should accept Any when _prepare_<item> exists."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                items: list[int]

                def _prepare_item(self, value: object) -> int:
                    return 0

            f = Foo()
            f.with_item("42")    # OK: item preparer accepts anything
            f.with_item(3.14)    # OK
            f.update_item(0, "99")  # OK: _new_item also widened
            """
        )
        assert errors == [], errors

    def test_item_preparer_bad_return_type_flagged(self) -> None:
        """_prepare_<item> returning a type incompatible with item type should error."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                items: list[int]

                def _prepare_item(self, value: object) -> str:  # wrong: should return int
                    return str(value)
            """
        )
        assert len(errors) == 1
        assert "preparer" in errors[0].lower() or "incompatible" in errors[0].lower()

    def test_no_preparer_keeps_strict_types(self) -> None:
        """Without a preparer the original strict type is still enforced."""
        errors = mypy_errors(
            """
            from spec_classes import spec_class

            @spec_class
            class Foo:
                x: int
                items: list[int]

            f = Foo()
            f.with_x("oops")     # Error: no preparer
            f.with_item("oops")  # Error: no item preparer
            """
        )
        assert len(errors) == 2
        assert all("arg-type" in e for e in errors)
