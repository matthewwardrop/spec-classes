import functools
from inspect import Parameter
from typing import Any, Callable, Dict, TypeVar, Union

from spec_classes.types import Attr, MISSING
from spec_classes.utils.method_builder import MethodBuilder
from spec_classes.utils.mutation import mutate_attr
from spec_classes.utils.type_checking import type_label

from ..base import AttrMethodDescriptor


def _get_mapping_key_and_value_annotations(attr_spec):
    """
    Get the annotations of keys and values for mapping method signatures.
    """
    key_type = (
        attr_spec.type.__args__[0]
        if hasattr(attr_spec.type, "__args__")
        and not isinstance(attr_spec.type.__args__[0], TypeVar)
        else Any
    )
    value_type = attr_spec.item_type
    if attr_spec.item_spec_key_type:
        value_type = Union[
            attr_spec.item_spec_key_type,
            value_type,
        ]
    return key_type, value_type


class WithMappingItemMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `with_<attr_singular>' for mapping
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
    def with_mapping_item(
        attr_spec: Attr,
        self,
        _key: Any = None,
        _value: Any = None,
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
                    _key,
                    _value,
                    attrs=attrs,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
        fn_key_type, fn_value_type = _get_mapping_key_and_value_annotations(
            self.attr_spec
        )
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.with_mapping_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item added to or updated in `{self.attr_spec.name}`."
            )
            .with_arg(
                "_key",
                desc="The key for the item to be inserted or updated.",
                annotation=fn_key_type,
            )
            .with_arg(
                "_value",
                desc=f"A new `{type_label(self.attr_spec.item_type)}` instance for {self.attr_spec.name}.",
                default=MISSING if self.attr_spec.item_spec_type else Parameter.empty,
                annotation=fn_value_type,
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


class UpdateMappingItemMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `update_<attr_singular>' for mapping
    collections.

    This method updates the value (or the attributes thereof) associated
    assigned to a spec-class atribute. For more information refer to the
    spec-classes documentation or the generated method.
    """

    @property
    def method_name(self) -> str:
        return f"update_{self.attr_spec.item_name}"

    @staticmethod
    def update_mapping_item(
        attr_spec: Attr,
        self,
        _key: Any,
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
                    key=_key,
                    value=_new_item,
                    attrs=attrs,
                    replace=False,
                    require_pre_existent=True,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
        fn_key_type, fn_value_type = _get_mapping_key_and_value_annotations(
            self.attr_spec
        )
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.update_mapping_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item updated in `{self.attr_spec.name}`."
            )
            .with_arg(
                "_key",
                desc="The key for the item to be updated.",
                annotation=fn_key_type,
            )
            .with_arg(
                "_new_item",
                desc="A new value for the nominated key.",
                default=MISSING if self.attr_spec.item_spec_type else Parameter.empty,
                annotation=Callable[[fn_value_type], fn_value_type],
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
                desc_template=f"Optional new value for `{self.attr_spec.item_name}.{{}}`.",
            )
            .with_returns(
                f"A reference to the mutated `{self.spec_cls.__name__}` instance.",
                annotation=self.spec_cls,
            )
            .build()
        )


class TransformMappingItemMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `transform_<attr_singular>' for mapping
    collections.

    The default behavior of this method is to copy the spec-class with the item
    associated with the given key in the collection associated with the singular
    form of the attribute name transformed under the provided transform. For
    more information refer to the spec-classes documentation or the generated
    method.
    """

    @property
    def method_name(self) -> str:
        return f"transform_{self.attr_spec.item_name}"

    @staticmethod
    def transform_mapping_item(
        attr_spec: Attr,
        self,
        _key: Any,
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
                    key=_key,
                    transform=_transform,
                    attr_transforms=attr_transforms,
                )
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
        fn_key_type, fn_value_type = _get_mapping_key_and_value_annotations(
            self.attr_spec
        )
        return (
            MethodBuilder(
                self.name,
                functools.partial(self.transform_mapping_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item transformed in `{self.attr_spec.name}`."
            )
            .with_arg(
                "_key",
                desc="The key for the item to be inserted or updated.",
                annotation=fn_key_type,
            )
            .with_arg(
                "_transform",
                desc="A function that takes the old item as input, and returns the new item.",
                default=MISSING if self.attr_spec.item_spec_type else Parameter.empty,
                annotation=Callable[[fn_value_type], fn_value_type],
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


class WithoutMappingItemMethod(AttrMethodDescriptor):
    """
    The method descriptor/generator for `without_<attr_singular>' for mapping
    collections.

    The default behavior of this method is to copy the spec-class with the item
    associated with the given key in the collection associated with the singular
    form of the attribute name removed. For more information refer to the
    spec-classes documentation or the generated method.
    """

    @property
    def method_name(self) -> str:
        return f"without_{self.attr_spec.item_name}"

    @staticmethod
    def without_mapping_item(
        attr_spec: Attr, self, _key: Any, *, _inplace: bool = False, _if: bool = True
    ) -> Any:
        if not _if:
            return self
        return mutate_attr(
            obj=self,
            attr=attr_spec.name,
            value=(
                attr_spec.get_collection_mutator(self, inplace=_inplace)
                .remove_item(key=_key)
                .collection
            ),
            inplace=_inplace,
            type_check=False,
        )

    def build_method(self) -> Callable:
        fn_key_type, _ = _get_mapping_key_and_value_annotations(self.attr_spec)
        return (
            MethodBuilder(
                f"without_{self.attr_spec.item_name}",
                functools.partial(self.without_mapping_item, self.attr_spec),
            )
            .with_preamble(
                f"Return a `{self.spec_cls.__name__}` instance identical to this one except with an item removed from `{self.attr_spec.name}`."
            )
            .with_arg(
                "_key", desc="The key of the item to remove.", annotation=fn_key_type
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


MAPPING_METHODS = [
    WithMappingItemMethod,
    UpdateMappingItemMethod,
    TransformMappingItemMethod,
    WithoutMappingItemMethod,
]
