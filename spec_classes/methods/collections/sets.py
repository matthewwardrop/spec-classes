import functools
from inspect import Parameter
from typing import Any, Callable, Dict

from spec_classes.types import Attr, MISSING
from spec_classes.utils.method_builder import MethodBuilder
from spec_classes.utils.mutation import mutate_attr
from spec_classes.utils.type_checking import type_label

from ..base import AttrMethodDescriptor


class WithSetItemMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `with_<attr_singular>' for set
    collections.

    The default behavior of this method is to copy the spec-class with an
    additional item added to the collection associated with the singular form of
    the attribute name. For more information refer to the spec-classes
    documentation or the generated method.
    """

    @property
    def method_name(self) -> str:
        return f"with_{self.attr_spec.item_name}"

    @staticmethod
    def with_set_item(
        attr_spec: Attr,
        self,
        _item: Any,
        *,
        _inplace: bool = False,
        _if: bool = True,
        **attrs,
    ) -> Any:
        if not _if:
            return self
        return mutate_attr(
            obj=self,
            attr=attr_spec.name,
            value=(
                attr_spec.get_collection(self, inplace=_inplace)
                .add_item(
                    item=_item,
                    attrs=attrs,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
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
                kind="keyword_only",
                annotation=bool,
            )
            .with_arg(
                "_if",
                "This action is only taken when `_if` is `True`. If it is `False`, this is a no-op.",
                default=True,
                kind="keyword_only",
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
    """
    The method descriptor/generator for `transform_<attr_singular>' for set
    collections.

    The default behavior of this method is to copy the spec-class with the item
    associated with the given item in the collection associated with the
    singular form of the attribute name transformed under the provided
    transform. For more information refer to the spec-classes documentation or
    the generated method.
    """

    @property
    def method_name(self) -> str:
        return f"transform_{self.attr_spec.item_name}"

    @staticmethod
    def transform_set_item(
        attr_spec: Attr,
        self,
        _item: Any,
        _transform: Callable[[Any], Any],
        *,
        _inplace: bool = False,
        _if: bool = True,
        **attr_transforms: Dict[str, Callable[[Any], Any]],
    ) -> Any:
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

    def build_method(self) -> Callable:
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.transform_set_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item transformed in `{self.attr_spec.name}`."
            )
            .with_arg(
                "_item", "The value to transform.", annotation=self.attr_spec.item_type
            )
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
                kind="keyword_only",
                annotation=bool,
            )
            .with_arg(
                "_if",
                "This action is only taken when `_if` is `True`. If it is `False`, this is a no-op.",
                default=True,
                kind="keyword_only",
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
    """
    The method descriptor/generator for `without_<attr_singular>' for set
    collections.

    The default behavior of this method is to copy the spec-class with the given
    item in the collection associated with the singular form of the attribute
    name removed. For more information refer to the spec-classes documentation
    or the generated method.
    """

    @property
    def method_name(self) -> str:
        return f"without_{self.attr_spec.item_name}"

    @staticmethod
    def without_set_item(
        attr_spec: Attr, self, _item: Any, *, _inplace: bool = False, _if: bool = True
    ) -> Any:
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

    def build_method(self) -> Callable:
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.without_set_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item removed from `{self.attr_spec.name}`."
            )
            .with_arg(
                "_item", "The value to remove.", annotation=self.attr_spec.item_type
            )
            .with_arg(
                "_inplace",
                "Whether to perform change without first copying.",
                default=False,
                kind="keyword_only",
                annotation=bool,
            )
            .with_arg(
                "_if",
                "This action is only taken when `_if` is `True`. If it is `False`, this is a no-op.",
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


SET_METHODS = [
    WithSetItemMethod,
    TransformSetItemMethod,
    WithoutSetItemMethod,
]
