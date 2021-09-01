import types
from abc import ABCMeta, abstractmethod, abstractproperty

from cached_property import cached_property


class MethodDescriptor(metaclass=ABCMeta):
    def __init__(self, spec_cls=None, dissolve=True):
        self.spec_cls = spec_cls
        self.dissolve = dissolve

    def __set_name__(self, spec_cls, name):
        self.spec_cls = spec_cls
        self.name = name

    def __get__(self, instance, spec_cls=None):
        if self.dissolve:
            setattr(spec_cls, self.name, self.method)
        if instance is not None:
            return types.MethodType(self.method, instance)
        return self.method

    @cached_property
    def method(self):
        return self.build_method()

    @abstractproperty
    def name(self):
        ...

    @abstractmethod
    def build_method(self):
        ...


class AttrMethodDescriptor(MethodDescriptor):
    def __init__(self, attr_spec, spec_cls=None, dissolve=True):
        super().__init__(spec_cls=spec_cls, dissolve=dissolve)
        self.attr_spec = attr_spec
