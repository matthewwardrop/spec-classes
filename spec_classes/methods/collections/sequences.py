import functools
from inspect import Parameter
from typing import Any, Callable, Dict, Union

from spec_classes.types import Attr, MISSING
from spec_classes.utils.method_builder import MethodBuilder
from spec_classes.utils.mutation import mutate_attr
from spec_classes.utils.type_checking import type_label

from ..base import AttrMethodDescriptor


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
                attr_spec.get_collection(self, inplace=_inplace)
                .add_item(
                    item=_item,
                    attrs=attrs,
                    index=_index,
                    insert=_insert,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
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
                kind="keyword_only",
                annotation=fn_index_type,
            )
            .with_arg(
                "_insert",
                f"Insert item before {self.attr_spec.name}[index], otherwise replace this index.",
                default=False,
                kind="keyword_only",
                annotation=bool,
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

    def build_method(self) -> Callable:
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
                kind="keyword_only",
                default=MISSING,
                annotation=bool,
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

    def build_method(self) -> Callable:
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
                kind="keyword_only",
                annotation=bool,
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


SEQUENCE_METHODS = [
    WithSequenceItemMethod,
    TransformSequenceItemMethod,
    WithoutSequenceItemMethod,
]