from __future__ import annotations

import inspect
import textwrap
from inspect import Parameter, Signature, cleandoc
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from spec_classes.types import MISSING
from spec_classes.utils.type_checking import type_label


class MethodBuilder:
    """
    Build a user-friendly wrapper around a callable implementation.

    Methods built using this buiilder are:
    - documented
    - annotated
    - potentially more restrictive than the underlying callable (for example
        perhaps certain attributes cannot be passed).

    Within spec-classes this builder is used to generate all helper methods,
    so that users can introspect the method using `help` (or other tools)
    and get useful information.

    After the specification is completed by the various `.with_*()` methods, you
    should call `.build()` to assemble the method and retrieve the function
    handle.

    Attributes:
        Passable via constructor:
            name: The name of the method being built.
            implementation: The underlying callable around which the method is being
                built.

        Populated via builder methods:
            doc_preamble: The preamble in the documentation string (to which
                argument documentation will be appended).
            doc_args: The docstrings for each argument to the method being
                built (in the order they were added).
            doc_returns: A string description of the value returned by the
                method being built.
            doc_notes: Any additional strings to be appended as notes in the
                methods docstring.
            method_args: A list of `Parameters` for the method signature.
            method_args_virtual: A list of "virtual" `Parameters` for the method
                signature (see notes below).
            method_return_type: The return type of the method being built.

    Notes:
        - "virtual" arguments are arguments that are not directly encoded into
            the generated method's signature, but which should appear in the
            user-facing advertised signature. Under the hood these are fed into
            the method via `**kwargs`. These are useful when you don't want
            attrs to be present in the `**kwargs` of an implementation unless
            the user has explicitly passed them. Also note that default values
            for virtual arguments are only for documentation purposes, and are
            not passed on to the underlying implementation. For this reason they
            should not be populated or corresponding to underlying defaults.

    """

    def __init__(self, name: str, implementation: Callable):
        self.name = name
        self.implementation = implementation

        # Documentation attributes
        self.doc_preamble: str = ""
        self.doc_args: List[str] = []
        self.doc_returns: str = ""
        self.doc_notes: List[str] = []

        # Method signature
        self.method_args: List[Parameter] = [
            Parameter("self", Parameter.POSITIONAL_OR_KEYWORD)
        ]
        self.method_args_virtual: List[Parameter] = []
        self.method_return_type: Optional[Type] = None

        self.check_attrs_match_sig = (  # TODO: Remove this
            True  # This is toggled if signature contains a var_kwarg parameter.
        )

    # Signature related methods

    def with_arg(
        self,
        name: str,
        *,
        desc: str,
        annotation: Type = Parameter.empty,
        default: Any = Parameter.empty,
        kind: Union[str, inspect._ParameterKind] = Parameter.POSITIONAL_OR_KEYWORD,
        virtual: bool = False,
        only_if: bool = True,
    ) -> MethodBuilder:
        """
        Append an argument to the method wrapper. The kind of the argument must
        make sense given the arguments already in the method (e.g. `VAR_KEYWORD`
        attributes should come after all other arguments, etc).

        Args:
            name: The name of the argument.
            desc: A description for the argument (will be added to the method
                docstring).
            annotation: An (optional) type for the argument.
            default: A default value for the argument (optional unless `kind`
                is `KEYWORD_ONLY`.
            kind: The kind of argument. For convenience you can pass a string
                here instead of the enum value. Options are: 'positional_only',
                'positional_or_keyword', 'var_positional', 'keyword_only',
                and 'var_keyword'. Note that virtual arguments can only be
                'keyword_only' and 'var_keyword'.
            virtual: Whether the arguments should be compiled into the method
                (False), or simulated via **kwargs under the hood (True). This
                is useful when you do not want the argument appearing in the
                underlying implementation's `**kwargs` argument unless manually
                supplied by the user.
            only_if: If `False`, this method is a no-op.

        Returns:
            A reference to this `MethodBuilder`.
        """
        if not only_if:
            return self

        if isinstance(kind, str):
            kind = inspect._ParameterKind[kind.upper()]

        # Runtime checks
        if virtual:
            if kind not in (Parameter.VAR_KEYWORD, Parameter.KEYWORD_ONLY):
                raise RuntimeError(
                    f"Virtual arguments can only be `KEYWORD_ONLY` or `VAR_KEYWORD`, not `{kind.name}`."
                )
            if self.method_args_virtual and self.method_args_virtual[
                -1
            ].kind.value > min(kind.value, Parameter.KEYWORD_ONLY.value):
                raise RuntimeError(
                    f"Virtual arguments of kind `{kind.name}` cannot be added after `{self.method_args_virtual[-1].kind.name}` arguments."
                )
        elif self.method_args and self.method_args[-1].kind.value > min(
            kind.value, Parameter.KEYWORD_ONLY.value
        ):
            raise RuntimeError(
                f"Arguments of kind `{kind.name}` cannot be added after `{self.method_args[-1].kind.name}` arguments."
            )

        self.doc_args.append(
            "\n".join(
                textwrap.wrap(
                    f"{name}: {desc or 'Undocumented argument.'}",
                    subsequent_indent="    ",
                )
            )
        )

        # If this is the first virtual argument, append a `kwargs` non-virtual argument to collect these virtual arguments.
        if virtual and not self.method_args_virtual:
            self.method_args.append(Parameter("kwargs", kind=Parameter.VAR_KEYWORD))

        (self.method_args_virtual if virtual else self.method_args).append(
            Parameter(
                name,
                kind=kind,
                default=default,
                annotation=annotation,
            )
        )

        if virtual and kind is Parameter.VAR_KEYWORD:
            self.check_attrs_match_sig = False

        return self

    def with_args(
        self,
        args: Union[List[str], Dict[str, str]],
        *,
        annotations: Optional[Dict[str, Type]] = None,
        defaults: Optional[Dict[str, Any]] = None,
        virtual: bool = False,
        only_if: bool = True,
    ) -> MethodBuilder:
        """
        Append multiple arguments at once to the method wrapper. This is a
        convenience wrapper only, and just makes out calls to `with_arg`. All
        arguments are assumed to be of kind `KEYWORD_ONLY`.

        Args:
            args: A list of argument names, or a mapping of argument names to
                descriptions.
            annotations: An optional mapping from argument name to annotation
                for that argument.
            defaults: An optional mapping from argument name to default values.
            kind: The kind of argument. For convenience you can pass a string
                here instead of the enum value. Options are: 'positional_only',
                'positional_or_keyword', 'var_positional', 'keyword_only',
                and 'var_keyword'. Note that virtual arguments can only be
                'keyword_only' and 'var_keyword'.
            virtual: Whether the arguments should be compiled into the method
                (False), or simulated via **kwargs under the hood (True). This
                is useful when you do not want the argument appearing in the
                underlying implementation's `**kwargs` argument unless manually
                supplied by the user.
            only_if: If `False`, this method is a no-op.

        Returns:
            A reference to this `MethodBuilder`.
        """
        if not only_if or not args:
            return self

        # Remove any arguments that already exist in the function signature.
        duplicate_args = {
            *(arg.name for arg in self.method_args),
            *(arg.name for arg in self.method_args_virtual),
        }.intersection(args)
        if duplicate_args:
            raise RuntimeError(
                f"Method already has some incoming arguments: {duplicate_args}"
            )

        # Cast to a dictionary so we only have to deal with one format.
        if not isinstance(args, dict):
            args = {arg: None for arg in args}

        defaults = defaults or {}
        for name, desc in args.items():
            self.with_arg(
                name,
                desc=desc,
                annotation=(annotations or {}).get(name, Parameter.empty),
                default=(defaults or {}).get(name, MISSING),
                kind=Parameter.KEYWORD_ONLY,
                virtual=virtual,
            )

        return self

    def with_spec_attrs_for(
        self,
        spec_cls: type,
        *,
        desc_template: Optional[str] = None,
        only_if: bool = True,
    ) -> MethodBuilder:
        """
        Add virtual arguments corresponding to the attributes of a spec-class.
        This uses `.with_args` and `.with_arg` under the hood.

        Args:
            spec_cls: The spec class for which arguments should be added to the
                method (one for each spec-class attribute).
            desc_template: If provided, should be a template with one unnamed
                format parameter `{}` (which will be replaced with the attribute
                name); otherwise the attribute descriptions will be used.
            only_if: If `False`, this method is a no-op.

        Returns:
            A reference to this `MethodBuilder`.
        """
        if not only_if or not hasattr(spec_cls, "__spec_class__"):
            return self

        args = {}
        annotations = {}
        defaults = {}

        current_args = {
            *(arg.name for arg in self.method_args),
            *(arg.name for arg in self.method_args_virtual),
        }

        for attr, attr_spec in spec_cls.__spec_class__.attrs.items():
            if (
                not attr_spec.init
                or attr in current_args
                or attr == spec_cls.__spec_class__.init_overflow_attr
            ):
                continue
            args[attr] = (
                desc_template.format(attr_spec.name)
                if desc_template is not None
                else attr_spec.desc
            )
            annotations[attr] = attr_spec.type
            defaults[attr] = MISSING if attr_spec.is_masked else attr_spec.default

        self.with_args(
            args=args,
            annotations=annotations,
            defaults=defaults,
            virtual=True,
        )

        if spec_cls.__spec_class__.init_overflow_attr:
            attr_spec = spec_cls.__spec_class__.attrs[
                spec_cls.__spec_class__.init_overflow_attr
            ]
            self.with_arg(
                name=attr_spec.name,
                desc=attr_spec.desc,
                annotation=attr_spec.type,
                kind=Parameter.VAR_KEYWORD,
                virtual=True,
            )

        return self

    def with_returns(
        self, desc: str, *, annotation: Type = Parameter.empty, only_if: bool = True
    ) -> MethodBuilder:
        """
        Specify the return type and description of the method being built.

        Args:
            spec_cls: The spec class for which arguments should be added to the
                method (one for each spec-class attribute).
            desc: A description for the returned value (will be added to the
                method docstring).
            annotation: An (optional) type for the returned value.
            only_if: If `False`, this method is a no-op.

        Returns:
            A reference to this `MethodBuilder`.
        """
        if not only_if:
            return self

        self.doc_returns = desc
        self.method_return_type = (
            annotation if annotation is not Parameter.empty else Any
        )

        return self

    # Documentation-only related methods.

    def with_preamble(self, preamble: str, *, only_if: bool = True) -> MethodBuilder:
        """
        Specify the method's documentation preamble.

        Args:
            preamble: The documentation preamble to be prefixed to the generated
                method docstring.
            only_if: If `False`, this method is a no-op.

        Returns:
            A reference to this `MethodBuilder`.
        """
        if not only_if:
            return self

        self.doc_preamble = preamble

        return self

    def with_notes(self, *lines, only_if=True) -> MethodBuilder:
        """
        Specify additional notes to be appended to the method's docstring.

        Args:
            lines: An iterable of additional notes.
            only_if: If `False`, this method is a no-op.

        Returns:
            A reference to this `MethodBuilder`.
        """
        if not only_if:
            return self

        self.doc_notes.extend(
            ["\n".join(textwrap.wrap(line, subsequent_indent="    ")) for line in lines]
        )

        return self

    # Builder and helpers

    def build(self) -> Callable:
        """
        Build the method.

        Returns:
            The generated method.
        """
        namespace = {}

        signature = self._signature
        impl_signature = Signature.from_callable(self.implementation)
        signature_advertised = (
            self._signature_virtual if self.method_args_virtual else signature
        )

        if not self._check_signature_compatible_with_implementation(
            signature, impl_signature
        ):
            raise RuntimeError(
                f"Proposed method signature `{self.name}{signature}` is not compatible with implementation signature `implementation{impl_signature}`."
            )

        VALID_KWARGS = {p.name for p in self.method_args_virtual}

        def validate_attrs(attrs):
            for attr in attrs:
                if attr not in VALID_KWARGS:
                    extra_attrs = set(attrs)
                    extra_attrs.difference_update(VALID_KWARGS)
                    raise TypeError(
                        f"{self.name}() got unexpected keyword arguments: {repr(extra_attrs)}."
                    )

        str_signature, defaults = self._method_signature_to_definition_str(signature)

        exec(
            textwrap.dedent(
                f"""
            from __future__ import annotations
            def {self.name}{str_signature} { '-> ' + repr(type_label(self.method_return_type)) if self.method_return_type is not None else ""}:
                {"validate_attrs(kwargs)" if self.method_args_virtual and self.check_attrs_match_sig else ""}
                return implementation({self._method_signature_to_implementation_call(self._signature)})
        """
            ),
            {
                "implementation": self.implementation,
                "MISSING": MISSING,
                "validate_attrs": validate_attrs,
                "DEFAULTS": defaults,
            },
            namespace,
        )

        method = namespace[self.name]
        method.__doc__ = self._docstring
        method.__signature__ = signature_advertised
        return method

    @property
    def _signature(self) -> Signature:
        """
        The signature to use when building the method. This does not include
        any virtual arguments.
        """
        return Signature(parameters=self.method_args)

    @property
    def _signature_virtual(self) -> Signature:
        """
        The signature to advertise using method.__signature__ on the built method.
        This includes virtual arguments.
        """
        if self.method_args_virtual:
            return Signature(
                parameters=self.method_args[:-1] + self.method_args_virtual
            )
        return (
            self._signature
        )  # pragma: no cover; we avoid this case in the code to running this twice

    @property
    def _docstring(self) -> str:
        """
        The method docstring, as composed from the preamble, arg descs, return
        annotations and notes.
        """
        docstring = ""
        if self.doc_preamble:
            docstring += self.doc_preamble
        if self.doc_args:
            docstring += "\n\nArgs:\n" + textwrap.indent(
                "\n".join(self.doc_args), "    "
            )
        if self.doc_returns:
            docstring += "\n\nReturns:\n" + "\n".join(
                textwrap.wrap(
                    self.doc_returns, initial_indent="    ", subsequent_indent="    "
                )
            )
        if self.doc_notes:
            docstring += "\n\nNotes:\n" + textwrap.indent(
                "\n".join(self.doc_notes), "    "
            )
        return cleandoc(docstring)

    @staticmethod
    def _check_signature_compatible_with_implementation(
        sig_method: Signature, sig_impl: Signature
    ) -> bool:
        """
        Check whether signatures conform to one another, assuming that the fields
        in `sig_method` are going to be passed by position for positional parameters,
        and then by name, to a function with signature `sig_impl`.
        """
        impl_has_var_args = False
        impl_has_var_kwargs = False

        # Check that implementation positional elements have values
        for impl_param in sig_impl.parameters.values():
            if impl_param.kind is Parameter.VAR_POSITIONAL:
                impl_has_var_args = True
            elif impl_param.kind is Parameter.VAR_KEYWORD:
                impl_has_var_kwargs = True
            elif (
                impl_param.kind
                in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
                and impl_param.default is Parameter.empty
                and impl_param.name not in sig_method.parameters
            ):
                return False

        # Check that all method parameters exist on implementation
        for method_param in sig_method.parameters.values():
            if method_param.kind is Parameter.VAR_POSITIONAL:
                if not impl_has_var_args:
                    return False
            elif method_param.kind is Parameter.VAR_KEYWORD:
                if not impl_has_var_kwargs:
                    return False
            elif method_param.name not in sig_impl.parameters:
                if (
                    method_param.kind is Parameter.POSITIONAL_ONLY
                    or not impl_has_var_kwargs
                ):
                    return False  # pragma: no cover; this requires python 3.8 or newer

        return True

    @staticmethod
    def _method_signature_to_definition_str(
        signature: Signature,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Return a string representation of the signature that can be used in exec.
        This string assumes that `DEFAULTS` is available in the evaluation
        namespace, and is the dictionary returned here.
        """
        out = []
        defaults = {}
        done_kw_only = False
        for p in signature.parameters.values():
            if p.kind is Parameter.VAR_POSITIONAL:
                done_kw_only = True
            elif p.kind is Parameter.KEYWORD_ONLY and not done_kw_only:
                done_kw_only = True
                out.append("*")
            param = str(p).split(":", maxsplit=1)[0]
            if p.default is not Parameter.empty:
                param = param.split("=")[0]
                out.append(f'{param}=DEFAULTS["{p.name}"]')
                defaults[p.name] = p.default
            else:
                out.append(param)
        return f'({", ".join(out)})', defaults

    @staticmethod
    def _method_signature_to_implementation_call(signature: Signature) -> str:
        """
        Return a string form "<positional_value>, ..., <field>=<value>, ..."
        """
        out = []
        for name, p in signature.parameters.items():
            if p.kind is inspect.Parameter.POSITIONAL_ONLY:
                out.append(name)
            elif p.kind is inspect.Parameter.VAR_POSITIONAL:
                out.append(f"*{name}")
            elif p.kind is inspect.Parameter.VAR_KEYWORD:
                out.append(f"**{name}")
            else:
                out.append(f"{name}={name}")
        return ", ".join(out)
