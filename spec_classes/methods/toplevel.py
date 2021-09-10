# pylint: disable=bad-staticmethod-argument

import copy
from typing import Any, Callable

from spec_classes.types import MISSING
from spec_classes.utils.method_builder import MethodBuilder
from spec_classes.utils.mutation import mutate_value
from spec_classes.utils.type_checking import type_label

from .base import MethodDescriptor


class UpdateMethod(MethodDescriptor):
    """
    The method descriptor/generator for `update`.

    The default behavior of this method is to update nominated attributes,
    copying if necessary to avoid modifying the original spec class instance.
    """

    method_name = "update"

    @staticmethod
    def update(
        self,
        _new_value=MISSING,
        *,
        _inplace: bool = False,
        _if: bool = True,
        **attrs,
    ):
        if not _if:
            return self

        return mutate_value(
            old_value=self,
            new_value=_new_value,
            attrs=attrs,
            inplace=_inplace,
        )

    def build_method(self) -> Callable:
        return (
            MethodBuilder(self.name, self.update)
            .with_preamble(
                f"Return `_new_value`, or an `{self.spec_cls.__name__}` instance identical to this one except with nominated attributes mutated."
            )
            .with_arg(
                "_new_value",
                desc="A complete replacement for this instance.",
                default=MISSING,
                annotation=self.spec_cls,
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
                self.spec_cls,
                desc_template=f"An optional new value for {type_label(self.spec_cls)}.{{}}.",
            )
            .with_returns(
                f"`_new_value` or a reference to the mutated `{type_label(self.spec_cls)}` instance.",
                annotation=Any,
            )
            .build()
        )


class TransformMethod(MethodDescriptor):
    """
    The method descriptor/generator for `transform`.

    The default behavior of this method is to update nominated attributes under
    the provided transformations, copying as necessary to avoid modifying
    in-place.
    """

    method_name = "transform"

    @staticmethod
    def transform(
        self,
        _transform=None,
        *,
        _inplace: bool = False,
        _if: bool = True,
        **attr_transforms,
    ):
        if not _if:
            return self

        return mutate_value(
            old_value=self,
            transform=_transform,
            attr_transforms=attr_transforms,
            inplace=_inplace,
        )

    def build_method(self) -> Callable:
        return (
            MethodBuilder(self.name, self.transform)
            .with_preamble(f"Return a transformed `{self.spec_cls.__name__}` instance.")
            .with_arg(
                "_transform",
                desc=f"A function that takes the current `{type_label(self.spec_cls)}` instance, and returns the new value.",
                default=MISSING,
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
                self.spec_cls,
                desc_template=f"An optional transformer for {type_label(self.spec_cls)}.{{}}.",
            )
            .with_returns(
                f"The output of `_transform(self)` or a reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=Any,
            )
            .build()
        )


class ResetMethod(MethodDescriptor):
    """
    The method descriptor/generator for `reset'.

    This method resets all managed attributes back to their default values.
    """

    method_name = "reset"

    @staticmethod
    def reset(
        self,
        *,
        _inplace: bool = False,
        _if: bool = True,
    ):
        if not _if:
            return self

        if not _inplace:
            self = copy.deepcopy(self)

        for attr in self.__spec_class__.attrs:
            try:
                delattr(self, attr)
            except AttributeError:
                pass

        return self

    def build_method(self) -> Callable:
        return (
            MethodBuilder(self.name, self.reset)
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical but with all attributes reset to their default values."
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
                f"A reference to the mutated `{type_label(self.spec_cls)}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


TOPLEVEL_METHODS = [
    UpdateMethod,
    TransformMethod,
    ResetMethod,
]
