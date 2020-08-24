from __future__ import annotations

import copy
import functools
import inspect
import textwrap
import typing
from inspect import cleandoc, Signature, Parameter
from typing import Any, Callable, Dict, Iterable, Type, Tuple, Union

import inflect


# Sentinel for unset inputs to spec_class methods
class _MissingType:

    def __bool__(self):
        return False

    def __repr__(self):
        return "MISSING"


MISSING = _MissingType()


class FrozenInstanceError(RuntimeError):
    pass


class spec_class:
    """
    A class decorator that adds `with_<field>`, `transform_<field>` and
    `without_<field>` methods to a class in order to simplify the incremental
    building and mutating of specification objects. By default these methods
    return a new instance decorated class, with the appropriate field mutated.

    It can be used directly on a class, for example:
    >>> @spec_class
    >>> class MyClass:
    >>>     pass
    or can be passed arguments (see the constructor for argument details), for
    example:
    >>> @spec_class('my_field', _key='my_key_field')
    >>> class MyClass:
    >>>     pass

    For each attribute that `spec_cls` is told to manage (if not explicitly
    told, it will manage all attributes that have a type annotation), `spec_cls`
    will add a subset of the following methods (depending on the type of each
    attribute):

    - all types:
        - `with_<attribute>(...)`: Update the attribute value.
        - `transform_<attribute>(...)`: Update the attribute value by calling
            a passed function on the existing value.
    - collection types (list, set, dict):
        - `with_<singular_noun_for_attribute>(...)`: Add/modify a member of the
            collection.
        - `transform_<singular_noun_for_attribute>(...)`: Update a member of a
            collection by transforming an existing member.
        - `without_<singular_noun_for_attribute>(...)`: Remove a member of a
            collection.

    If the attribute type (or type stored by a collection) is also decorated by
    `spec_cls`, then additional arguments will be exposed in the methods to
    directly modify nested structure. For example, if an attribute `foos` has
    type `List[Foo]`, and `Foo` is a class decorated by `spec_class`, then the
    method `with_foo` method will have signature:
    `with_foo(<spec>, *, index=MISSING, insert=False, replace=False, <all attributes of foo>=MISSING)`

    If the attribute type (or type stored by a collection) is annoted by
    `spec_cls` and a key attribute has been specified, then in collections the
    key of the element can additionally be used to directly look up elements.

    For more information, you can look up the generated docstrings on any of
    these methods.

    Notes:
        * `spec_cls` "upgrades" all classes to be dataclasses. As always,
            if you have already implemented __init__, it won't be overridden.
        * Any attribute passed to `spec_cls` (or all attributes if none are
            explicitly passed to the constructor) should be both gettable and
            settable (i.e., no read-only properties). Where this is not
            satisfied you will need to implement your own `with_*`, `transform_*`
            and `without_*` methods (`spec_cls` will never clobber existing
            methods).
        * For any attribute managed by `spec_cls`, it should be possible to
            construct an instance of the decorated class using
            `cls(**attributes)`. This is used whenever a decorated class refers
            to other types decorated by `spec_cls`.

    Examples:
    (1) Simple example
        @spec_class
        class Foo:
            key: str
            value: int

        @SpecClass(foo=Foo)
        class Bar:
            foo: Foo = Foo('k', 1)

        Bar().with_foo(Foo('k2', 2)).foo  # Foo('k2', 2)
        Bar().with_foo(value=3).foo  # Foo('k', 3)
        Bar().transform_foo(lambda x: x.with_value(10)).foo  # Foo('k', 10)

    (2) A class demonstrating all functionalities. You can experiment with this
        class and/or look up its docstrings in order to understand how
        everything works.

        @spec_class
        class UnkeyedSpec:
            nested_scalar: int = 1
            nested_scalar2: str = 'original value'

        @spec_class(_key='key')
        class KeyedSpec:
            key: str = 'key'
            nested_scalar: int = 1
            nested_scalar2: str = 'original value'


        @spec_class(_key='key')
        class Spec:
            key: str = None
            scalar: int = None
            list_values: List[int] = None
            dict_values: Dict[str, int] = None
            set_values: Set[str] = None
            spec: UnkeyedSpec = None
            spec_list_items: List[UnkeyedSpec] = None
            spec_dict_items: Dict[str, UnkeyedSpec] = None
            keyed_spec_list_items: List[KeyedSpec] = None
            keyed_spec_dict_items: Dict[str, KeyedSpec] = None
            recursive: Spec = None

    For more complete examples, refer to the method docstrings, or to the unit
    tests which thoroughly test example (2) above.
    """

    INFLECT_ENGINE = inflect.engine()

    def __new__(cls, *args, **kwargs):
        """
        Handle un-annotated case where the class to be decorated is passed
        directly to the `spec_class` constructor, for example:
        >>> @spec_class
        >>> class MyClass:
        >>>     pass
        """
        if len(args) == 1 and isinstance(args[0], type):
            return spec_class()(args[0])
        return super().__new__(cls)

    def __init__(
            self, *attrs: str, _key: str = None, _skip: Iterable[str] = None, _deepcopy: bool = None, _frozen: bool = False,
            _init: bool = True, _repr: bool = True, _eq: bool = True, **attrs_typed: Any
    ):
        """
        Args:
            *attrs: The attrs for which this `spec_cls` should add helper
                methods.
            _key: The name of the attribute which can be used to uniquely
                identify a particular specification.
            _skip: Attributes which should not be considered by this `spec_cls`.
                If `None`, and `attrs` and/or `attrs_typed` are specified, then
                it is assumed that all attributes not listed should be skipped.
                To interpret passed `attrs` and `attrs_typed` as incremental/
                overrides, pass a (potentially empty) iterable.
            _deepcopy: Whether to do a deep or shallow copy when doing
                non-inplace mutations. This is valuable when deepcopying is
                memory intensive, and when mutations *only* occur via the
                helper methods generated by `spec_class`. This also changes the
                behavior of the constructor (if deepcopy is True, a copy of
                incoming attributes is made before assignment to the attribute).
                If not specified, and not inherited from a subclass, this will
                default to `True`.
            _frozen: Whether to disallow direct modifications of attributes. If
                not specified and not inherited from parent class, this will
                default to `False`.
            _init: Whether to add an `__init__` method if one does not already
                exist.
            _repr: Whether to add a `__repr__` method if one does not already
                exist.
            _eq: Whether to add an `__eq__` method if one does not already
                exist.
            **attrs_typed: Additional attributes for which this `spec_cls`
                should add helper methods, with the type of the attr taken to be
                as specified, overriding (if present) any other type annotations
                for that attribute (e.g. List[int], Dict[str, int], Set[int], etc).
        """
        self.inherit_annotations = not (attrs or attrs_typed) or _skip is not None
        self.key = _key
        self.attrs = {
            **{attr: Any for attr in attrs},
            **attrs_typed
        }
        self.skip = set(_skip or set())
        self.spec_cls_methods = {
            '__init__': _init,
            '__repr__': _repr,
            '__spec_class_repr__': _repr,
            '__eq__': _eq,
            '__getattr__': True,
            '__setattr__': True,
            '__delattr__': True,
        }
        self.deepcopy = _deepcopy
        self.frozen = _frozen

        # Check for private attr specification, and if found, raise!
        private_attrs = [attr for attr in self.attrs if attr.startswith('_')]
        if private_attrs:
            raise ValueError(f"`spec_cls` cannot be used to generate helper methods for private attributes (got: {private_attrs}).")

    def __call__(self, spec_cls: type) -> type:
        """
        Add helper methods for all (or specified) attributes.

        Args:
            spec_cls: The decorated class.

        Returns:
            `spec_cls`, with the helper methods added.
        """
        # Attrs to be considered are those explicitly passed into constructor, or if none,
        # all of the type annotated fields if the class is not a subclass of an already
        # annotated spec class, or else none.
        managed_attrs = set(self.attrs)
        if self.inherit_annotations:
            managed_attrs.update({
                attr
                for attr in getattr(spec_cls, "__annotations__", {})
                if (
                    not attr.startswith('_')
                    and attr not in self.skip
                    and not (
                        isinstance(getattr(spec_cls, attr, None), property)
                        and getattr(spec_cls, attr).fset is None
                    )
                )
            })

        spec_cls.__is_spec_class__ = True
        spec_cls.__spec_class_key__ = self.key
        spec_cls.__spec_class_deepcopy__ = getattr(spec_cls, '__spec_class_deepcopy__', True if self.deepcopy is None else self.deepcopy)
        spec_cls.__spec_class_frozen__ = getattr(spec_cls, '__spec_class_frozen__', False if self.frozen is None else self.frozen)

        # Update annotations
        if not hasattr(spec_cls, '__annotations__'):
            spec_cls.__annotations__ = {}
        if self.key and self.key not in spec_cls.__annotations__:
            spec_cls.__annotations__[self.key] = self.attrs.get(self.key, Any)
        spec_cls.__annotations__.update({
            attr: annotation
            for attr, annotation in self.attrs.items()
            if attr not in spec_cls.__annotations__  # Do not override class annotations
        })

        # Generate and record managed annotations subset
        parsed_type_hints = typing.get_type_hints(spec_cls, localns={spec_cls.__name__: spec_cls})
        spec_cls.__spec_class_annotations__ = getattr(spec_cls, '__spec_class_annotations__', {}).copy()
        spec_cls.__spec_class_annotations__.update({
            attr: self.attrs[attr] if self.attrs.get(attr, Any) is not Any else parsed_type_hints.get(attr, Any)
            for attr in spec_cls.__annotations__
            if attr in ({self.key} | managed_attrs).difference([None])
        })

        # Register class-level methods
        self.register_methods(spec_cls, self.get_methods_for_spec_class(spec_cls, self.spec_cls_methods))

        self._validate_spec_cls(spec_cls)

        # For each new attribute to be managed by `spec_cls`, generate helper methods.
        for attr_name in managed_attrs:
            self.register_methods(spec_cls, self.get_methods_for_attribute(
                spec_cls, attr_name, attr_type=spec_cls.__spec_class_annotations__[attr_name]
            ))

        return spec_cls

    @classmethod
    def _validate_spec_cls(cls, spec_cls):
        spec_annotations = spec_cls.__spec_class_annotations__

        # Check that attribute types are satisfied by class defaults
        for attr_name, attr_type in spec_annotations.items():
            if (
                attr_name in spec_cls.__dict__
                and not inspect.isdatadescriptor(spec_cls.__dict__[attr_name])
                and not cls._check_type(spec_cls.__dict__[attr_name], attr_type)
            ):
                raise TypeError(f"Class default `{repr(spec_cls.__dict__[attr_name])}` for `{spec_cls.__name__}.{attr_name}` does not match annotation type `{attr_type}`.")

        # Check that constructor is present for all managed keys.
        init_sig = Signature.from_callable(spec_cls.__init__)
        missing_args = set(spec_annotations).difference(init_sig.parameters)

        if missing_args:
            raise ValueError(f"`{spec_cls.__name__}.__init__()` is missing required arguments to populate attributes: {missing_args}.")

    @classmethod
    def get_methods_for_spec_class(cls, spec_cls: type, methods_filter: Dict[str, bool]) -> Dict[str, Callable]:
        """
        Generate any required `__init__`, `__repr__` and `__eq__` methods. Will
        only be added if these methods do not already exist on the class.
        """
        def init_impl(self, **kwargs):
            copier = copy.deepcopy if self.__spec_class_deepcopy__ else lambda x: x
            for attr in self.__spec_class_annotations__:
                if attr in kwargs:
                    cls._with_attr(self, attr, copier(kwargs[attr]), inplace=True)
                else:
                    attr_value = getattr(self.__class__, attr, MISSING)
                    if inspect.isfunction(attr_value) or inspect.isdatadescriptor(attr_value):
                        continue  # Methods will already be bound to instance from class
                    elif attr_value is not MISSING:
                        cls._with_attr(self, attr, copier(attr_value), inplace=True)

        def __repr__(self, include_attrs=None, indent=None, indent_threshold=100):
            """
            Args:
                include_attrs: An ordered iterable of attrs to include in the
                    representation.
                indent: Whether to indent. If `True`, indenting is always
                    performed. If `False`, indenting is never performed. If
                    `None`, indenting is performed when output otherwise exceeds
                    `indent_threshold` characters. (default: None)
                indent_threshold: The threshold at which to switch to indented
                    representations (see above).
            """
            include_attrs = include_attrs or list(self.__spec_class_annotations__)

            def object_repr(obj, indent=False):
                if inspect.ismethod(obj) and obj.__self__ is self:
                    return f"<bound method {obj.__name__} of self>"
                if hasattr(obj, '__repr__') and 'indent' in Signature.from_callable(obj.__repr__).parameters:
                    return obj.__repr__(indent=indent)

                if indent:
                    if isinstance(obj, list):
                        if not obj:
                            return "[]"
                        items_repr = textwrap.indent(",\n".join([object_repr(item, indent=indent) for item in obj]), '    ')
                        return f"[\n{items_repr}\n]"
                    if isinstance(obj, dict):
                        if not obj:
                            return "{}"
                        items_repr = textwrap.indent(",\n".join([f"{repr(key)}: {object_repr(item, indent=indent)}" for key, item in obj.items()]), '    ')
                        return f"{{\n{items_repr}\n}}"
                    if isinstance(obj, set):
                        if not obj:
                            return "set()"
                        items_repr = textwrap.indent(",\n".join([object_repr(item, indent=indent) for item in obj]), '    ')
                        return f"{{\n{items_repr}\n}}"

                return repr(obj)

            # Collect unindented representations
            if not indent:
                unindented_attrs = ', '.join([
                    f"{attr}={object_repr(getattr(self, attr, MISSING))}"
                    for attr in include_attrs
                ])
                unindented_repr = f"{self.__class__.__name__}({unindented_attrs})"
                if indent is False or (len(unindented_repr) <= indent_threshold and not any('\n' in attr_repr for attr_repr in unindented_attrs)):
                    return unindented_repr

            # Collected indented representation
            indented_attrs = textwrap.indent(',\n'.join([
                f"{attr}={object_repr(getattr(self, attr, MISSING), indent=True)}"
                for attr in include_attrs
            ]), '    ')
            return f"{self.__class__.__name__}(\n{indented_attrs}\n)"

        def __eq__(self, other):
            if not isinstance(other, self.__class__):
                return False
            for attr in self.__spec_class_annotations__:
                value_self = getattr(self, attr, MISSING)
                value_other = getattr(other, attr, MISSING)
                if inspect.ismethod(value_self) and inspect.ismethod(value_other):
                    return value_self.__func__ is value_other.__func__
                if value_self != value_other:
                    return False
            return True

        def __getattr__(self, attr):
            if attr in self.__spec_class_annotations__ and attr not in self.__dict__:
                raise AttributeError(f"`{self.__class__.__name__}.{attr}` has not yet been assigned a value.")
            scls = self.__class__
            while getattr(scls.__getattr__, '__module__', None) == cls.__module__:
                scls = scls.mro()[1]
            return scls.__getattr__(self, attr)  # pragma: no cover; pylint: disable=bad-super-call

        def __setattr__(self, attr, value, force=False):
            # Abort if frozen
            if not force and self.__spec_class_frozen__:
                raise FrozenInstanceError(f"Cannot mutate attribute `{attr}` of frozen Spec Class `{self}`.")

            # Check attr type if managed attribute
            if force or attr not in self.__spec_class_annotations__ or not hasattr(self, f'with_{attr}'):
                scls = self.__class__
                while getattr(scls.__setattr__, '__module__', None) == cls.__module__:
                    scls = scls.mro()[1]
                scls.__setattr__(self, attr, value)  # pylint: disable=bad-super-call
            else:
                getattr(self, f'with_{attr}')(value, _inplace=True)

        def __delattr__(self, attr, force=False):
            # Abort if frozen
            if not force and self.__spec_class_frozen__:
                raise FrozenInstanceError(f"Cannot mutate attribute `{attr}` of frozen Spec Class `{self}`.")

            scls = self.__class__
            while getattr(scls.__delattr__, '__module__', None) == cls.__module__:
                scls = scls.mro()[1]
            return scls.__delattr__(self, attr)  # pylint: disable=bad-super-call

        spec_class_key = spec_cls.__spec_class_key__
        key_default = Parameter.empty
        if spec_class_key:
            key_default = getattr(spec_cls, spec_class_key, Parameter.empty)
            if inspect.isfunction(key_default) or inspect.isdatadescriptor(key_default):
                key_default = Parameter.empty

        methods = {
            '__init__': (
                _MethodBuilder('__init__', init_impl)
                .with_preamble(f"Initialise this `{spec_cls.__name__}` instance.")
                .with_arg(
                    spec_class_key, f"The value to use for the `{spec_class_key}` key attribute.",
                    default=key_default, annotation=spec_cls.__spec_class_annotations__.get(spec_class_key),
                    only_if=spec_class_key
                )
                .with_spec_attrs_for(spec_cls, defaults=True)
            ),
            '__repr__': __repr__,
            '__spec_class_repr__': __repr__,
            '__eq__': __eq__,
            '__getattr__': __getattr__,
            '__setattr__': __setattr__,
            '__delattr__': __delattr__,
        }
        return {
            name: method
            for name, method in methods.items()
            if methods_filter.get(name, False)
        }

    def get_methods_for_attribute(self, spec_cls: type, attr_name: str, attr_type: Type) -> Dict[str, Callable]:
        """
        Return the methods that should be added to `spec_cls` for the given
        `attr_name` and `attr_type`.

        Args:
            spec_cls: The decorated class for which methods should be generated.
            attr_name: The name of the attribute for which methods should be
                generated.
            attr_type: The type of the attribute (used to determine which
                methods are generated).

        Returns:
            A dictionary of methods (keyed by method name).
        """
        methods = self._get_methods_for_scalar(
            spec_cls, attr_name, attr_type,
            is_collection=self._type_match(attr_type, (list, dict, set))
        )
        if self._type_match(attr_type, list):
            methods.update(self._get_methods_for_list(spec_cls, attr_name, attr_type))
        elif self._type_match(attr_type, dict):
            methods.update(self._get_methods_for_dict(spec_cls, attr_name, attr_type))
        elif self._type_match(attr_type, set):
            methods.update(self._get_methods_for_set(spec_cls, attr_name, attr_type))
        return methods

    @classmethod
    def register_methods(cls, spec_cls: type, methods: Dict[str, Callable]):
        """
        Register nominated methods onto `spec_cls`. Methods will not be added if
        they already exist on the class.

        Args:
            spec_cls: The decorated class.
            methods: A dictionary of methods keyed by name.
        """
        for name, method in methods.items():
            cls.register_method(spec_cls, name, method)

    @staticmethod
    def register_method(spec_cls: type, name: str, method: Callable):
        """
        Add a method to the decorated class, and name it `name`. Do nothing if a
        method by this name already exists.

        Args:
            spec_cls: Decorated class.
            name: The name of the method to add.
            method: The method to add.
        """
        if name in spec_cls.__dict__:
            return
        if isinstance(method, _MethodBuilder):
            method = method.build()
        setattr(spec_cls, name, method)

    # Type checking and validation helpers

    @staticmethod
    def _type_match(type_input: Type, type_reference: type) -> bool:
        """
        Check whether `type_input` matches `type_reference`, that latter of
        which is permitted to be a sequence of multiple values; but cannot be
        a parameterized generic type.
        """
        while hasattr(type_input, '__origin__'):
            type_input = type_input.__origin__
        return isinstance(type_input, type) and issubclass(type_input, type_reference)

    @classmethod
    def _check_type(cls, value: Any, attr_type: Type) -> bool:
        """
        Check whether a given object `value` matches the provided `attr_type`.
        """
        if attr_type is Any:
            return True

        if hasattr(attr_type, '__origin__'):  # we are dealing with a `typing` object.

            if attr_type.__origin__ is Union:
                return any(cls._check_type(value, type_) for type_ in attr_type.__args__)

            if isinstance(attr_type, typing._GenericAlias):  # pylint: disable=protected-access
                if not isinstance(value, attr_type.__origin__):
                    return False
                if attr_type._name in ('List', 'Set') and not isinstance(attr_type.__args__[0], typing.TypeVar):  # pylint: disable=protected-access
                    for item in value:
                        if not cls._check_type(item, attr_type.__args__[0]):
                            return False
                elif attr_type._name == 'Dict' and not isinstance(attr_type.__args__[0], typing.TypeVar):  # pylint: disable=protected-access
                    for k, v in value.items():
                        if not cls._check_type(k, attr_type.__args__[0]):
                            return False
                        if not cls._check_type(v, attr_type.__args__[1]):
                            return False
                return True

            return isinstance(value, attr_type.__origin__)  # pragma: no cover; This is here as a fallback currently, just in case!

        return isinstance(value, attr_type)

    @classmethod
    def _get_collection_item_type(cls, container_type: Type) -> Type:
        """
        Return the type of object inside a typing container (List, Set, Dict),
        or `None` if this isn't annotated.
        """
        if not hasattr(container_type, '__args__'):  # i.e. this is not a `typing` container
            return Any

        item_type = Any
        if cls._type_match(container_type, dict) and len(container_type.__args__) == 2:
            item_type = container_type.__args__[1]
        elif len(container_type.__args__) == 1:
            item_type = container_type.__args__[0]
        if isinstance(item_type, typing.TypeVar):
            item_type = Any
        return item_type

    @classmethod
    def _get_spec_class_for_type(cls, attr_type: Type, allow_polymorphic=False) -> Union[Type, None]:
        """
        Get the spec class to associated with a given attribute type. This is
        useful when `attr_type` is a polymorphic type, e.g.
        Union[SpecClass, str]. It works by finding the spec class type in the
        polymorphic type. If there is not exactly one spec class type, `None` is
        returned.
        """
        if getattr(attr_type, '__is_spec_class__', False):
            return attr_type
        if allow_polymorphic and getattr(attr_type, '__origin__', None) is Union:
            spec_classes = [
                typ
                for typ in attr_type.__args__
                if getattr(typ, '__is_spec_class__', False)
            ]
            if len(spec_classes) == 1:
                return spec_classes[0]
        return None

    @staticmethod
    def _attr_type_label(attr_type: Type) -> str:
        """
        Generate the label to be used to describe an `attr_type` in generated
        user documentation. Since we care about the output of this method when
        `attr_type` points to a `spec_cls` decorated type, we don't make this
        method general.
        """
        if isinstance(attr_type, type):
            return attr_type.__name__
        return "object"

    # High-level mutation helpers

    @classmethod
    def _with_attr(cls, self: Any, name: str, value: Any, inplace: bool = False) -> Any:
        """
        Set attribute `name` of `self` to `value`, and return the mutated
        instance. If `inplace` is `False`, copy the instance before assigning
        the new attribute value.
        """
        if value is MISSING:
            return self
        if not inplace:
            self = (copy.deepcopy if self.__spec_class_deepcopy__ else copy.copy)(self)
        attr_type = self.__spec_class_annotations__[name]
        if not cls._check_type(value, attr_type):
            raise TypeError(f"Attempt to set `{self.__class__.__name__}.{name}` with an invalid type [got `{repr(value)}`; expecting `{attr_type}`].")
        try:
            if 'force' in inspect.Signature.from_callable(self.__setattr__).parameters:
                self.__setattr__(name, value, force=True)
            else:
                setattr(self, name, value)  # pragma: no cover
        except AttributeError:
            raise AttributeError(f"Cannot set `{self.__class__.__name__}.{name}` to `{value}`. Is this a property without a setter?")
        return self

    @staticmethod
    def _get_updated_value(
            old_value: Any, *, new_value: Any = MISSING, constructor: Union[Type, Callable] = None, transform: Callable = None,
            attrs: Dict[str, Any] = None, attr_transforms: Dict[str, Callable] = None, replace: bool = False
    ) -> Any:
        """
        General strategy for generating an updated value from an old value, and
        either a new value or a combination of new attribute values and/or
        transforms.
        """
        mutate_safe = False

        # Start with `old_value`
        value = old_value

        # If `new_value` is not `MISSING`, use it.
        if new_value is not MISSING:
            value = new_value

        # If `value` is `MISSING`, or `replace` is True, and we have a
        # constructor, create a new instance with existing attrs. Any attrs not
        # found in the constructor will be assigned later.
        if (value is MISSING or replace) and constructor is not None:
            mutate_safe = True
            while hasattr(constructor, '__origin__'):
                constructor = constructor.__origin__
            try:
                constructor_args = set(inspect.Signature.from_callable(constructor).parameters)
            except ValueError:
                constructor_args = set()
            value = constructor(**{attr: value for attr, value in (attrs or {}).items() if attr in constructor_args})
            attrs = {
                attr: value
                for attr, value in (attrs or {}).items()
                if attr not in constructor_args
            }

        # If there are any attributes to apply to our value, we do so here,
        # special casing any spec classes.
        if value not in (None, MISSING) and attrs:
            if not mutate_safe:
                value = copy.deepcopy(value)
                mutate_safe = True
            if getattr(value, '__is_spec_class__', False):
                for attr, attr_value in attrs.items():
                    if attr not in value.__spec_class_annotations__:
                        raise TypeError(f"Invalid attribute `{attr}` for spec class `{value.__class__.__name__}`.")
                    setter = getattr(value, f'with_{attr}', None)
                    if setter is None:
                        setattr(value, attr, attr_value)  # pragma: no cover; This should never happen, but it is here just in case!
                    else:
                        value = setter(attr_value, _inplace=True)
            else:
                for attr, attr_value in attrs.items():
                    setattr(value, attr, attr_value)
        elif attrs:
            raise ValueError("Cannot use attrs on a missing value without a constructor.")

        # If `transform` is provided, transform `value`
        if transform:
            value = transform(value)

        # If `attr_transforms` is provided, transform attributes
        if attr_transforms:
            if not mutate_safe:
                value = copy.deepcopy(value)
            if getattr(value, '__is_spec_class__', False):
                for attr, attr_transform in attr_transforms.items():
                    if attr not in value.__spec_class_annotations__:
                        raise TypeError(f"Invalid attribute `{attr}` for spec class `{value.__class__.__name__}`.")
                    transformer = getattr(value, f'transform_{attr}', None)
                    if transformer is None:  # pragma: no cover; This should never happen, but it is here just in case!
                        setattr(value, attr, attr_transform(getattr(value, attr)))
                    else:
                        value = transformer(attr_transform, _inplace=True)
            else:
                for attr, attr_transform in attr_transforms.items():
                    setattr(value, attr, attr_transform(getattr(value, attr)))

        return value

    @classmethod
    def _get_updated_collection(cls,
            collection: Any, collection_constructor: Union[Type, Callable], value_or_index: Any, extractor: Callable, inserter: Callable, *,
            new_item: Any = MISSING, constructor: Union[Type, Callable] = None, transform: Callable = None,
            attrs: Dict[str, Any] = None, attr_transforms: Dict[str, Callable] = None, replace: bool = False
    ) -> Any:
        """
        General strategy for mutation elements within a collection, which wraps
        `cls._get_updated_value`. Extraction and insertion are handled by the
        functions passed in as `extractor` and `inserter` functions respectively.

        Extractor functions must have a signature of: `(collection, value_or_index)`,
        and output the index and value of existing items in the collection.

        Inserter functions must have a signature of: `(collection, index, new_item)`,
        and insert the given item into the collection appropriately. `index` will
        be the same `index` as that output by the extractor, and is not otherwise
        interpreted.
        """
        if collection is MISSING:
            collection = collection_constructor()
        else:
            collection = copy.deepcopy(collection)
        index, old_item = extractor(collection, value_or_index)
        new_item = cls._get_updated_value(old_item, new_value=new_item, constructor=constructor, transform=transform, attrs=attrs, attr_transforms=attr_transforms, replace=replace)
        inserter(collection, index, new_item)
        return collection

    # Scalar methods
    @classmethod
    def _get_methods_for_scalar(cls, spec_cls: type, attr_name: str, attr_type: Type, is_collection: bool = False):
        attr_spec_type = cls._get_spec_class_for_type(attr_type)

        def with_attr(self, _new_value=MISSING, *, _replace=False, _inplace=False, **attrs):
            _new_value = getattr(self, f'_prepare_{attr_name}', lambda x, attrs: x)(_new_value, attrs)
            old_value = getattr(self, attr_name, MISSING)
            new_value = cls._get_updated_value(old_value, new_value=MISSING if is_collection else _new_value, constructor=attr_type, attrs=attrs, replace=_replace)
            self = cls._with_attr(self, attr_name, new_value, inplace=_inplace)
            if is_collection:
                try:
                    self = cls._populate_collection(self, attr_name, attr_type, _new_value, inplace=_inplace)
                finally:
                    if _inplace:
                        cls._with_attr(self, attr_name, old_value, inplace=_inplace)
            return self

        def transform_attr(self, _transform=None, *, _inplace=False, **attr_transforms):
            old_value = getattr(self, attr_name, MISSING)
            new_value = cls._get_updated_value(old_value, transform=_transform, constructor=attr_type, attr_transforms=attr_transforms)
            return cls._with_attr(self, attr_name, new_value, inplace=_inplace)

        or_its_attributes = " or its attributes" if attr_spec_type else ""
        return {
            f'with_{attr_name}': (
                _MethodBuilder(f'with_{attr_name}', with_attr)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with `{attr_name}`{or_its_attributes} mutated.")
                .with_arg("_new_value", f"The new value for `{attr_name}`.", default=MISSING, annotation=attr_type)
                .with_arg("_replace", f"If True, build a new {cls._attr_type_label(attr_type)} from scratch. Otherwise, modify the old value.",
                          only_if=attr_spec_type, default=False, keyword_only=True, annotation=bool)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(attr_type, template=f"An optional new value for {attr_name}.{{}}.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'transform_{attr_name}': (
                _MethodBuilder(f'transform_{attr_name}', transform_attr)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with `{attr_name}`{or_its_attributes} transformed.")
                .with_arg("_transform", f"A function that takes the old value for {attr_name} as input, and returns the new value.",
                          default=MISSING if attr_spec_type else Parameter.empty, annotation=Callable)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(attr_type, template=f"An optional transformer for {attr_name}.{{}}.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
        }

    # Collection methods

    @classmethod
    def _get_singular_form(cls, attr_name):
        """
        Determine the singular form of an attribute name, for use in the naming
        of collection helper methods.
        """
        singular = cls.INFLECT_ENGINE.singular_noun(attr_name)
        if not singular or singular == attr_name:
            return f"{attr_name}_item"
        return singular

    @classmethod
    def _get_spec_key(cls, spec_cls, item, attrs=None):
        """
        Get the key associated with a spec class isntance or from attrs.
        """
        assert hasattr(spec_cls, '__spec_class_key__'), f"`{spec_cls}` is not a keyed spec class instance."
        if isinstance(item, spec_cls):
            return getattr(item, spec_cls.__spec_class_key__, MISSING)
        if cls._check_type(item, spec_cls.__spec_class_annotations__[spec_cls.__spec_class_key__]):
            return item
        return (attrs or {}).get(spec_cls.__spec_class_key__, MISSING)

    @classmethod
    def _populate_collection(cls, self, attr_name, attr_type, collection, *, inplace=False):
        singular_name = cls._get_singular_form(attr_name)
        item_type = cls._get_collection_item_type(attr_type)
        item_spec_type = cls._get_spec_class_for_type(item_type)
        item_spec_type_is_keyed = item_spec_type and item_spec_type.__spec_class_key__ is not None
        with_item = getattr(self.__class__, f'with_{singular_name}')

        if cls._type_match(attr_type, list) and isinstance(collection, list):
            for item in collection:
                self = with_item(self, item, _insert=True, _inplace=inplace)
        elif item_spec_type_is_keyed and cls._type_match(attr_type, dict) and isinstance(collection, (list, dict)):
            for value in collection.values() if isinstance(collection, dict) else collection:
                self = with_item(self, value, _inplace=inplace)
        elif cls._type_match(attr_type, dict) and isinstance(collection, (list, dict)):
            for key, value in collection.items():
                self = with_item(self, key, value, _inplace=inplace)
        elif cls._type_match(attr_type, set) and isinstance(collection, set):
            for item in collection:
                self = with_item(self, item, _inplace=inplace)
        else:
            cls._with_attr(self, attr_name, collection, inplace=inplace)

        return self

    @classmethod
    def _get_methods_for_list(cls, spec_cls: type, attr_name: str, attr_type: Type) -> Dict[str, Callable]:
        """
        Generate and return the methods for a list container. There are three
        scenarios dealt with here. They are when the container item type is:
        (1) a non-spec type.
        (2) another class decorated with `spec_cls` that does not have a key
            attribute.
        (3) another classed decorated with `spec_cls` that does have a key
            attribute.

        Each scenario progressively enriches the generated methods. From (1 -> 2)
        the methods garner the ability to mutate elements of the nested spec
        class directly. From (2 -> 3) the methods garner the ability to lookup
        items in the list by key (as well as integer).

        Notes: List containers do not support keyed specs with integer keys.
        """
        singular_name = cls._get_singular_form(attr_name)
        item_type = cls._get_collection_item_type(attr_type)
        item_spec_type = cls._get_spec_class_for_type(item_type)
        item_spec_type_is_keyed = item_spec_type and item_spec_type.__spec_class_key__ is not None

        # Check that keyed item type does not have an integral key
        def abort_due_to_integer_keys():
            raise ValueError(
                "List containers do not support keyed spec classes with integral keys. Check "
                f"`{spec_cls.__name__}.{attr_name}` and consider using a `Dict` container instead."
            )

        if item_spec_type_is_keyed:
            item_key_type = item_spec_type.__spec_class_annotations__[item_spec_type.__spec_class_key__]
            if cls._type_match(item_key_type, int):
                abort_due_to_integer_keys()

        def extractor(collection, value_or_index, by_index=False):
            if value_or_index is MISSING:
                return None, MISSING

            if by_index:
                if item_spec_type_is_keyed and not isinstance(value_or_index, int):
                    for i, item in enumerate(collection):
                        if isinstance(item, item_spec_type) and getattr(item, item_spec_type.__spec_class_key__) == value_or_index:
                            return i, item
                    return None, item_spec_type(**{item_spec_type.__spec_class_key__: value_or_index})
                return value_or_index, collection[value_or_index] if value_or_index is not None and value_or_index < len(collection) else MISSING

            if item_spec_type_is_keyed:
                if isinstance(value_or_index, item_spec_type):
                    value_or_index = getattr(value_or_index, item_spec_type.__spec_class_key__)
                for i, item in enumerate(collection):
                    if getattr(item, item_spec_type.__spec_class_key__) == value_or_index:
                        return i, item
                return None, item_spec_type(**{item_spec_type.__spec_class_key__: value_or_index})
            return collection.index(value_or_index), value_or_index

        def inserter(collection, index, new_item, insert=False):
            if not cls._check_type(new_item, item_type):
                raise ValueError(f"Attempted to add an invalid item `{repr(new_item)}` to `{spec_cls.__name__}.{attr_name}`. Expected item of type `{item_type}`.")
            if index is None:
                collection.append(new_item)
            elif insert:
                collection.insert(index, new_item)
            else:
                collection[index] = new_item
            if item_spec_type_is_keyed and isinstance(new_item, item_spec_type):
                key = getattr(new_item, item_spec_type.__spec_class_key__)
                if sum([1 for item in collection if isinstance(item, item_spec_type) and getattr(item, item_spec_type.__spec_class_key__) == key]) > 1:
                    raise ValueError(f"Adding {new_item} to list would result in more than instance with the same key: {repr(key)}.")

        def with_attr_item(self, _item=MISSING, *, _index=MISSING, _insert=False, _replace=False, _inplace=False, **attrs):
            _item = getattr(self, f'_prepare_{singular_name}', lambda x, attrs: x)(_item, attrs)
            old_value = getattr(self, attr_name, MISSING)

            if item_spec_type_is_keyed:
                if _index is MISSING:
                    _index = cls._get_spec_key(item_spec_type, _item, attrs)
                    if isinstance(_index, int):
                        abort_due_to_integer_keys()
                if _item is not MISSING and not isinstance(_item, item_spec_type):
                    _key = cls._get_spec_key(item_spec_type, _item, attrs)
                    if _key is not MISSING:
                        _item = (
                            item_spec_type(**{item_spec_type.__spec_class_key__: _item})
                            if extractor(old_value or [], _key, by_index=True)[0] is None else
                            MISSING
                        )

            new_value = cls._get_updated_collection(
                old_value, collection_constructor=list, value_or_index=_index, extractor=functools.partial(extractor, by_index=True), inserter=functools.partial(inserter, insert=_insert),
                new_item=_item, constructor=item_type, attrs=attrs, replace=_replace
            )
            return cls._with_attr(self, attr_name, new_value, inplace=_inplace)

        def transform_attr_item(self, _value_or_index, _transform, *, _by_index=False, _inplace=False, **attr_transforms):
            old_value = getattr(self, attr_name, MISSING)
            new_value = cls._get_updated_collection(
                old_value, collection_constructor=list, value_or_index=_value_or_index, extractor=functools.partial(extractor, by_index=_by_index), inserter=inserter,
                constructor=item_type, transform=_transform, attr_transforms=attr_transforms
            )
            return cls._with_attr(self, attr_name, new_value, inplace=_inplace)

        def without_attr_item(self, _value_or_index, *, _by_index=False, _inplace=False):
            old_value = getattr(self, attr_name, MISSING)
            new_value = copy.deepcopy(old_value)
            index, _ = extractor(new_value, _value_or_index, by_index=_by_index)
            del new_value[index]
            return cls._with_attr(self, attr_name, new_value, inplace=_inplace)

        # types for function signatures
        fn_item_type = item_type
        fn_index_type = int
        if item_spec_type_is_keyed:
            fn_item_type = Union[item_spec_type.__spec_class_annotations__[item_spec_type.__spec_class_key__], fn_item_type]
            fn_index_type = Union[item_spec_type.__spec_class_annotations__[item_spec_type.__spec_class_key__], fn_index_type]

        return {
            f'with_{singular_name}': (
                _MethodBuilder(f'with_{singular_name}', with_attr_item)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item added to or updated in `{attr_name}`.")
                .with_arg("_item", f"A new `{cls._attr_type_label(item_type)}` instance for {attr_name}.", default=MISSING, annotation=fn_item_type)
                .with_arg("_index", "Index for which to insert or replace, depending on `insert`; if not provided, append.", default=MISSING, keyword_only=True, annotation=fn_index_type)
                .with_arg("_insert", f"Insert item before {attr_name}[index], otherwise replace this index.", default=False, keyword_only=True, annotation=bool)
                .with_arg(
                    "_replace", f"If True, and if replacing an old item, build a new {cls._attr_type_label(item_type)} from scratch. Otherwise, apply changes on top of the old value.",
                    only_if=item_spec_type, default=False, keyword_only=True, annotation=bool
                )
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional new value for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'transform_{singular_name}': (
                _MethodBuilder(f'transform_{singular_name}', transform_attr_item)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item transformed in `{attr_name}`.")
                .with_arg("_value_or_index", "The value to transform, or (if `by_index=True`) its index.", annotation=Union[fn_item_type, fn_index_type])
                .with_arg("_transform", "A function that takes the old item as input, and returns the new item.", default=MISSING if item_spec_type else Parameter.empty, annotation=Callable)
                .with_arg("_by_index", "If True, value_or_index is the index of the item to transform.", keyword_only=True, default=False, annotation=bool)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional transformer for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'without_{singular_name}': (
                _MethodBuilder(f'without_{singular_name}', without_attr_item)
                .with_preamble(
                    f"Return a `{spec_cls.__name__}` instance identical to this one except with an item removed from `{attr_name}`."
                )
                .with_arg("_value_or_index", "The value to remove, or (if `by_index=True`) its index.", annotation=Union[fn_item_type, fn_index_type])
                .with_arg("_by_index", "If True, value_or_index is the index of the item to remove.", default=False, keyword_only=True, annotation=bool)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
        }

    @classmethod
    def _get_methods_for_dict(cls, spec_cls: type, attr_name: str, attr_type: Type) -> Dict[str, Callable]:
        """
        Generate and return the methods for a dict container. There are three
        scenarios dealt with here. They are when the container item type is:
        (1) a non-spec type.
        (2) another class decorated with `spec_cls` that does not have a key
            attribute.
        (3) another classed decorated with `spec_cls` that does have a key
            attribute.

        Each scenario progressively enriches the generated methods. From (1 -> 2)
        the methods garner the ability to mutate elements of the nested spec
        class directly. From (2 -> 3) the methods automatically infer the key
        from the passed item types (and the key parameter is explicitly removed).
        """
        singular_name = cls._get_singular_form(attr_name)
        item_type = cls._get_collection_item_type(attr_type)
        item_spec_type = cls._get_spec_class_for_type(item_type)
        item_spec_type_is_keyed = item_spec_type and item_spec_type.__spec_class_key__ is not None

        def extractor(collection, value_or_index):
            default = MISSING
            if item_spec_type_is_keyed:
                if isinstance(value_or_index, item_spec_type):
                    value_or_index = getattr(value_or_index, item_spec_type.__spec_class_key__)
                default = item_spec_type(**{item_spec_type.__spec_class_key__: value_or_index})
            return value_or_index, collection.get(value_or_index, default)

        def inserter(collection, index, new_item):
            if not cls._check_type(new_item, item_type):
                raise ValueError(f"Attempted to add an invalid item `{repr(new_item)}` to `{spec_cls.__name__}.{attr_name}`. Expected item of type `{item_type}`.")
            if item_spec_type_is_keyed:
                index = getattr(new_item, item_spec_type.__spec_class_key__)
            collection[index] = new_item

        def with_attr_item(self, _key=None, _value=None, _replace=False, _inplace=False, **attrs):
            _key, _value = getattr(self, f'_prepare_{singular_name}', lambda k, v, attrs: (k, v))(_key, _value, attrs)
            old_value = getattr(self, attr_name, MISSING)
            if item_spec_type_is_keyed:
                _key = cls._get_spec_key(item_spec_type, _value, attrs)
                _value = _value if cls._check_type(_value, item_spec_type) else MISSING
            new_value = cls._get_updated_collection(
                old_value, collection_constructor=dict, value_or_index=_key, extractor=extractor, inserter=inserter,
                new_item=_value, constructor=item_type, attrs=attrs, replace=_replace
            )
            return cls._with_attr(self, attr_name, new_value, inplace=_inplace)

        def transform_attr_item(self, _key, _transform, *, _inplace=False, **attr_transforms):
            old_value = getattr(self, attr_name, MISSING)
            new_value = cls._get_updated_collection(
                old_value, collection_constructor=list, value_or_index=_key, extractor=extractor, inserter=inserter,
                constructor=item_type, transform=_transform, attr_transforms=attr_transforms
            )
            return cls._with_attr(self, attr_name, new_value, inplace=_inplace)

        def without_attr_item(self, _key, *, _inplace=False):
            if item_spec_type_is_keyed and isinstance(_key, item_spec_type):
                _key = getattr(_key, item_spec_type.__spec_class_key__)
            old_value = getattr(self, attr_name, MISSING)
            new_value = copy.deepcopy(old_value)
            del new_value[_key]
            return cls._with_attr(self, attr_name, new_value, inplace=_inplace)

        # types for function signatures
        if item_spec_type_is_keyed:
            fn_key_type = fn_value_type = Union[item_spec_type.__spec_class_annotations__[item_spec_type.__spec_class_key__], item_type]
        else:
            fn_key_type = Any
            if hasattr(attr_type, '__args__') and not isinstance(attr_type.__args__[0], typing.TypeVar):
                fn_key_type = attr_type.__args__[0]
            fn_value_type = item_type

        return {
            f'with_{singular_name}': (
                _MethodBuilder(f'with_{singular_name}', with_attr_item)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item added to or updated in `{attr_name}`.")
                .with_arg("_key", "The key for the item to be inserted or updated.", annotation=fn_key_type, only_if=not item_spec_type_is_keyed)
                .with_arg("_value", f"A new `{cls._attr_type_label(item_type)}` instance for {attr_name}.", default=MISSING if item_spec_type else Parameter.empty, annotation=fn_value_type)
                .with_arg(
                    "_replace", f"If True, and if replacing an old item, build a new {cls._attr_type_label(item_type)} from scratch. Otherwise, apply changes on top of the old value.",
                    only_if=item_spec_type, default=False, keyword_only=True, annotation=bool
                )
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional new value for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'transform_{singular_name}': (
                _MethodBuilder(f'transform_{singular_name}', transform_attr_item)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item transformed in `{attr_name}`.")
                .with_arg("_key", "The key for the item to be inserted or updated.", annotation=fn_key_type)
                .with_arg("_transform", "A function that takes the old item as input, and returns the new item.", default=MISSING if item_spec_type else Parameter.empty, annotation=Callable)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional transformer for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'without_{singular_name}': (
                _MethodBuilder(f'without_{singular_name}', without_attr_item)
                .with_preamble(
                    f"Return a `{spec_cls.__name__}` instance identical to this one except with an item removed from `{attr_name}`."
                )
                .with_arg("_key", "The key of the item to remove.", annotation=fn_key_type)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
        }

    @classmethod
    def _get_methods_for_set(cls, spec_cls: type, attr_name: str, attr_type: Type) -> Dict[str, Callable]:
        """
        Generate and return the methods for a set container. There are three
        scenarios dealt with here. They are when the container item type is:
        (1) a non-spec type.
        (2) another class decorated with `spec_cls` that does not have a key
            attribute.

        From (1 -> 2) the methods garner the ability to mutate elements of the
        nested spec class directly. Note that sets do not have explicit support
        for keyed spec classes. Also note that for an `spec_cls` to work as the
        item type of a set, it must be hashable. If you set the hash to be the
        key value, then sets will automatically accommodate the required
        uniqueness of the keys.
        """
        singular_name = cls._get_singular_form(attr_name)
        item_type = cls._get_collection_item_type(attr_type)
        item_spec_type = cls._get_spec_class_for_type(item_type)

        def extractor(collection, value_or_index):
            return value_or_index, value_or_index if value_or_index in collection else MISSING

        def inserter(collection, index, new_item, replace=False):
            if not cls._check_type(new_item, item_type):
                raise ValueError(f"Attempted to add an invalid item `{repr(new_item)}` to `{spec_cls.__name__}.{attr_name}`. Expected item of type `{item_type}`.")
            if replace:
                collection.discard(index)
            collection.add(new_item)

        def with_attr_item(self, _item, *, _replace=False, _inplace=False, **attrs):
            _item = getattr(self, f'_prepare_{singular_name}', lambda x, attrs: x)(_item, attrs)
            old_value = getattr(self, attr_name, MISSING)
            new_value = cls._get_updated_collection(
                old_value, collection_constructor=set, value_or_index=_item, extractor=extractor, inserter=inserter,
                new_item=_item, constructor=item_type, attrs=attrs, replace=_replace
            )
            return cls._with_attr(self, attr_name, new_value, inplace=_inplace)

        def transform_attr_item(self, _item, _transform, *, _inplace=False, **attr_transforms):
            old_value = getattr(self, attr_name, MISSING)
            new_value = cls._get_updated_collection(
                old_value, collection_constructor=set, value_or_index=_item, extractor=extractor, inserter=functools.partial(inserter, replace=True),
                constructor=item_type, transform=_transform, attr_transforms=attr_transforms
            )
            return cls._with_attr(self, attr_name, new_value, inplace=_inplace)

        def without_attr_item(self, _item, *, _inplace=False):
            old_value = getattr(self, attr_name, MISSING)
            new_value = copy.deepcopy(old_value)
            new_value.discard(_item)
            return cls._with_attr(self, attr_name, new_value, inplace=_inplace)

        return {
            f'with_{singular_name}': (
                _MethodBuilder(f'with_{singular_name}', with_attr_item)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item added to `{attr_name}`.")
                .with_arg("_item", f"A new `{cls._attr_type_label(item_type)}` instance for {attr_name}.", default=MISSING if item_spec_type else Parameter.empty, annotation=item_type)
                .with_arg(
                    "_replace", f"If True, and if replacing an old item, build a new {cls._attr_type_label(item_type)} from scratch. Otherwise, apply changes on top of the old value.",
                    only_if=item_spec_type, default=False, keyword_only=True, annotation=bool
                )
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional new value for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'transform_{singular_name}': (
                _MethodBuilder(f'transform_{singular_name}', transform_attr_item)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item transformed in `{attr_name}`.")
                .with_arg("_item", "The value to transform.", annotation=item_type)
                .with_arg("_transform", "A function that takes the old item as input, and returns the new item.", default=MISSING if item_spec_type else Parameter.empty, annotation=Callable)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional transformer for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'without_{singular_name}': (
                _MethodBuilder(f'without_{singular_name}', without_attr_item)
                .with_preamble(
                    f"Return a `{spec_cls.__name__}` instance identical to this one except with an item removed from `{attr_name}`."
                )
                .with_arg("_item", "The value to remove.", annotation=item_type)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
        }


class _MethodBuilder:  # pragma: no cover; This is an internal helper class only; so long as `spec_class` works, we are golden!
    """
    Build a method based on its signature, allowing more restrictive wrappers
    to be built around a more general `implementation`, that is replete with
    user documentation and that throws sensible errors when users do the "wrong"
    thing with it.
    """

    def __init__(self, name: str, implementation: Callable):
        self.name = name
        self.implementation = implementation

        self.preamble = ""
        self.args = []
        self.returns = ""
        self.return_type = None
        self.notes = []
        self.parameters = [Parameter("self", Parameter.POSITIONAL_OR_KEYWORD)]
        self.parameters_sig_only = []

    # Signature related methods

    def with_arg(
            self, name: str, desc: str, default: Any = Parameter.empty, keyword_only: bool = False,
            annotation: Type = Parameter.empty, only_if: bool = True
    ):
        """
        Add argument to method.
        """
        if not only_if:
            return self

        self.args.append('\n'.join(textwrap.wrap(f"{name}: {desc}", subsequent_indent='    ')))
        self.parameters.append(Parameter(
            name,
            kind=Parameter.KEYWORD_ONLY if keyword_only else Parameter.POSITIONAL_OR_KEYWORD,
            default=default,
            annotation=annotation,
        ))

        return self

    def with_attrs(self, args: Dict[str, Type], template: str = "", defaults: Dict[str, Any] = None, only_if: bool = True):
        """
        Add **attrs to signature, and record valid keywords as specified in `args`.
        """
        if not only_if:
            return self

        # Remove any arguments that already exist in the function signature.
        args = args.copy()
        current_sig = self.signature
        for arg in list(args):
            if arg in current_sig.parameters:
                args.pop(arg)

        if not args:
            return self

        self.args.extend([
            "{}: {}".format(name, template.format(name)) for name in list(args)
        ])
        if not self.parameters_sig_only:
            self.parameters.append(Parameter('attrs', kind=Parameter.VAR_KEYWORD))
        defaults = defaults or {}
        self.parameters_sig_only.extend([
            Parameter(name, Parameter.KEYWORD_ONLY, annotation=arg_type, default=defaults.get(name))
            for name, arg_type in args.items()
        ])
        return self

    def with_spec_attrs_for(self, spec_cls: type, template: str = "", defaults=None, only_if: bool = True):
        """
        Add **attrs based on the attributes of a spec_class.
        """
        if not only_if or not getattr(spec_cls, '__is_spec_class__', False):
            return self
        if defaults is True:
            defaults = {
                attr: (
                    getattr(spec_cls, attr, MISSING)
                    if not inspect.isfunction(getattr(spec_cls, attr, None)) and not inspect.isdatadescriptor(getattr(spec_cls, attr, None)) else
                    MISSING
                )
                for attr in spec_cls.__spec_class_annotations__
            }
        return self.with_attrs(spec_cls.__spec_class_annotations__, template=template, defaults=defaults)

    def with_returns(self, desc: str, annotation: Type = Parameter.empty, only_if: bool = True):
        """
        Specify return type and description.
        """
        if not only_if:
            return self

        self.returns = desc
        self.return_type = annotation if annotation is not Parameter.empty else Any

        return self

    # Documentation-only related methods.

    def with_preamble(self, value: str, only_if: bool = True):
        """
        Set documentation preamble.
        """
        if not only_if:
            return self

        self.preamble = value
        return self

    def with_notes(self, *lines, only_if=True):
        if not only_if:
            return self

        self.notes.extend([
            '\n'.join(textwrap.wrap(line, subsequent_indent='    '))
            for line in lines
        ])
        return self

    # Extractors

    @property
    def docstring(self):
        docstring = ""
        if self.preamble:
            docstring += self.preamble + "\n"
        if self.args:
            docstring += "\nArgs:\n" + textwrap.indent("\n".join(self.args), "    ")
        if self.returns:
            docstring += "\nReturns:\n" + '\n'.join(textwrap.wrap(self.returns, initial_indent='    ', subsequent_indent='    '))
        if self.notes:
            docstring += "\nNotes:\n" + textwrap.indent("\n".join(self.notes), "    ")
        return cleandoc(docstring)

    @property
    def signature(self):
        """
        The signature to use when building the method.
        """
        return Signature(parameters=self.parameters)

    @property
    def signature_advertised(self):
        """
        The signature to advertise using method.__signature__ on the built method.
        """
        if self.parameters_sig_only:
            return Signature(parameters=self.parameters[:-1] + self.parameters_sig_only)
        return self.signature

    @staticmethod
    def __check_signature_conformance(sig_method: Signature, sig_impl: Signature) -> bool:
        """
        Check whether signatures conform to one another, assuming that the fields
        in `sig_method` are going to be passed by position for positional parameters,
        and then by name, to a function with signature `sig_impl`.
        """
        impl_has_var_args = False
        impl_has_var_kwargs = False

        # Check that implementation positional elements have values
        for impl_param in sig_impl.parameters.values():
            if impl_param.kind is Parameter.VAR_POSITIONAL:
                impl_has_var_args = True
            elif impl_param.kind is Parameter.VAR_KEYWORD:
                impl_has_var_kwargs = True
            elif (
                    impl_param.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
                    and impl_param.default is Parameter.empty
                    and impl_param.name not in sig_method.parameters
            ):
                return False

        # Check that all method parameters exist on implementation
        for method_param in sig_method.parameters.values():
            if method_param.kind is Parameter.VAR_POSITIONAL:
                if not impl_has_var_args:
                    return False
            elif method_param.kind is Parameter.VAR_KEYWORD:
                if not impl_has_var_kwargs:
                    return False
            elif method_param.name not in sig_impl.parameters:
                if method_param.kind is Parameter.POSITIONAL_ONLY or not impl_has_var_kwargs:
                    return False

        return True

    def build(self) -> Callable:
        """
        Generate and return the built method.
        """
        namespace = {}

        signature = self.signature
        impl_signature = Signature.from_callable(self.implementation)
        signature_advertised = self.signature_advertised

        if not self.__check_signature_conformance(signature, impl_signature):
            raise ValueError(f"Proposed method signature `{self.name}{signature}` is not compatible with implementation signature `implementation{impl_signature}`.")

        def validate_attrs(attrs):
            extra_attrs = set(attrs).difference([p.name for p in self.parameters_sig_only])
            if extra_attrs:
                raise TypeError(f"{self.name}() got unexpected keyword arguments: {repr(extra_attrs)}.")

        str_signature, defaults = self.__call_signature_str(signature)

        exec(textwrap.dedent(f"""
            from __future__ import annotations
            def {self.name}{str_signature} { "-> " + str(self.return_type.__name__) if self.return_type is not None else ""}:
                {"validate_attrs(attrs)" if self.parameters_sig_only else ""}
                return implementation({self.__call_implementation_str(self.signature)})
        """), {'implementation': self.implementation, 'MISSING': MISSING, 'validate_attrs': validate_attrs, 'DEFAULTS': defaults}, namespace)

        method = namespace[self.name]
        method.__doc__ = self.docstring
        method.__signature__ = signature_advertised
        return method

    @staticmethod
    def __call_signature_str(signature: Signature) -> Tuple[str, Dict[str, Any]]:
        """
        Return a string representation of the signature that can be used in exec.
        """
        out = []
        defaults = {}
        done_kw_only = False
        for p in signature.parameters.values():
            if p.kind is Parameter.VAR_POSITIONAL:
                done_kw_only = True
            elif p.kind is Parameter.KEYWORD_ONLY and not done_kw_only:
                done_kw_only = True
                out.append('*')
            param = str(p).split(':')[0]
            if p.default is not Parameter.empty:
                param = param.split('=')[0]
                out.append(
                    f'{param}=DEFAULTS["{p.name}"]'
                )
                defaults[p.name] = p.default
            else:
                out.append(param)
        return f'({", ".join(out)})', defaults

    @staticmethod
    def __call_implementation_str(signature: Signature):
        """
        Return a string form "<positional_value>, ..., <field>=<value>, ..."
        """
        out = []
        for name, p in signature.parameters.items():
            if p.kind is inspect.Parameter.POSITIONAL_ONLY:
                out.append(name)
            elif p.kind is inspect.Parameter.VAR_POSITIONAL:
                out.append(f'*{name}')
            elif p.kind is inspect.Parameter.VAR_KEYWORD:
                out.append(f'**{name}')
            else:
                out.append(f'{name}={name}')
        return ", ".join(out)
