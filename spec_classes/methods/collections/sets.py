import functools
from inspect import Parameter
from typing import Any, Callable, Dict, Union

from spec_classes.types import Attr, MISSING
from spec_classes.utils.method_builder import MethodBuilder
from spec_classes.utils.mutation import mutate_attr
from spec_classes.utils.type_checking import type_label

from ..base import AttrMethodDescriptor


def _get_set_item_type(attr_spec):
    """
    Get the type(s) of items for set method signatures.
    """
    item_type = attr_spec.item_type
    if attr_spec.item_spec_key_type:
        item_type = Union[
            attr_spec.item_spec_key_type,
            item_type,
        ]
    return item_type


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
                attr_spec.get_collection_mutator(self, inplace=_inplace)
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
        fn_item_type = _get_set_item_type(self.attr_spec)
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
                desc=f"A new `{type_label(self.attr_spec.item_type)}` instance for {self.attr_spec.name}.",
                default=MISSING if self.attr_spec.item_spec_type else Parameter.empty,
                annotation=fn_item_type,
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
                self.attr_spec.item_spec_type,
                desc_template=f"An optional new value for `{self.attr_spec.item_name}.{{}}`.",
            )
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


class UpdateSetItemMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `update_<attr_singular>' for set
    collections.

    The default behavior of this method is to copy the spec-class with the item
    associated with the given item in the collection associated with the
    singular form of the attribute name updated with the provided new values.
    For more information refer to the spec-classes documentation or the
    generated method.
    """

    @property
    def method_name(self) -> str:
        return f"update_{self.attr_spec.item_name}"

    @staticmethod
    def update_set_item(
        attr_spec: Attr,
        self,
        _item: Any,
        _new_item: Any,
        *,
        _inplace: bool = False,
        _if: bool = True,
        **attrs: Dict[str, Any],
    ) -> Any:
        if not _if:
            return self

        return mutate_attr(
            obj=self,
            attr=attr_spec.name,
            value=(
                attr_spec.get_collection_mutator(self, inplace=_inplace)
                .add_item(
                    item=_new_item,
                    attrs=attrs,
                    value_or_index=_item,
                    replace=False,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
        fn_item_type = _get_set_item_type(self.attr_spec)
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.update_set_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item updated in `{self.attr_spec.name}`."
            )
            .with_arg(
                "_item",
                desc="The value to transform.",
                annotation=fn_item_type,
            )
            .with_arg(
                "_new_item",
                desc="A new item to replace the current item.",
                default=MISSING if self.attr_spec.item_spec_type else Parameter.empty,
                annotation=Callable[[fn_item_type], fn_item_type],
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
                self.attr_spec.item_spec_type,
                desc_template=f"An optional new value for `{self.attr_spec.item_name}.{{}}`.",
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
                attr_spec.get_collection_mutator(self, inplace=_inplace)
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
        fn_item_type = _get_set_item_type(self.attr_spec)
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.transform_set_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item transformed in `{self.attr_spec.name}`."
            )
            .with_arg(
                "_item",
                desc="The value to transform.",
                annotation=fn_item_type,
            )
            .with_arg(
                "_transform",
                desc="A function that takes the old item as input, and returns the new item.",
                default=MISSING if self.attr_spec.item_spec_type else Parameter.empty,
                annotation=Callable[[fn_item_type], fn_item_type],
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
                self.attr_spec.item_spec_type,
                desc_template=f"An optional transformer for `{self.attr_spec.item_name}.{{}}`.",
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
                attr_spec.get_collection_mutator(self, inplace=_inplace)
                .remove_item(_item)
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
        fn_item_type = _get_set_item_type(self.attr_spec)
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.without_set_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item removed from `{self.attr_spec.name}`."
            )
            .with_arg(
                "_item",
                desc="The value to remove.",
                annotation=fn_item_type,
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


SET_METHODS = [
    WithSetItemMethod,
    UpdateSetItemMethod,
    TransformSetItemMethod,
    WithoutSetItemMethod,
]
