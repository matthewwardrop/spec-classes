import types
from abc import ABCMeta, abstractmethod
from typing import Any, Callable, Type

from cached_property import cached_property

from spec_classes.types import Attr


class MethodDescriptor(metaclass=ABCMeta):
    """
    A [descriptor](https://docs.python.org/3/howto/descriptor.html) object that
    is used by spec-classes to attach methods to classes. It is implemented as
    a descriptor so that methods are only generated when they are needed, and
    so that we can easily split out the implementation of a method from its
    generated (user-friendly) wrapper.

    By default, this descriptor is "dissolved" and replaced by the generated
    method once it is accessed by the users. You can disable this by passing
    `dissolve=False` to the constructor.

    Subclasses should implement `method_name` and `build_method`.

    Class Attributes:
        method_name: The intended (default) name for this method. The actual
            name may differ (see `attr_name`).

    Attributes:
        attr_name: The name assigned to this method during attaching to a class.
            If it is not yet attached, this will be `None`. This may differ from
            `method_name` if the method was attached via an alias.
        spec_cls: The spec class to which this method is attached. It is
            populated optionally in the constructor, and when Python attaches
            this object to the host class.
        dissolve: Whether to dissolve this descriptor by replacing itself with
            the generated method after it is accessed for the first time
            (resulting in this object being garbage collected). By default this
            is true.
    """

    def __init__(self, spec_cls: Type = None, dissolve: bool = True):
        self.spec_cls = spec_cls
        self.attr_name = None
        self.dissolve = dissolve

    def __set_name__(self, spec_cls: Type, attr_name: str):
        self.spec_cls = spec_cls
        self.attr_name = attr_name

    def __get__(self, instance: Any, spec_cls: Type = None) -> Callable:
        if self.dissolve:
            setattr(spec_cls, self.name, self.method)
        if instance is not None:
            return types.MethodType(self.method, instance)
        return self.method

    @property
    def name(self) -> str:
        return self.method_name or self.attr_name

    @cached_property
    def method(self) -> Callable:
        return self.build_method()

    @property
    @abstractmethod
    def method_name(self) -> str:
        ...  # pragma: no cover

    @abstractmethod
    def build_method(self) -> Callable:
        ...  # pragma: no cover


class AttrMethodDescriptor(MethodDescriptor):  # pylint: disable=abstract-method
    """
    A `MethodDescriptor` for methods of an attribute. This class adds one
    attribe `attr_spec`, which allows the descriptor to build a tailored method
    for a given attribute.

    Attributes:
        attr_spec: The `Attr` instance for the attribute with which this method
            is supposed to interact.
    """

    def __init__(self, attr_spec: Attr, spec_cls: Type = None, dissolve: bool = True):
        super().__init__(spec_cls=spec_cls, dissolve=dissolve)
        self.attr_spec = attr_spec
