from inspect import Parameter
from spec_classes.types.missing import MISSING
from spec_classes.utils.type_checking import get_collection_item_type, type_label
from spec_classes.utils.mutation import mutate_attr
from spec_classes.utils.method_builder import MethodBuilder
from ..base import AttrMethodDescriptor

import functools
from typing import Any, Callable, TypeVar


class WithSetItemMethod(AttrMethodDescriptor):

    @property
    def name(self):
        return f"with_{self.attr_spec.item_name}"

    @staticmethod
    def with_set_item(attr_spec, self, _item, *, _inplace=False, _if=True, **attrs):
        if not _if:
            return self
        return mutate_attr(
            obj=self,
            attr=attr_spec.name,
            value=(
                attr_spec.get_collection(self, inplace=_inplace)
                .add_item(
                    item=attr_spec.prepare_item(self, _item, **attrs),
                    attrs=attrs,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self):
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.with_set_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item added to `{self.attr_spec.name}`."
            )
            .with_arg(
                "_item",
                f"A new `{type_label(self.attr_spec.item_type)}` instance for {self.attr_spec.name}.",
                default=MISSING if self.attr_spec.item_spec_type else Parameter.empty,
                annotation=self.attr_spec.item_type,
            )
            .with_arg(
                "_inplace",
                "Whether to perform change without first copying.",
                default=False,
                keyword_only=True,
                annotation=bool,
            )
            .with_arg(
                "_if",
                "This action is only taken when `_if` is `True`. If it is `False`, this is a no-op.",
                default=True,
                keyword_only=True,
                annotation=bool,
            )
            .with_spec_attrs_for(
                self.attr_spec.item_spec_type,
                template=f"An optional new value for `{self.attr_spec.item_name}.{{}}`.",
            )
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


class TransformSetItemMethod(AttrMethodDescriptor):

    @property
    def name(self):
        return f"transform_{self.attr_spec.item_name}"

    @staticmethod
    def transform_set_item(attr_spec, self, _item, _transform, *, _inplace=False, _if=True, **attr_transforms):
        if not _if:
            return self
        return mutate_attr(
            obj=self,
            attr=attr_spec.name,
            value=(
                attr_spec.get_collection(self, inplace=_inplace)
                .transform_item(
                    item=_item,
                    transform=_transform,
                    attr_transforms=attr_transforms,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self):
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.transform_set_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item transformed in `{self.attr_spec.name}`."
            )
            .with_arg("_item", "The value to transform.", annotation=self.attr_spec.item_type)
            .with_arg(
                "_transform",
                "A function that takes the old item as input, and returns the new item.",
                default=MISSING if self.attr_spec.item_spec_type else Parameter.empty,
                annotation=Callable,
            )
            .with_arg(
                "_inplace",
                "Whether to perform change without first copying.",
                default=False,
                keyword_only=True,
                annotation=bool,
            )
            .with_arg(
                "_if",
                "This action is only taken when `_if` is `True`. If it is `False`, this is a no-op.",
                default=True,
                keyword_only=True,
                annotation=bool,
            )
            .with_spec_attrs_for(
                self.attr_spec.item_spec_type,
                template=f"An optional transformer for `{self.attr_spec.item_name}.{{}}`.",
            )
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


class WithoutSetItemMethod(AttrMethodDescriptor):

    @property
    def name(self):
        return f"without_{self.attr_spec.item_name}"

    @staticmethod
    def without_set_item(attr_spec, self, _item, _inplace=False, _if=True):
        if not _if:
            return self
        return mutate_attr(
            obj=self,
            attr=attr_spec.name,
            value=(
                attr_spec.get_collection(self, inplace=_inplace)
                .remove_item(_item)
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self):
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.without_set_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item removed from `{self.attr_spec.name}`."
            )
            .with_arg("_item", "The value to remove.", annotation=self.attr_spec.item_type)
            .with_arg(
                "_inplace",
                "Whether to perform change without first copying.",
                default=False,
                keyword_only=True,
                annotation=bool,
            )
            .with_arg(
                "_if",
                "This action is only taken when `_if` is `True`. If it is `False`, this is a no-op.",
                default=True,
                keyword_only=True,
                annotation=bool,
            )
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


SET_METHODS = [
    WithSetItemMethod,
    TransformSetItemMethod,
    WithoutSetItemMethod,
]
