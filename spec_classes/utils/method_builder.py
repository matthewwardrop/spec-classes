import inspect
import textwrap
from inspect import cleandoc, Signature, Parameter
from typing import Any, Callable, Dict, Optional, Type, Tuple

from spec_classes.special_types import MISSING


class MethodBuilder:  # pragma: no cover; This is an internal helper class only; so long as `spec_class` works, we are golden!
    """
    Build a method based on its signature, allowing more restrictive wrappers
    to be built around a more general `implementation`, that is replete with
    user documentation and that throws sensible errors when users do the "wrong"
    thing with it.
    """

    def __init__(self, name: str, implementation: Callable):
        self.name = name
        self.implementation = implementation

        self.preamble = ""
        self.args = []
        self.returns = ""
        self.return_type = None
        self.notes = []
        self.parameters = [Parameter("self", Parameter.POSITIONAL_OR_KEYWORD)]
        self.parameters_sig_only = []
        self.check_attrs_match_sig = True  # This is toggled if signature contains a var_kwarg parameter.

    # Signature related methods

    def with_arg(
            self, name: str, desc: str, default: Any = Parameter.empty, keyword_only: bool = False,
            annotation: Type = Parameter.empty, only_if: bool = True
    ):
        """
        Add argument to method.
        """
        if not only_if:
            return self

        self.args.append('\n'.join(textwrap.wrap(f"{name}: {desc}", subsequent_indent='    ')))
        self.parameters.append(Parameter(
            name,
            kind=Parameter.KEYWORD_ONLY if keyword_only else Parameter.POSITIONAL_OR_KEYWORD,
            default=default,
            annotation=annotation,
        ))

        return self

    def with_attrs(self, args: Dict[str, Type], var_kwarg: Optional[str] = None, template: str = "", defaults: Dict[str, Any] = None, only_if: bool = True):
        """
        Add **attrs to signature, and record valid keywords as specified in `args`.
        """
        if not only_if:
            return self

        # Remove any arguments that already exist in the function signature.
        args = args.copy()
        current_sig = self.signature
        for arg in list(args):
            if arg in current_sig.parameters:
                args.pop(arg)

        if not args:
            return self

        self.args.extend([
            "{}: {}".format(name, template.format(name)) for name in list(args)
        ])
        if not self.parameters_sig_only:
            self.parameters.append(Parameter('attrs', kind=Parameter.VAR_KEYWORD))
        defaults = defaults or {}
        self.parameters_sig_only.extend([
            Parameter(name, Parameter.KEYWORD_ONLY, annotation=arg_type, default=defaults.get(name))
            for name, arg_type in args.items()
            if name != var_kwarg
        ])
        if var_kwarg:
            self.parameters_sig_only.append(
                Parameter(var_kwarg, Parameter.VAR_KEYWORD)
            )
            self.check_attrs_match_sig = False
        return self

    def with_spec_attrs_for(self, spec_cls: type, template: str = "", defaults=None, only_if: bool = True):
        """
        Add **attrs based on the attributes of a spec_class.
        """
        if not only_if or not getattr(spec_cls, '__is_spec_class__', False):
            return self
        if defaults is True:
            defaults = {
                attr: (
                    getattr(spec_cls, attr, MISSING)
                    if not inspect.isfunction(getattr(spec_cls, attr, None)) and not inspect.isdatadescriptor(getattr(spec_cls, attr, None)) else
                    MISSING
                )
                for attr in spec_cls.__spec_class_annotations__
            }
        return self.with_attrs(spec_cls.__spec_class_annotations__, var_kwarg=spec_cls.__spec_class_init_overflow_attr__, template=template, defaults=defaults)

    def with_returns(self, desc: str, annotation: Type = Parameter.empty, only_if: bool = True):
        """
        Specify return type and description.
        """
        if not only_if:
            return self

        self.returns = desc
        self.return_type = annotation if annotation is not Parameter.empty else Any

        return self

    # Documentation-only related methods.

    def with_preamble(self, value: str, only_if: bool = True):
        """
        Set documentation preamble.
        """
        if not only_if:
            return self

        self.preamble = value
        return self

    def with_notes(self, *lines, only_if=True):
        if not only_if:
            return self

        self.notes.extend([
            '\n'.join(textwrap.wrap(line, subsequent_indent='    '))
            for line in lines
        ])
        return self

    # Extractors

    @property
    def docstring(self):
        docstring = ""
        if self.preamble:
            docstring += self.preamble + "\n"
        if self.args:
            docstring += "\nArgs:\n" + textwrap.indent("\n".join(self.args), "    ")
        if self.returns:
            docstring += "\nReturns:\n" + '\n'.join(textwrap.wrap(self.returns, initial_indent='    ', subsequent_indent='    '))
        if self.notes:
            docstring += "\nNotes:\n" + textwrap.indent("\n".join(self.notes), "    ")
        return cleandoc(docstring)

    @property
    def signature(self):
        """
        The signature to use when building the method.
        """
        return Signature(parameters=self.parameters)

    @property
    def signature_advertised(self):
        """
        The signature to advertise using method.__signature__ on the built method.
        """
        if self.parameters_sig_only:
            return Signature(parameters=self.parameters[:-1] + self.parameters_sig_only)
        return self.signature

    @staticmethod
    def __check_signature_conformance(sig_method: Signature, sig_impl: Signature) -> bool:
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
                    impl_param.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
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
                if method_param.kind is Parameter.POSITIONAL_ONLY or not impl_has_var_kwargs:
                    return False

        return True

    def build(self) -> Callable:
        """
        Generate and return the built method.
        """
        namespace = {}

        signature = self.signature
        impl_signature = Signature.from_callable(self.implementation)
        signature_advertised = self.signature_advertised

        if not self.__check_signature_conformance(signature, impl_signature):
            raise ValueError(f"Proposed method signature `{self.name}{signature}` is not compatible with implementation signature `implementation{impl_signature}`.")

        def validate_attrs(attrs):
            extra_attrs = set(attrs).difference([p.name for p in self.parameters_sig_only])
            if extra_attrs:
                raise TypeError(f"{self.name}() got unexpected keyword arguments: {repr(extra_attrs)}.")

        str_signature, defaults = self.__call_signature_str(signature)

        exec(textwrap.dedent(f"""
            from __future__ import annotations
            def {self.name}{str_signature} { "-> " + str(self.return_type.__name__) if self.return_type is not None and hasattr(self.return_type, '__name__') else ""}:
                {"validate_attrs(attrs)" if self.parameters_sig_only and self.check_attrs_match_sig else ""}
                return implementation({self.__call_implementation_str(self.signature)})
        """), {'implementation': self.implementation, 'MISSING': MISSING, 'validate_attrs': validate_attrs, 'DEFAULTS': defaults}, namespace)

        method = namespace[self.name]
        method.__doc__ = self.docstring
        method.__signature__ = signature_advertised
        return method

    @staticmethod
    def __call_signature_str(signature: Signature) -> Tuple[str, Dict[str, Any]]:
        """
        Return a string representation of the signature that can be used in exec.
        """
        out = []
        defaults = {}
        done_kw_only = False
        for p in signature.parameters.values():
            if p.kind is Parameter.VAR_POSITIONAL:
                done_kw_only = True
            elif p.kind is Parameter.KEYWORD_ONLY and not done_kw_only:
                done_kw_only = True
                out.append('*')
            param = str(p).split(':')[0]
            if p.default is not Parameter.empty:
                param = param.split('=')[0]
                out.append(
                    f'{param}=DEFAULTS["{p.name}"]'
                )
                defaults[p.name] = p.default
            else:
                out.append(param)
        return f'({", ".join(out)})', defaults

    @staticmethod
    def __call_implementation_str(signature: Signature):
        """
        Return a string form "<positional_value>, ..., <field>=<value>, ..."
        """
        out = []
        for name, p in signature.parameters.items():
            if p.kind is inspect.Parameter.POSITIONAL_ONLY:
                out.append(name)
            elif p.kind is inspect.Parameter.VAR_POSITIONAL:
                out.append(f'*{name}')
            elif p.kind is inspect.Parameter.VAR_KEYWORD:
                out.append(f'**{name}')
            else:
                out.append(f'{name}={name}')
        return ", ".join(out)
