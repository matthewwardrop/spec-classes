Sometimes you need to do some type-casting in order to get incoming values to
conform the right types. Sometimes this is done in the constructor (`__init__`)
or via properties... but in spec-classes this is made much more explicit and
concise. Here's an example:

```python
from spec_classes import spec_class
from typing import Any, Union

@spec_class
class BinaryNumbers:

    are_cool: bool
    numbers: List[str]

    def _prepare_are_cool(self, are_cool: Any) -> bool:
        return bool(are_cool)

    def _prepare_number(self, number: Union[str, int]) -> bool:
        if isinstance(number, int):
            return "{0:b}".format(number)
        if set(number).difference({"0", "1"}):
            raise TypeError(f"Incoming string `{repr(number)}` is not a valid binary number.")
        return number

BinaryNumbers(are_cool=1, numbers=['01001', 10])
# BinaryNumbers(are_cool=True, numbers=['01001', '1010'])

BinaryNumbers().with_number('3213')
# TypeError: Incoming string `'3213'` is not a valid binary number.
```

As you can see, `_prepare_<attr>` and `_prepare_<attr_singular>` are detected
as preparation/typecasting methods. You can also explicitly associate attributes
with methods/functions ala. Python properties using:
```python
from spec_classes import spec_class, Attr
from typing import Any, Union

@spec_class
class BinaryNumbers:

    are_cool: bool = Attr()
    numbers: List[str] = Attr()

    @are_cool.preparer
    def _(self, are_cool):
        return bool(are_cool)

    @numbers.item_preparer
    def _(self, number):
        if isinstance(number, int):
            return "{0:b}".format(number)
        if set(number).difference({"0", "1"}):
            raise TypeError(f"Incoming string `{repr(number)}` is not a valid binary number.")
        return number
```
