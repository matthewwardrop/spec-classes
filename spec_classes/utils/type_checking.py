from typing import Any, Union, _GenericAlias, Type, TypeVar  # pylint: disable=protected-access


def type_match(type_input: Type, type_reference: type) -> bool:
    """
    Check whether `type_input` matches `type_reference`, that latter of
    which is permitted to be a sequence of multiple values; but cannot be
    a parameterized generic type.
    """
    while hasattr(type_input, '__origin__'):
        type_input = type_input.__origin__
    return isinstance(type_input, type) and issubclass(type_input, type_reference)


def check_type(value: Any, attr_type: Type) -> bool:
    """
    Check whether a given object `value` matches the provided `attr_type`.
    """
    if attr_type is Any:
        return True

    if hasattr(attr_type, '__origin__'):  # we are dealing with a `typing` object.

        if attr_type.__origin__ is Union:
            return any(check_type(value, type_) for type_ in attr_type.__args__)

        if isinstance(attr_type, _GenericAlias):
            if not isinstance(value, attr_type.__origin__):
                return False
            if attr_type._name in ('List', 'Set') and not isinstance(attr_type.__args__[0], TypeVar):  # pylint: disable=protected-access
                for item in value:
                    if not check_type(item, attr_type.__args__[0]):
                        return False
            elif attr_type._name == 'Dict' and not isinstance(attr_type.__args__[0], TypeVar):  # pylint: disable=protected-access
                for k, v in value.items():
                    if not check_type(k, attr_type.__args__[0]):
                        return False
                    if not check_type(v, attr_type.__args__[1]):
                        return False
            return True

        return isinstance(value, attr_type.__origin__)  # pragma: no cover; This is here as a fallback currently, just in case!

    return isinstance(value, attr_type)


def get_collection_item_type(container_type: Type) -> Type:
    """
    Return the type of object inside a typing container (List, Set, Dict),
    or `None` if this isn't annotated.
    """
    if not hasattr(container_type, '__args__'):  # i.e. this is not a `typing` container
        return Any

    item_type = Any
    if type_match(container_type, dict) and len(container_type.__args__) == 2:
        item_type = container_type.__args__[1]
    elif len(container_type.__args__) == 1:
        item_type = container_type.__args__[0]
    if isinstance(item_type, TypeVar):
        item_type = Any
    return item_type


def get_spec_class_for_type(attr_type: Type, allow_polymorphic=False) -> Union[Type, None]:
    """
    Get the spec class to associated with a given attribute type. This is
    useful when `attr_type` is a polymorphic type, e.g.
    Union[SpecClass, str]. It works by finding the spec class type in the
    polymorphic type. If there is not exactly one spec class type, `None` is
    returned.
    """
    if getattr(attr_type, '__is_spec_class__', False):
        attr_type.__spec_class_bootstrap__()
        return attr_type
    if allow_polymorphic and getattr(attr_type, '__origin__', None) is Union:
        spec_classes = [
            typ
            for typ in attr_type.__args__
            if getattr(typ, '__is_spec_class__', False)
        ]
        if len(spec_classes) == 1:
            spec_class = spec_classes[0]
            spec_class.__spec_class_bootstrap__()
            return spec_class
    return None


def type_label(attr_type: Type) -> str:
    """
    Generate the label to be used to describe an `attr_type` in generated
    user documentation. Since we care about the output of this method when
    `attr_type` points to a `spec_cls` decorated type, we don't make this
    method general.
    """
    if isinstance(attr_type, type):
        return attr_type.__name__
    return "object"
