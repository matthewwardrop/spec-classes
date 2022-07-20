# pylint: disable=bad-staticmethod-argument

import copy
import functools
import inspect
from typing import Callable

from cached_property import cached_property
from lazy_object_proxy import Proxy

from spec_classes.types import Attr, MISSING
from spec_classes.utils.method_builder import MethodBuilder
from spec_classes.utils.mutation import mutate_attr, mutate_value, prepare_attr_value

from .base import AttrMethodDescriptor


class WithAttrMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `with_<attr>'.

    The default behavior of this method is to copy the spec-class with the
    nominated attribute taking on the provided value. For more information refer
    to the spec-classes documentation or the generated method.
    """

    @cached_property
    def method_name(self) -> str:
        return f"with_{self.attr_spec.name}"

    @staticmethod
    def with_attr(
        attr_spec: Attr,
        self,
        _new_value=MISSING,
        *,
        _inplace: bool = False,
        _if: bool = True,
        **attrs,
    ):
        if not _if:
            return self

        return mutate_attr(
            obj=self,
            attr=attr_spec.name,
            value=prepare_attr_value(
                attr_spec=attr_spec, instance=self, value=_new_value, attrs=attrs
            ),
            inplace=_inplace,
        )

    def build_method(self) -> Callable:
        attr_spec_type = self.attr_spec.spec_type
        or_its_attributes = " or its attributes" if attr_spec_type else ""
        return (
            MethodBuilder(self.name, functools.partial(self.with_attr, self.attr_spec))
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with `{self.attr_spec.name}`{or_its_attributes} mutated."
            )
            .with_arg(
                "_new_value",
                desc=f"The new value for `{self.attr_spec.name}`.",
                default=MISSING,
                annotation=self.attr_spec.type,
            )
            .with_arg(
                "_inplace",
                desc="Whether to perform change without first copying.",
                default=False,
                kind="keyword_only",
                annotation=bool,
            )
            .with_arg(
                "_if",
                desc="This action is only taken when `_if` is `True`. If it is `False`, this is a no-op.",
                default=True,
                kind="keyword_only",
                annotation=bool,
            )
            .with_spec_attrs_for(
                self.attr_spec.type,
                desc_template=f"An optional new value for {self.attr_spec.name}.{{}}.",
            )
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


class UpdateAttrMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `update_<attr>'.

    The default behavior of this method is to copy the spec-class with the
    nominated attribute updated with the provided values. For more
    information refer to the spec-classes documentation or the generated method.
    """

    @cached_property
    def method_name(self) -> str:
        return f"update_{self.attr_spec.name}"

    @staticmethod
    def update_attr(
        attr_spec: Attr,
        self,
        _new_value=MISSING,
        *,
        _inplace: bool = False,
        _if: bool = True,
        **attrs,
    ):
        if not _if:
            return self
        return WithAttrMethod.with_attr(
            attr_spec,
            self,
            _new_value=mutate_value(
                old_value=Proxy(lambda: getattr(self, attr_spec.name, MISSING)),
                new_value=_new_value,
                constructor=attr_spec.constructor,
                expected_type=attr_spec.type,
                attrs=attrs,
            ),
            _inplace=_inplace,
        )

    def build_method(self) -> Callable:
        self.attr_spec.name = self.attr_spec.name
        self.attr_spec.type = self.attr_spec.type
        attr_spec_type = self.attr_spec.spec_type
        or_its_attributes = " or its attributes" if attr_spec_type else ""
        return (
            MethodBuilder(
                self.name, functools.partial(self.update_attr, self.attr_spec)
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with `{self.attr_spec.name}`{or_its_attributes} updated."
            )
            .with_arg(
                "_new_value",
                desc=f"An optional value to replace the old value for `{self.attr_spec.name}`.",
                default=MISSING if attr_spec_type else inspect.Parameter.empty,
                annotation=Callable,
            )
            .with_arg(
                "_inplace",
                desc="Whether to perform change without first copying.",
                default=False,
                kind="keyword_only",
                annotation=bool,
            )
            .with_arg(
                "_if",
                desc="This action is only taken when `_if` is `True`. If it is `False`, this is a no-op.",
                default=True,
                kind="keyword_only",
                annotation=bool,
            )
            .with_spec_attrs_for(
                self.attr_spec.type,
                desc_template=f"An optional new value for {self.attr_spec.name}.{{}}.",
            )
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


class TransformAttrMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `transform_<attr>'.

    The default behavior of this method is to copy the spec-class with the
    nominated attribute transformed under the provided transform. For more
    information refer to the spec-classes documentation or the generated method.
    """

    @cached_property
    def method_name(self) -> str:
        return f"transform_{self.attr_spec.name}"

    @staticmethod
    def transform_attr(
        attr_spec: Attr,
        self,
        _transform=None,
        *,
        _inplace: bool = False,
        _if: bool = True,
        **attr_transforms,
    ):
        if not _if:
            return self
        return WithAttrMethod.with_attr(
            attr_spec,
            self,
            _new_value=mutate_value(
                old_value=Proxy(lambda: getattr(self, attr_spec.name, MISSING)),
                transform=_transform,
                constructor=attr_spec.constructor,
                expected_type=attr_spec.type,
                attr_transforms=attr_transforms,
            ),
            _inplace=_inplace,
        )

    def build_method(self) -> Callable:
        self.attr_spec.name = self.attr_spec.name
        self.attr_spec.type = self.attr_spec.type
        attr_spec_type = self.attr_spec.spec_type
        or_its_attributes = " or its attributes" if attr_spec_type else ""
        return (
            MethodBuilder(
                self.name, functools.partial(self.transform_attr, self.attr_spec)
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with `{self.attr_spec.name}`{or_its_attributes} transformed."
            )
            .with_arg(
                "_transform",
                desc=f"A function that takes the old value for {self.attr_spec.name} as input, and returns the new value.",
                default=MISSING if attr_spec_type else inspect.Parameter.empty,
                annotation=Callable,
            )
            .with_arg(
                "_inplace",
                desc="Whether to perform change without first copying.",
                default=False,
                kind="keyword_only",
                annotation=bool,
            )
            .with_arg(
                "_if",
                desc="This action is only taken when `_if` is `True`. If it is `False`, this is a no-op.",
                default=True,
                kind="keyword_only",
                annotation=bool,
            )
            .with_spec_attrs_for(
                self.attr_spec.type,
                desc_template=f"An optional transformer for {self.attr_spec.name}.{{}}.",
            )
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


class ResetAttrMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `reset_<attr>'.

    The default behavior of this method is to copy the spec-class with the
    nominated attribute reset to its default value. For more information refer
    to the spec-classes documentation or the generated method.
    """

    @cached_property
    def method_name(self) -> str:
        return f"reset_{self.attr_spec.name}"

    @staticmethod
    def reset_attr(attr_spec: Attr, self, *, _inplace: bool = False, _if: bool = True):
        if not _if:
            return self
        if not _inplace:
            self = copy.deepcopy(self)
        delattr(self, attr_spec.name)
        return self

    def build_method(self) -> Callable:
        return (
            MethodBuilder(self.name, functools.partial(self.reset_attr, self.attr_spec))
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with `{self.attr_spec.name}` reset to its default value."
            )
            .with_arg(
                "_inplace",
                desc="Whether to perform change without first copying.",
                default=False,
                kind="keyword_only",
                annotation=bool,
            )
            .with_arg(
                "_if",
                desc="This action is only taken when `_if` is `True`. If it is `False`, this is a no-op.",
                default=True,
                kind="keyword_only",
                annotation=bool,
            )
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


SCALAR_METHODS = [
    WithAttrMethod,
    UpdateAttrMethod,
    TransformAttrMethod,
    ResetAttrMethod,
]
