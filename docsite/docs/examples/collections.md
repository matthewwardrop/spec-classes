Here's a spec-class with collections.

```python
from spec_classes import spec_class
from typing import List

@spec_class
class Number:
    einstein_approved: bool = False
    value: int

@spec_class
class FavoriteNumbers:
    numbers: List[Number] = []
```

We can instantiate it:
```python
FavoriteNumbers()
# FavoriteNumbers(numbers=[])

FavoriteNumbers(numbers=[Number(value=10), Number(value=13, einstein_approved=True)])
# FavoriteNumbers(
#     numbers=[
#         Number(
#             einstein_approved=False,
#             value=10
#         ),
#         Number(
#             einstein_approved=True,
#             value=13
#         )
#     ]
# )
```

We can extend and mutate it:

```python
(
    FavoriteNumbers()
    .with_number(value=26, einstein_approved=True)
    # FavoriteNumbers(numbers=[Number(einstein_approved=True, value=26)])
    .transform_number(0, value=lambda value: value * 2)
    # FavoriteNumbers(numbers=[Number(einstein_approved=True, value=52)])
    .without_number(0)
)
# FavoriteNumbers(numbers=[])
```

Similar methods exist for dictionary and set collections also; see
[Collections Usage](../usage/collections.md).
