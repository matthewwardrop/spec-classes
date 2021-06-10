from __future__ import annotations

import copy
import functools
import inspect
import textwrap
import typing
from collections import defaultdict
from inspect import Signature, Parameter
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Type, Union

import inflect
from lazy_object_proxy import Proxy

from .errors import FrozenInstanceError
from .special_types import MISSING
from .utils.collections import DictCollection, ListCollection, SetCollection
from .utils.method_builder import MethodBuilder
from .utils.mutation import mutate_attr, mutate_value, invalidate_attrs
from .utils.type_checking import get_collection_item_type, get_spec_class_for_type, type_label, type_match


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
    >>> @spec_class(attrs={'my_field'}, key='my_key_field')
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

        @spec_class(key='key')
        class KeyedSpec:
            key: str = 'key'
            nested_scalar: int = 1
            nested_scalar2: str = 'original value'


        @spec_class(key='key')
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
    INFLECT_CACHE = {}

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
            self, key: str = MISSING, shallowcopy: Union[bool, Iterable[str]] = False, frozen: bool = False,
            init: bool = True, repr: bool = True, eq: bool = True,  bootstrap: bool = False,
            attrs: Iterable[str] = MISSING, attrs_typed: Mapping[str, Type] = MISSING, attrs_skip: Iterable[str] = MISSING,
            init_overflow_attr: Optional[str] = MISSING,
    ):
        """
        Args:
            key: The name of the attribute which can be used to uniquely
                identify a particular specification. If not specified, it will
                be inherited from the parent class. To explicitly disable the
                key functionality, pass `None`.
            shallowcopy: Whether to do a shallow or deep copy when doing
                non-inplace mutations. If this is an iterable of strings, the strings
                should correspond to the attributes which should be passed through
                to the copy of class instances without being copied. This is
                valuable when copying is memory intensive, and when mutations *only*
                occur via the helper methods generated by `spec_class`. If not
                specified, and not inherited from a subclass, this will default to
                `False`.
            frozen: Whether to disallow direct modifications of attributes. If
                not specified and not inherited from parent class, this will
                default to `False`.
            init: Whether to add an `__init__` method if one does not already
                exist.
            repr: Whether to add a `__repr__` method if one does not already
                exist.
            eq: Whether to add an `__eq__` method if one does not already
                exist.
            bootstrap: Whether to bootstrap spec-class immediately (True), or
                wait until first instantiation (False). Default is to defer
                bootstrapping to avoid cyclic annotation imports (False). This
                may be suboptimal if subclasses are wanting to override the
                generated methods.
            attrs: The attrs for which this `spec_cls` should add helper
                methods.
            attrs_typed: Additional attributes for which this `spec_cls`
                should add helper methods, with the type of the attr taken to be
                as specified, overriding (if present) any other type annotations
                for that attribute (e.g. List[int], Dict[str, int], Set[int], etc).
            attrs_skip: Attributes which should not be considered by this `spec_cls`.
            init_overflow_attr: If specified, any extra keyword arguments passed
                to the constructor will be collected as a dictionary and set as
                an attribute of this name.

        Notes:
            - If `attrs` and `attrs_typed` are not specified, then spec-classes
              will manage all annotated attributes. To treat these fields as
              incremental on top of all attributes, pass a (potentially empty)
              iterable to `attrs_skip`.
        """
        self.inherit_annotations = not (attrs or attrs_typed) or attrs_skip is not MISSING
        self.key = key
        self.attrs = {
            **({init_overflow_attr: Dict[str, Any]} if init_overflow_attr else {}),
            **{attr: Any for attr in (attrs or set())},
            **(attrs_typed or {}),
        }
        self.attrs_skip = set(attrs_skip or set())
        self.spec_cls_methods = {
            '__init__': init,
            '__eq__': eq,
            '__repr__': repr,
            '__getattr__': True,
            '__setattr__': True,
            '__delattr__': True,
            '__deepcopy__': True,
        }
        self.shallowcopy = shallowcopy
        self.frozen = frozen
        self.init_overflow_attr = init_overflow_attr
        self.bootstrap_immediately = bootstrap

        # Check for private attr specification, and if found, raise!
        private_attrs = [attr for attr in self.attrs if attr.startswith('_')]
        if private_attrs:
            raise ValueError(f"`spec_cls` cannot be used to generate helper methods for private attributes (got: {private_attrs}).")

    def __call__(self, spec_cls: type) -> type:
        """
        Mark the nominated `spec_class` as a spec-class, and wrap the
        `__new__` magic method with hooks to lazily bootstrap spec-class
        utiltiy methods upon first instantiation.

        Args:
            spec_cls: The decorated class.

        Returns:
            `spec_cls`, with the necessary hooks to generate methods on first
                instantiation.

        Notes:
            - We defer method generation until first instantiation to mitigate
              cyclic import errors when type annotations are bidirectional
              between two classes.
        """
        spec_cls.__is_spec_class__ = True
        spec_cls.__spec_class_bootstrap__ = lambda: self.bootstrap(spec_cls)
        spec_cls.__spec_class_bootstrapped__ = False

        if self.bootstrap_immediately:
            self.bootstrap(spec_cls)
        else:
            orig_new = spec_cls.__new__ if '__new__' in spec_cls.__dict__ else None

            def __new__(cls, *args, **kwargs):
                # Bootstrap spec class
                spec_cls.__spec_class_bootstrap__()

                # Chain out to original __new__ implementation if defined on this
                # spec class.
                if orig_new:
                    return orig_new(cls, *args, **kwargs)

                # Otherwise, remove any additional kwargs added by this class, and
                # chain out to the super-class implementation of __new__.
                if args or kwargs:
                    cls_annotations = getattr(spec_cls, '__annotations__', {})
                    if self.key is not MISSING and self.key in cls_annotations:
                        args = args[1:]
                    if self.init_overflow_attr:
                        kwargs = {}
                    else:
                        for attr in cls_annotations:
                            kwargs.pop(attr, None)

                return super(spec_cls, cls).__new__(cls, *args, **kwargs)

            spec_cls.__new__ = __new__
        return spec_cls

    def bootstrap(self, spec_cls: type):
        """
        Add helper methods for all (or specified) attributes.

        Args:
            spec_cls: The decorated class.
        """
        if getattr(spec_cls, '__spec_class_bootstrapped__', False):
            return
        spec_cls.__spec_class_bootstrapped__ = True

        # Bootstrap any parents of this class first (we can abort after the first
        # such parent since that parent will bootstrap its parent, and so on)
        for parent in spec_cls.mro()[1:]:
            if getattr(parent, '__is_spec_class__', False):
                parent.__spec_class_bootstrap__()
                break

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
                    and attr not in self.attrs_skip
                    and not (
                        isinstance(getattr(spec_cls, attr, None), property)
                        and getattr(spec_cls, attr).fset is None
                    )
                )
            })

        spec_cls.__spec_class_key__ = getattr(spec_cls, '__spec_class_key__', None) if self.key is MISSING else self.key
        spec_cls.__spec_class_frozen__ = getattr(spec_cls, '__spec_class_frozen__', False) if self.frozen is None else self.frozen
        spec_cls.__spec_class_init_overflow_attr__ = getattr(spec_cls, '__spec_class_init_overflow_attr__', None) if self.init_overflow_attr is MISSING else self.init_overflow_attr

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

        # Build invalidation cache
        invalidation_map = copy.deepcopy(getattr(spec_cls, '__spec_class_invalidation_map__', defaultdict(set)))
        for name, member in spec_cls.__dict__.items():
            if hasattr(member, '__spec_class_invalidated_by__'):
                for invalidator in member.__spec_class_invalidated_by__:
                    invalidation_map[invalidator].add(name)
        spec_cls.__spec_class_invalidation_map__ = invalidation_map

        # Register shallow copy attributes
        shallow_attrs = getattr(spec_cls, '__spec_class_shallowcopy__', set())
        if isinstance(self.shallowcopy, bool):
            if self.shallowcopy:
                shallow_attrs.update(spec_cls.__spec_class_annotations__)
        else:
            shallow_attrs.update(self.shallowcopy)
        spec_cls.__spec_class_shallowcopy__ = shallow_attrs

        # Register class-level methods
        self.register_methods(spec_cls, self.get_methods_for_spec_class(spec_cls, self.spec_cls_methods))

        self._validate_spec_cls(spec_cls)

        # For each new attribute to be managed by `spec_cls`, generate helper methods.
        for attr_name in managed_attrs:
            self.register_methods(spec_cls, self.get_methods_for_attribute(
                spec_cls, attr_name, attr_type=spec_cls.__spec_class_annotations__[attr_name]
            ))

    @classmethod
    def _validate_spec_cls(cls, spec_cls):
        spec_annotations = spec_cls.__spec_class_annotations__

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
        spec_class_key = spec_cls.__spec_class_key__
        key_default = Parameter.empty
        if spec_class_key:
            key_default = MISSING if hasattr(spec_cls, spec_class_key) else Parameter.empty
            if inspect.isfunction(key_default) or inspect.isdatadescriptor(key_default):
                spec_class_key = None

        def init_impl(self, **kwargs):
            is_frozen = self.__spec_class_frozen__
            self.__spec_class_frozen__ = False

            get_attr_default = getattr(self, '__spec_class_get_attr_default__', None)

            for attr in self.__spec_class_annotations__:
                if attr == self.__spec_class_init_overflow_attr__:
                    continue
                value = kwargs.get(attr, MISSING)
                if value is MISSING:  # Look up from spec_class_get_attr_default handler, if handled, or class attributes (if set)
                    if get_attr_default:
                        value = get_attr_default(attr)
                    if value is MISSING:
                        value = getattr(self.__class__, attr, MISSING)
                        if value is MISSING or inspect.isfunction(value) or inspect.isdatadescriptor(value):
                            continue  # Methods will already be bound to instance from class
                        # We *always* deepcopy values from class defaults so we do not share
                        # values across instances.
                        value = copy.deepcopy(value)
                else:
                    if attr not in self.__spec_class_shallowcopy__:
                        value = copy.deepcopy(value)

                getattr(self, f'with_{attr}')(value, _inplace=True)

            if self.__spec_class_init_overflow_attr__:
                getattr(self, f'with_{self.__spec_class_init_overflow_attr__}')(
                    {
                        key: value
                        for key, value in kwargs.items()
                        if key not in self.__spec_class_annotations__ or key == self.__spec_class_init_overflow_attr__
                    },
                    _inplace=True,
                )

            if is_frozen:
                self.__spec_class_frozen__ = True

        __init__ = (
            MethodBuilder('__init__', init_impl)
            .with_preamble(f"Initialise this `{spec_cls.__name__}` instance.")
            .with_arg(
                spec_class_key, f"The value to use for the `{spec_class_key}` key attribute.",
                default=key_default, annotation=spec_cls.__spec_class_annotations__.get(spec_class_key),
                only_if=spec_class_key
            )
            .with_spec_attrs_for(spec_cls, defaults=True)
        )

        def __repr__(self, include_attrs=None, exclude_attrs=None, indent=None, indent_threshold=100):
            """
            Args:
                include_attrs: An ordered iterable of attrs to include in the
                    representation.
                exclude_attrs: An iterable of attrs to exclude from the
                    representation.
                indent: Whether to indent. If `True`, indenting is always
                    performed. If `False`, indenting is never performed. If
                    `None`, indenting is performed when output otherwise exceeds
                    `indent_threshold` characters. (default: None)
                indent_threshold: The threshold at which to switch to indented
                    representations (see above).
            """
            ambiguous_attrs = set(include_attrs or []).intersection(exclude_attrs or [])
            if ambiguous_attrs:
                raise ValueError(f"Some attributes were both included and excluded: {ambiguous_attrs}.")

            include_attrs = include_attrs or list(self.__spec_class_annotations__)
            exclude_attrs = set(exclude_attrs or [])

            def object_repr(obj, indent=False):
                if inspect.ismethod(obj) and obj.__self__ is self:
                    return f"<bound method {obj.__name__} of self>"
                if hasattr(obj, '__repr__'):
                    try:
                        return obj.__repr__(indent=indent)
                    except TypeError:
                        pass

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
                    if attr not in exclude_attrs
                ])
                unindented_repr = f"{self.__class__.__name__}({unindented_attrs})"
                if indent is False or (len(unindented_repr) <= indent_threshold and not any('\n' in attr_repr for attr_repr in unindented_attrs)):
                    return unindented_repr

            # Collected indented representation
            indented_attrs = textwrap.indent(',\n'.join([
                f"{attr}={object_repr(getattr(self, attr, MISSING), indent=True)}"
                for attr in include_attrs
                if attr not in exclude_attrs
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
            if attr in self.__spec_class_annotations__ and attr not in self.__dict__ and not inspect.isdatadescriptor(getattr(self.__class__, attr, None)):
                raise AttributeError(f"`{self.__class__.__name__}.{attr}` has not yet been assigned a value.")
            return self.__getattr__.__raw__(self, attr)

        def __setattr__(self, attr, value, force=False):
            # Abort if frozen
            if not force and self.__spec_class_frozen__ and attr != '__spec_class_frozen__':
                raise FrozenInstanceError(f"Cannot mutate attribute `{attr}` of frozen spec class `{self.__class__.__name__}`.")

            # Check attr type if managed attribute
            if force or attr not in self.__spec_class_annotations__ or not hasattr(self, f'with_{attr}'):
                self.__setattr__.__raw__(self, attr, value)
                invalidate_attrs(self, attr)
            else:
                getattr(self, f'with_{attr}')(value, _inplace=True)

        def __delattr__(self, attr, force=False):
            # Abort if frozen
            if not force and self.__spec_class_frozen__:
                raise FrozenInstanceError(f"Cannot mutate attribute `{attr}` of frozen spec class `{self.__class__.__name__}`.")

            cls_value = getattr(self.__class__, attr, MISSING)
            if inspect.isfunction(cls_value) or inspect.isdatadescriptor(cls_value) or cls_value is MISSING:
                self.__delattr__.__raw__(self, attr)
                invalidate_attrs(self, attr)
                return None

            return mutate_attr(
                obj=self,
                attr=attr,
                value=copy.deepcopy(cls_value),
                inplace=True,
                force=True
            )

        # Set __raw__ attribute on attribute extractors/mutators to call back to
        # underlying objects.
        if hasattr(spec_cls, '__getattr__'):
            __getattr__.__raw__ = getattr(spec_cls.__getattr__, '__raw__', spec_cls.__getattr__)
        else:
            __getattr__.__raw__ = spec_cls.__getattribute__
        __setattr__.__raw__ = getattr(spec_cls.__setattr__, '__raw__', spec_cls.__setattr__)
        __delattr__.__raw__ = getattr(spec_cls.__delattr__, '__raw__', spec_cls.__delattr__)

        def __deepcopy__(self, memo):
            if self.__spec_class_frozen__:
                return self
            new = self.__class__.__new__(self.__class__)
            for attr, value in self.__dict__.items():
                if inspect.ismethod(value) and value.__self__ is self:
                    continue
                if attr in self.__spec_class_shallowcopy__:
                    new.__dict__[attr] = value
                else:
                    new.__dict__[attr] = copy.deepcopy(value, memo)
            return new

        methods = {
            '__init__': __init__,
            '__repr__': __repr__,
            '__eq__': __eq__,
            '__getattr__': __getattr__,
            '__setattr__': __setattr__,
            '__delattr__': __delattr__,
            '__deepcopy__': __deepcopy__,
            '__spec_class_init__': __init__,
            '__spec_class_repr__': __repr__,
            '__spec_class_eq__': __eq__,
        }
        return {
            name: method
            for name, method in methods.items()
            if name.startswith('__spec_class') or methods_filter.get(name, False)
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
            is_collection=type_match(attr_type, (list, dict, set))
        )
        if type_match(attr_type, list):
            methods.update(self._get_methods_for_list(spec_cls, attr_name, attr_type))
        elif type_match(attr_type, dict):
            methods.update(self._get_methods_for_dict(spec_cls, attr_name, attr_type))
        elif type_match(attr_type, set):
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
            setattr(method, '__spec_class_owned__', True)
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
        if name in spec_cls.__dict__ and not name.startswith('__spec_class'):
            return
        if isinstance(method, MethodBuilder):
            method = method.build()
        setattr(spec_cls, name, method)

    # High-level mutation helpers

    @classmethod
    def _get_attr(cls, self: Any, name: str, default: Any = MISSING):
        try:
            return object.__getattribute__(self, name)
        except Exception:  # pylint: disable=broad-except
            return default

    # Scalar methods
    @classmethod
    def _get_methods_for_scalar(cls, spec_cls: type, attr_name: str, attr_type: Type, is_collection: bool = False):
        attr_spec_type = get_spec_class_for_type(attr_type)
        attr_prepare_method = f'_prepare_{attr_name}'

        def get_attr(self, _raise_if_missing=True):
            if _raise_if_missing:
                return getattr(self, attr_name)
            return cls._get_attr(self, attr_name)

        def with_attr(self, _new_value=MISSING, *, _replace=False, _inplace=False, **attrs):
            try:
                _new_value = getattr(self, attr_prepare_method)(_new_value, **attrs)
            except AttributeError:
                pass

            if is_collection:
                _new_value = cls._populate_collection(self, attr_name, attr_type, _new_value)
            else:
                _new_value = mutate_value(
                    old_value=Proxy(lambda: cls._get_attr(self, attr_name)), new_value=_new_value, constructor=attr_type, attrs=attrs, replace=_replace
                )

            return mutate_attr(
                obj=self,
                attr=attr_name,
                value=_new_value,
                inplace=_inplace,
            )

        def transform_attr(self, _transform=None, *, _inplace=False, **attr_transforms):
            return with_attr(
                self,
                _new_value=mutate_value(
                    old_value=Proxy(lambda: cls._get_attr(self, attr_name)),
                    transform=_transform,
                    constructor=attr_type,
                    attr_transforms=attr_transforms
                ),
                _inplace=_inplace,
            )

        def reset_attr(self, _inplace=False):
            if not _inplace:
                self = copy.deepcopy(self)
            self.__delattr__(attr_name)
            return self

        or_its_attributes = " or its attributes" if attr_spec_type else ""
        return {
            f'get_{attr_name}': (
                MethodBuilder(f'get_{attr_name}', get_attr)
                .with_preamble(f"Retrieve the value of attribute `{attr_name}`.")
                .with_arg('_raise_if_missing', "Whether to raise an AttributeError when `{attr_name}` has not been set.", default=True, keyword_only=True, annotation=bool)
                .with_returns("The current value of the attribute (or `MISSING` if `_raise_if_missing` is `False`).", annotation=attr_type)
            ),
            f'with_{attr_name}': (
                MethodBuilder(f'with_{attr_name}', with_attr)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with `{attr_name}`{or_its_attributes} mutated.")
                .with_arg("_new_value", f"The new value for `{attr_name}`.", default=MISSING, annotation=attr_type)
                .with_arg("_replace", f"If True, build a new {type_label(attr_type)} from scratch. Otherwise, modify the old value.",
                          only_if=attr_spec_type, default=False, keyword_only=True, annotation=bool)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(attr_type, template=f"An optional new value for {attr_name}.{{}}.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'transform_{attr_name}': (
                MethodBuilder(f'transform_{attr_name}', transform_attr)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with `{attr_name}`{or_its_attributes} transformed.")
                .with_arg("_transform", f"A function that takes the old value for {attr_name} as input, and returns the new value.",
                          default=MISSING if attr_spec_type else Parameter.empty, annotation=Callable)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(attr_type, template=f"An optional transformer for {attr_name}.{{}}.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'reset_{attr_name}': (
                MethodBuilder(f'reset_{attr_name}', reset_attr)
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with `{attr_name}` reset to its default value.")
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
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
        if attr_name not in cls.INFLECT_CACHE:
            singular = cls.INFLECT_ENGINE.singular_noun(attr_name)
            if not singular or singular == attr_name:
                singular = f"{attr_name}_item"
            cls.INFLECT_CACHE[attr_name] = singular
        return cls.INFLECT_CACHE[attr_name]

    @classmethod
    def _populate_collection(cls, self, attr_name, attr_type, items):
        singular_name = cls._get_singular_form(attr_name)

        if type_match(attr_type, list):
            collection = ListCollection(attr_type, name=attr_name)
        elif type_match(attr_type, dict):
            collection = DictCollection(attr_type, name=attr_name)
        elif type_match(attr_type, set):
            collection = SetCollection(attr_type, name=attr_name)
        else:
            raise TypeError("Unrecognised collection type.")  # pragma: no cover; this is just a sentinel.

        if items:
            preparer = getattr(self, f'_prepare_{singular_name}', None)
            collection.add_items(items, preparer=preparer)
            return collection.collection
        return collection._create_collection()  # pylint: disable=protected-access

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
        item_type = get_collection_item_type(attr_type)
        item_spec_type = get_spec_class_for_type(item_type)
        item_spec_type_is_keyed = item_spec_type and item_spec_type.__spec_class_key__ is not None

        # Check list collection type is valid (i.e. nested spec-type doesn't have integer keys)
        ListCollection(attr_type, name=attr_name)

        def get_collection(self, inplace=True):
            return ListCollection(
                collection_type=attr_type,
                collection=cls._get_attr(self, attr_name, MISSING),
                name=f"{self.__class__.__name__}.{attr_name}",
                inplace=inplace,
            )

        # types for function signatures
        fn_item_type = item_type
        fn_index_type = int
        if item_spec_type_is_keyed:
            fn_item_type = Union[item_spec_type.__spec_class_annotations__[item_spec_type.__spec_class_key__], fn_item_type]
            fn_index_type = Union[item_spec_type.__spec_class_annotations__[item_spec_type.__spec_class_key__], fn_index_type]

        return {
            f'get_{singular_name}': (
                MethodBuilder(
                    f'get_{singular_name}',
                    lambda self, _value_or_index=MISSING, *, _by_index=False, _all_matches=False, _raise_if_missing=True, **attr_filters: (
                        get_collection(self)
                        .get_item(
                            value_or_index=_value_or_index,
                            attr_filters=attr_filters,
                            by_index=_by_index,
                            all_matches=_all_matches,
                            raise_if_missing=_raise_if_missing,
                        )
                    )
                )
                .with_preamble(f"Return `{attr_type}` instance(s) corresponding to a given value or index." + (" You can also filter by the nested spec class attributes." if item_spec_type else ""))
                .with_arg("_value_or_index", "The value for which to extract an item, or (if `by_index=True`) its index.", default=MISSING if item_spec_type else Parameter.empty, annotation=Union[fn_item_type, fn_index_type])
                .with_arg("_by_index", "If True, value_or_index is the index of the item to extract.", keyword_only=True, default=False, annotation=bool)
                .with_arg("_all_matches", "Whether to return all matching items in container, or just the first.", default=False, keyword_only=True, annotation=bool, only_if=item_spec_type)
                .with_arg('_raise_if_missing', "Whether to raise an AttributeError when an item is not found.", default=True, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional filter for `{singular_name}.{{}}`.")
                .with_returns("The extracted item.", annotation=item_type)
            ),
            f'with_{singular_name}': (
                MethodBuilder(
                    f'with_{singular_name}',
                    lambda self, _item=MISSING, *, _index=MISSING, _insert=False, _replace=False, _inplace=False, **attrs: (
                        mutate_attr(
                            obj=self,
                            attr=attr_name,
                            value=(
                                get_collection(self, inplace=_inplace)
                                .add_item(
                                    item=getattr(self, f'_prepare_{singular_name}', lambda x, **attrs: x)(_item, **attrs),
                                    attrs=attrs,
                                    index=_index,
                                    insert=_insert,
                                    replace=_replace,
                                )
                                .collection
                            ),
                            inplace=_inplace,
                            type_check=False,
                        )
                    )
                )
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item added to or updated in `{attr_name}`.")
                .with_arg("_item", f"A new `{type_label(item_type)}` instance for {attr_name}.", default=MISSING, annotation=fn_item_type)
                .with_arg("_index", "Index for which to insert or replace, depending on `insert`; if not provided, append.", default=MISSING, keyword_only=True, annotation=fn_index_type)
                .with_arg("_insert", f"Insert item before {attr_name}[index], otherwise replace this index.", default=False, keyword_only=True, annotation=bool)
                .with_arg(
                    "_replace", f"If True, and if replacing an old item, build a new {type_label(item_type)} from scratch. Otherwise, apply changes on top of the old value.",
                    only_if=item_spec_type, default=False, keyword_only=True, annotation=bool
                )
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional new value for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'transform_{singular_name}': (
                MethodBuilder(
                    f'transform_{singular_name}',
                    lambda self, _value_or_index, _transform, *, _by_index=False, _inplace=False, **attr_transforms: (
                        mutate_attr(
                            obj=self,
                            attr=attr_name,
                            value=(
                                get_collection(self, inplace=_inplace)
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
                    )
                )
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item transformed in `{attr_name}`.")
                .with_arg("_value_or_index", "The value to transform, or (if `by_index=True`) its index.", annotation=Union[fn_item_type, fn_index_type])
                .with_arg("_transform", "A function that takes the old item as input, and returns the new item.", default=MISSING if item_spec_type else Parameter.empty, annotation=Callable)
                .with_arg("_by_index", "If True, value_or_index is the index of the item to transform.", keyword_only=True, default=False, annotation=bool)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional transformer for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'without_{singular_name}': (
                MethodBuilder(
                    f'without_{singular_name}',
                    lambda self, _value_or_index, *, _by_index=False, _inplace=False: (
                        mutate_attr(
                            obj=self,
                            attr=attr_name,
                            value=(
                                get_collection(self, inplace=_inplace)
                                .remove_item(
                                    value_or_index=_value_or_index,
                                    by_index=_by_index,
                                )
                                .collection
                            ),
                            inplace=_inplace,
                            type_check=False,
                        )
                    )
                )
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
        item_type = get_collection_item_type(attr_type)
        item_spec_type = get_spec_class_for_type(item_type)
        item_spec_type_is_keyed = item_spec_type and item_spec_type.__spec_class_key__ is not None

        def get_collection(self, inplace=True):
            return DictCollection(
                collection_type=attr_type,
                collection=cls._get_attr(self, attr_name, MISSING),
                name=f"{self.__class__.__name__}.{attr_name}",
                inplace=inplace,
            )

        # types for function signatures
        if item_spec_type_is_keyed:
            fn_key_type = fn_value_type = Union[item_spec_type.__spec_class_annotations__[item_spec_type.__spec_class_key__], item_type]
        else:
            fn_key_type = Any
            if hasattr(attr_type, '__args__') and not isinstance(attr_type.__args__[0], typing.TypeVar):
                fn_key_type = attr_type.__args__[0]
            fn_value_type = item_type

        return {
            f'get_{singular_name}': (
                MethodBuilder(
                    f'get_{singular_name}',
                    lambda self, _key=MISSING, *, _all_matches=False, _raise_if_missing=True, **attr_filters: (
                        get_collection(self)
                        .get_item(
                            key=_key,
                            attr_filters=attr_filters,
                            all_matches=_all_matches,
                            raise_if_missing=_raise_if_missing,
                        )
                    )
                )
                .with_preamble(f"Return `{attr_type}` instance(s) corresponding to a given value or index." + (" You can also filter by the nested spec class attributes." if item_spec_type else ""))
                .with_arg("_key", "The key for which to extract an item.", default=MISSING if item_spec_type else Parameter.empty, annotation=fn_key_type)
                .with_arg("_all_matches", "Whether to return all matching items in container, or just the first.", default=False, keyword_only=True, annotation=bool, only_if=item_spec_type)
                .with_arg('_raise_if_missing', "Whether to raise an AttributeError when an item is not found.", default=True, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional filter for `{singular_name}.{{}}`.")
                .with_returns("The extracted item.", annotation=item_type)
            ),
            f'with_{singular_name}': (
                MethodBuilder(
                    f'with_{singular_name}',
                    lambda self, _key=None, _value=None, _replace=False, _inplace=False, **attrs: (
                        mutate_attr(
                            obj=self,
                            attr=attr_name,
                            value=(
                                get_collection(self, inplace=_inplace)
                                .add_item(
                                    *getattr(self, f'_prepare_{singular_name}', lambda k, v, **attrs: (k, v))(_key, _value, **attrs),  # Tuple of key, value
                                    replace=_replace,
                                    attrs=attrs,
                                )
                                .collection
                            ),
                            inplace=_inplace,
                            type_check=False,
                        )
                    )
                )
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item added to or updated in `{attr_name}`.")
                .with_arg("_key", "The key for the item to be inserted or updated.", annotation=fn_key_type, only_if=not item_spec_type_is_keyed)
                .with_arg("_value", f"A new `{type_label(item_type)}` instance for {attr_name}.", default=MISSING if item_spec_type else Parameter.empty, annotation=fn_value_type)
                .with_arg(
                    "_replace", f"If True, and if replacing an old item, build a new {type_label(item_type)} from scratch. Otherwise, apply changes on top of the old value.",
                    only_if=item_spec_type, default=False, keyword_only=True, annotation=bool
                )
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional new value for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'transform_{singular_name}': (
                MethodBuilder(
                    f'transform_{singular_name}',
                    lambda self, _key, _transform, *, _inplace=False, **attr_transforms: (
                        mutate_attr(
                            obj=self,
                            attr=attr_name,
                            value=(
                                get_collection(self, inplace=_inplace)
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
                    )
                )
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item transformed in `{attr_name}`.")
                .with_arg("_key", "The key for the item to be inserted or updated.", annotation=fn_key_type)
                .with_arg("_transform", "A function that takes the old item as input, and returns the new item.", default=MISSING if item_spec_type else Parameter.empty, annotation=Callable)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional transformer for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'without_{singular_name}': (
                MethodBuilder(
                    f'without_{singular_name}',
                    lambda self, _key, *, _inplace=False: (
                        mutate_attr(
                            obj=self,
                            attr=attr_name,
                            value=(
                                get_collection(self, inplace=_inplace)
                                .remove_item(key=_key)
                                .collection
                            ),
                            inplace=_inplace,
                            type_check=False,
                        )
                    ),
                )
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
        item_type = get_collection_item_type(attr_type)
        item_spec_type = get_spec_class_for_type(item_type)

        def get_collection(self, inplace=True):
            return SetCollection(
                collection_type=attr_type,
                collection=cls._get_attr(self, attr_name, MISSING),
                name=f"{self.__class__.__name__}.{attr_name}",
                inplace=inplace,
            )

        return {
            f'get_{singular_name}': (
                MethodBuilder(
                    f'get_{singular_name}',
                    lambda self, _item=MISSING, *, _all_matches=False, _raise_if_missing=True, **attr_filters: (
                        get_collection(self)
                        .get_item(
                            item=_item,
                            all_matches=_all_matches,
                            raise_if_missing=_raise_if_missing,
                            attr_filters=attr_filters,
                        )
                    )
                )
                .with_preamble(f"Return `{attr_type}` instance(s) corresponding to a given value or index." + (" You can also filter by the nested spec class attributes." if item_spec_type else ""))
                .with_arg("_item", "The item to extract.", default=MISSING if item_spec_type else Parameter.empty, annotation=item_type)
                .with_arg("_all_matches", "Whether to return all matching items in container, or just the first.", default=False, keyword_only=True, annotation=bool, only_if=item_spec_type)
                .with_arg('_raise_if_missing', "Whether to raise an AttributeError when an item is not found.", default=True, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional filter for `{singular_name}.{{}}`.")
                .with_returns("The extracted item.", annotation=item_type)
            ),
            f'with_{singular_name}': (
                MethodBuilder(
                    f'with_{singular_name}',
                    lambda self, _item, *, _replace=False, _inplace=False, **attrs: (
                        mutate_attr(
                            obj=self,
                            attr=attr_name,
                            value=(
                                get_collection(self, inplace=_inplace)
                                .add_item(
                                    item=getattr(self, f'_prepare_{singular_name}', lambda x, **attrs: x)(_item, **attrs),
                                    replace=_replace,
                                )
                                .collection
                            ),
                            inplace=_inplace,
                            type_check=False,
                        )
                    )
                )
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item added to `{attr_name}`.")
                .with_arg("_item", f"A new `{type_label(item_type)}` instance for {attr_name}.", default=MISSING if item_spec_type else Parameter.empty, annotation=item_type)
                .with_arg(
                    "_replace", f"If True, and if replacing an old item, build a new {type_label(item_type)} from scratch. Otherwise, apply changes on top of the old value.",
                    only_if=item_spec_type, default=False, keyword_only=True, annotation=bool
                )
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional new value for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'transform_{singular_name}': (
                MethodBuilder(
                    f'transform_{singular_name}',
                    lambda self, _item, _transform, *, _inplace=False, **attr_transforms: (
                        mutate_attr(
                            obj=self,
                            attr=attr_name,
                            value=(
                                get_collection(self, inplace=_inplace)
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
                    )
                )
                .with_preamble(f"Return a `{spec_cls.__name__}` instance identical to this one except with an item transformed in `{attr_name}`.")
                .with_arg("_item", "The value to transform.", annotation=item_type)
                .with_arg("_transform", "A function that takes the old item as input, and returns the new item.", default=MISSING if item_spec_type else Parameter.empty, annotation=Callable)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_spec_attrs_for(item_spec_type, template=f"An optional transformer for `{singular_name}.{{}}`.")
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
            f'without_{singular_name}': (
                MethodBuilder(
                    f'without_{singular_name}',
                    lambda self, _item, _inplace=False: (
                        mutate_attr(
                            obj=self,
                            attr=attr_name,
                            value=(
                                get_collection(self, inplace=_inplace)
                                .remove_item(_item)
                                .collection
                            ),
                            inplace=_inplace,
                            type_check=False,
                        )
                    )
                )
                .with_preamble(
                    f"Return a `{spec_cls.__name__}` instance identical to this one except with an item removed from `{attr_name}`."
                )
                .with_arg("_item", "The value to remove.", annotation=item_type)
                .with_arg("_inplace", "Whether to perform change without first copying.", default=False, keyword_only=True, annotation=bool)
                .with_returns(f"A reference to the mutated `{spec_cls.__name__}` instance.", annotation=spec_cls)
            ),
        }
