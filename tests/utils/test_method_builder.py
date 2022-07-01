import inspect
import re
import textwrap
from inspect import Parameter, Signature
from typing import Tuple

import pytest

from spec_classes.utils.method_builder import MethodBuilder


class TestMethodBuilder:
    def test_with_arg(self):
        m = MethodBuilder("basic_wrapper", None)
        m.with_arg("a", desc="A value.")

        assert len(m.method_args) == 2
        assert m.method_args[0].name == "self"
        assert m.method_args[1].name == "a"

        m.with_arg("c", desc="Another value.", kind="keyword_only", virtual=True)

        assert len(m.method_args) == 3
        assert m.method_args[2].name == "kwargs"
        assert m.method_args[2].kind == Parameter.VAR_KEYWORD
        assert len(m.method_args_virtual) == 1
        assert m.method_args_virtual[0].kind == Parameter.KEYWORD_ONLY

        m.with_arg("d", desc="Another value.", only_if=False)
        assert len(m.method_args) == 3

        with pytest.raises(
            RuntimeError,
            match=re.escape(
                "Virtual arguments can only be `KEYWORD_ONLY` or `VAR_KEYWORD`, not `POSITIONAL_OR_KEYWORD`."
            ),
        ):
            m.with_arg("d", desc="Another value.", virtual=True)

        with pytest.raises(
            RuntimeError,
            match=re.escape(
                "Arguments of kind `POSITIONAL_OR_KEYWORD` cannot be added after `VAR_KEYWORD` arguments."
            ),
        ):
            m.with_arg("d", desc="Another value.")

        with pytest.raises(
            RuntimeError,
            match=re.escape(
                "Arguments of kind `POSITIONAL_ONLY` cannot be added after `VAR_KEYWORD` arguments."
            ),
        ):
            m.with_arg("d", desc="Another value.", kind="positional_only")

        m.with_arg("e", desc="Collect all.", kind="var_keyword", virtual=True)

        with pytest.raises(
            RuntimeError,
            match=re.escape(
                "Virtual arguments of kind `KEYWORD_ONLY` cannot be added after `VAR_KEYWORD` arguments."
            ),
        ):
            m.with_arg("f", desc="Another value.", virtual=True, kind="keyword_only")

    def test_with_args(self):
        m = MethodBuilder("basic_wrapper", None)
        m.with_args({"a": "A value."})
        m.with_args(["b"])

        assert len(m.method_args) == 3
        assert m.method_args[0].name == "self"
        assert m.method_args[1].name == "a"
        assert m.method_args[2].name == "b"

        m.with_args({"c": "Another value."}, only_if=False)
        assert len(m.method_args) == 3

        with pytest.raises(
            RuntimeError,
            match=re.escape("Method already has some incoming arguments: {'a'}"),
        ):
            m.with_args({"a": "A value."})

    def test_with_spec_attrs_for(self):
        from spec_classes import spec_class

        @spec_class(init_overflow_attr="overflow")
        class Spec:
            a: int
            b: float

        m = MethodBuilder("basic_wrapper", None).with_spec_attrs_for(Spec)

        assert len(m.method_args) == 2
        assert len(m.method_args_virtual) == 3
        assert {arg.name for arg in m.method_args_virtual} == {"a", "b", "overflow"}

        m = MethodBuilder("basic_wrapper", None).with_spec_attrs_for(
            Spec, only_if=False
        )

        assert len(m.method_args_virtual) == 0

    def test_with_returns(self):
        m = MethodBuilder("basic_wrapper", None)

        m.with_returns("A value", annotation=str)
        assert m.doc_returns == "A value"
        assert m.method_return_type is str

        m.with_returns("A different value", annotation=int, only_if=False)
        assert m.doc_returns == "A value"
        assert m.method_return_type is str

    def test_with_preamble(self):
        m = MethodBuilder("basic_wrapper", None)

        m.with_preamble("A value")
        assert m.doc_preamble == "A value"

        m.with_preamble("A different value", only_if=False)
        assert m.doc_preamble == "A value"

    def test_with_notes(self):
        m = MethodBuilder("basic_wrapper", None)

        m.with_notes("A note", "Another note")
        assert m.doc_notes == ["A note", "Another note"]

        m.with_notes("Anecdote", only_if=False)
        assert m.doc_notes == ["A note", "Another note"]

    def test_build(self):
        def basic_implementation(self, a, b, **kwargs):
            return (a, b, kwargs)

        m = MethodBuilder("basic_wrapper", basic_implementation)
        m.with_preamble("Hello World!")
        m.with_returns("All the arguments.", annotation=Tuple)
        m.with_notes("This method doesn't do a whole lot.")
        m.with_arg("a", desc="A value.", annotation=int)

        with pytest.raises(
            RuntimeError,
            match=re.escape(
                "Proposed method signature `basic_wrapper(self, a: int)` is not compatible with implementation signature `implementation(self, a, b, **kwargs)`"
            ),
        ):
            m.build()

        m.with_arg("b", desc="Another value.", annotation=str)
        m.with_arg(
            "c",
            desc="Yet another value.",
            annotation=float,
            virtual=True,
            kind="keyword_only",
        )

        c = m.build()

        assert (
            c.__doc__
            == textwrap.dedent(
                """
            Hello World!

            Args:
                a: A value.
                b: Another value.
                c: Yet another value.

            Returns:
                All the arguments.

            Notes:
                This method doesn't do a whole lot.
        """
            ).strip()
        )
        assert str(inspect.signature(c)) == "(self, a: int, b: str, *, c: float)"
        assert c(None, 1, "two", c=3.0) == (1, "two", {"c": 3.0})
        with pytest.raises(
            TypeError,
            match=re.escape("basic_wrapper() got unexpected keyword arguments: {'d'}."),
        ):
            c(None, 1, "two", c=3.0, d=None)

    def test__check_signature_compatible_with_implementation(self):
        assert MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda x: None),
            inspect.signature(lambda x: None),
        )
        assert MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda x: None),
            inspect.signature(lambda *x: None),
        )
        assert MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda *x: None),
            inspect.signature(lambda *x: None),
        )
        assert not MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda *x: None),
            inspect.signature(lambda x: None),
        )
        assert MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda x, y: None),
            inspect.signature(lambda x, y: None),
        )
        assert MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda y, x: None),
            inspect.signature(lambda x, y: None),
        )
        assert MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda x: None),
            inspect.signature(lambda x, y=False: None),
        )
        assert MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda x, y: None),
            inspect.signature(lambda x, y=False: None),
        )
        assert MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda x, y: None),
            inspect.signature(lambda x, **y: None),
        )
        assert not MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda x, **y: None),
            inspect.signature(lambda x, y: None),
        )
        assert MethodBuilder._check_signature_compatible_with_implementation(
            inspect.signature(lambda x, **y: None),
            inspect.signature(lambda x, **y: None),
        )

    def test__method_signature_to_definition_str(self):
        assert MethodBuilder._method_signature_to_definition_str(
            Signature(
                [
                    Parameter("a", kind=Parameter.POSITIONAL_ONLY),
                    Parameter("b", kind=Parameter.POSITIONAL_OR_KEYWORD),
                    Parameter("c", kind=Parameter.VAR_POSITIONAL),
                    Parameter("d", kind=Parameter.KEYWORD_ONLY, default=None),
                    Parameter("e", kind=Parameter.VAR_KEYWORD),
                ]
            )
        ) == ('(a, b, *c, d=DEFAULTS["d"], **e)', {"d": None})

    def test__method_signature_to_implementation_call(self):
        assert (
            MethodBuilder._method_signature_to_implementation_call(
                Signature(
                    [
                        Parameter("a", kind=Parameter.POSITIONAL_ONLY),
                        Parameter("b", kind=Parameter.POSITIONAL_OR_KEYWORD),
                        Parameter("c", kind=Parameter.VAR_POSITIONAL),
                        Parameter("d", kind=Parameter.KEYWORD_ONLY, default=None),
                        Parameter("e", kind=Parameter.VAR_KEYWORD),
                    ]
                )
            )
            == "a, b=b, *c, d=d, **e"
        )
