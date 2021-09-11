import functools
from inspect import Parameter
from typing import Any, Callable, Dict, Union

from spec_classes.types import Attr, MISSING
from spec_classes.utils.method_builder import MethodBuilder
from spec_classes.utils.mutation import mutate_attr
from spec_classes.utils.type_checking import type_label

from ..base import AttrMethodDescriptor


def _get_sequence_index_and_item_annotations(attr_spec):
    """
    Get the annotations of indexes and items for sequence method signatures.
    """
    index_type = Union[
        int, Any
    ]  # Some sequence containers (e.g. KeyedList) accept arbitrary index types.
    item_type = attr_spec.item_type
    if attr_spec.item_spec_key_type:
        item_type = Union[
            attr_spec.item_spec_key_type,
            item_type,
        ]
    return index_type, item_type


class WithSequenceItemMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `with_<attr_singular>' for sequence
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
    def with_sequence_item(
        attr_spec: Attr,
        self,
        _item: Any = MISSING,
        *,
        _index: Any = MISSING,
        _insert: bool = False,
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
                    value_or_index=_index,
                    by_index=True,
                    insert=_insert,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
        fn_index_type, fn_item_type = _get_sequence_index_and_item_annotations(
            self.attr_spec
        )
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.with_sequence_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item added to or updated in `{self.attr_spec.name}`."
            )
            .with_arg(
                "_item",
                desc=f"A new `{type_label(self.attr_spec.item_type)}` instance for {self.attr_spec.name}.",
                default=MISSING,
                annotation=fn_item_type,
            )
            .with_arg(
                "_index",
                desc="Index for which to insert or replace, depending on `insert`; if not provided, append.",
                default=MISSING,
                kind="keyword_only",
                annotation=fn_index_type,
            )
            .with_arg(
                "_insert",
                desc=f"Insert item before {self.attr_spec.name}[index], otherwise replace this index.",
                default=False,
                kind="keyword_only",
                annotation=bool,
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


class UpdateSequenceItemMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `update_<attr_singular>' for sequence
    collections.

    The default behavior of this method is to copy the spec-class with the item
    associated with the given index/value in the collection associated with the
    singular form of the attribute name mutated with the provided values. For
    more information refer to the spec-classes documentation or the generated
    method.
    """

    @property
    def method_name(self) -> str:
        return f"update_{self.attr_spec.item_name}"

    @staticmethod
    def update_sequence_item(
        attr_spec: Attr,
        self,
        _value_or_index: Any,
        _new_item: Any,
        *,
        _by_index: Any = MISSING,
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
                    value_or_index=_value_or_index,
                    by_index=_by_index,
                    replace=False,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
        fn_index_type, fn_item_type = _get_sequence_index_and_item_annotations(
            self.attr_spec
        )
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.update_sequence_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item updated in `{self.attr_spec.name}`."
            )
            .with_arg(
                "_value_or_index",
                desc="The value or index look up and transform.",
                annotation=Union[fn_item_type, fn_index_type],
            )
            .with_arg(
                "_new_item",
                desc="An optional replacement for the item.",
                default=MISSING,
                annotation=Callable[[fn_item_type], fn_item_type],
            )
            .with_arg(
                "_by_index",
                desc="If True, value_or_index is the index of the item to transform.",
                kind="keyword_only",
                default=MISSING,
                annotation=bool,
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
                desc_template=f"An optional value for `{self.attr_spec.item_name}.{{}}`.",
            )
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


class TransformSequenceItemMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `transform_<attr_singular>' for sequence
    collections.

    The default behavior of this method is to copy the spec-class with the item
    associated with the given index/value in the collection associated with the
    singular form of the attribute name transformed under the provided
    transform. For more information refer to the spec-classes documentation or
    the generated method.
    """

    @property
    def method_name(self) -> str:
        return f"transform_{self.attr_spec.item_name}"

    @staticmethod
    def transform_sequence_item(
        attr_spec: Attr,
        self,
        _value_or_index: Any,
        _transform: Callable[[Any], Any],
        *,
        _by_index: Any = MISSING,
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
                    value_or_index=_value_or_index,
                    transform=_transform,
                    by_index=_by_index,
                    attr_transforms=attr_transforms,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
        fn_index_type, fn_item_type = _get_sequence_index_and_item_annotations(
            self.attr_spec
        )
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.transform_sequence_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item transformed in `{self.attr_spec.name}`."
            )
            .with_arg(
                "_value_or_index",
                desc="The value to transform, or (if `by_index=True`) its index.",
                annotation=Union[fn_item_type, fn_index_type],
            )
            .with_arg(
                "_transform",
                desc="A function that takes the old item as input, and returns the new item.",
                default=MISSING if self.attr_spec.item_spec_type else Parameter.empty,
                annotation=Callable[[fn_item_type], fn_item_type],
            )
            .with_arg(
                "_by_index",
                desc="If True, value_or_index is the index of the item to transform.",
                kind="keyword_only",
                default=MISSING,
                annotation=bool,
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


class WithoutSequenceItemMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `without_<attr_singular>' for sequence
    collections.

    The default behavior of this method is to copy the spec-class with the item
    associated with the given index/value in the collection associated with the
    singular form of the attribute name removed. For more information refer to
    the spec-classes documentation or the generated method.
    """

    @property
    def method_name(self) -> str:
        return f"without_{self.attr_spec.item_name}"

    @staticmethod
    def without_sequence_item(
        attr_spec: Attr,
        self,
        _value_or_index: Any,
        *,
        _by_index: Any = MISSING,
        _inplace: bool = False,
        _if: bool = True,
    ) -> Any:
        if not _if:
            return self
        return mutate_attr(
            obj=self,
            attr=attr_spec.name,
            value=(
                attr_spec.get_collection_mutator(self, inplace=_inplace)
                .remove_item(
                    value_or_index=_value_or_index,
                    by_index=_by_index,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
        fn_index_type, fn_item_type = _get_sequence_index_and_item_annotations(
            self.attr_spec
        )
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.without_sequence_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item removed from `{self.attr_spec.name}`."
            )
            .with_arg(
                "_value_or_index",
                desc="The value to remove, or (if `by_index=True`) its index.",
                annotation=Union[fn_item_type, fn_index_type],
            )
            .with_arg(
                "_by_index",
                desc="If True, value_or_index is the index of the item to remove.",
                default=MISSING,
                kind="keyword_only",
                annotation=bool,
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


SEQUENCE_METHODS = [
    WithSequenceItemMethod,
    UpdateSequenceItemMethod,
    TransformSequenceItemMethod,
    WithoutSequenceItemMethod,
]
