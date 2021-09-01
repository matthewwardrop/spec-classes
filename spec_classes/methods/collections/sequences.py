from inspect import Parameter
from spec_classes.types.missing import MISSING
from spec_classes.utils.type_checking import get_collection_item_type, type_label
from spec_classes.utils.mutation import mutate_attr
from spec_classes.utils.method_builder import MethodBuilder
from ..base import AttrMethodDescriptor

import functools
from typing import Any, Callable, TypeVar, Union


class WithSequenceItemMethod(AttrMethodDescriptor):

    @property
    def name(self):
        return f"with_{self.attr_spec.item_name}"

    @staticmethod
    def with_sequence_item(attr_spec, self, _item=MISSING, *, _index=MISSING, _insert=False, _inplace=False, _if=True, **attrs):
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
                    index=_index,
                    insert=_insert,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self):
        fn_item_type = self.attr_spec.item_type
        fn_index_type = Union[int, Any]
        if self.attr_spec.spec_type:
            fn_item_type = Union[
                self.attr_spec.item_spec_type.__spec_class__.annotations[
                    self.attr_spec.item_spec_type.__spec_class__.key
                ],
                fn_item_type,
            ]
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
                f"A new `{type_label(self.attr_spec.item_type)}` instance for {self.attr_spec.name}.",
                default=MISSING,
                annotation=fn_item_type,
            )
            .with_arg(
                "_index",
                "Index for which to insert or replace, depending on `insert`; if not provided, append.",
                default=MISSING,
                keyword_only=True,
                annotation=fn_index_type,
            )
            .with_arg(
                "_insert",
                f"Insert item before {self.attr_spec.name}[index], otherwise replace this index.",
                default=False,
                keyword_only=True,
                annotation=bool,
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


class TransformSequenceItemMethod(AttrMethodDescriptor):

    @property
    def name(self):
        return f"transform_{self.attr_spec.item_name}"

    @staticmethod
    def transform_sequence_item(attr_spec, self, _value_or_index, _transform, *, _by_index=MISSING, _inplace=False, _if=True, **attr_transforms):
        if not _if:
            return self
        return mutate_attr(
            obj=self,
            attr=attr_spec.name,
            value=(
                attr_spec.get_collection(self, inplace=_inplace)
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

    def build_method(self):
        fn_item_type = self.attr_spec.item_type
        fn_index_type = Union[int, Any]
        if self.attr_spec.spec_type:
            fn_item_type = Union[
                self.attr_spec.item_spec_type.__spec_class__.annotations[
                    self.attr_spec.item_spec_type.__spec_class__.key
                ],
                fn_item_type,
            ]
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
                "The value to transform, or (if `by_index=True`) its index.",
                annotation=Union[fn_item_type, fn_index_type],
            )
            .with_arg(
                "_transform",
                "A function that takes the old item as input, and returns the new item.",
                default=MISSING if self.attr_spec.item_spec_type else Parameter.empty,
                annotation=Callable,
            )
            .with_arg(
                "_by_index",
                "If True, value_or_index is the index of the item to transform.",
                keyword_only=True,
                default=MISSING,
                annotation=bool,
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


class WithoutSequenceItemMethod(AttrMethodDescriptor):

    @property
    def name(self):
        return f"without_{self.attr_spec.item_name}"

    @staticmethod
    def without_sequence_item(attr_spec, self, _value_or_index, *, _by_index=MISSING, _inplace=False, _if=True):
        if not _if:
            return self
        return mutate_attr(
            obj=self,
            attr=attr_spec.name,
            value=(
                attr_spec.get_collection(self, inplace=_inplace)
                .remove_item(
                    value_or_index=_value_or_index,
                    by_index=_by_index,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self):
        fn_item_type = self.attr_spec.item_type
        fn_index_type = Union[int, Any]
        if self.attr_spec.spec_type:
            fn_item_type = Union[
                self.attr_spec.item_spec_type.__spec_class__.annotations[
                    self.attr_spec.item_spec_type.__spec_class__.key
                ],
                fn_item_type,
            ]
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
                "The value to remove, or (if `by_index=True`) its index.",
                annotation=Union[fn_item_type, fn_index_type],
            )
            .with_arg(
                "_by_index",
                "If True, value_or_index is the index of the item to remove.",
                default=MISSING,
                keyword_only=True,
                annotation=bool,
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
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


SEQUENCE_METHODS = [
    WithSequenceItemMethod,
    TransformSequenceItemMethod,
    WithoutSequenceItemMethod,
]
