# Python Type Checking

## Type Hint Fundamentals

### Basic annotations

```python
def process(name: str, count: int, active: bool = True) -> list[str]:
    ...

# Collections
items: list[str] = []
mapping: dict[str, int] = {}
unique: set[str] = set()
pair: tuple[str, int] = ("key", 1)
variable_tuple: tuple[str, ...] = ("a", "b", "c")
```

### Optional and Union

```python
# Modern syntax (Python 3.10+)
def find(name: str) -> User | None:
    ...

# For older Python or when needed
from typing import Optional, Union
value: Optional[str]  # equivalent to str | None
mixed: Union[str, int]  # equivalent to str | int
```

## Pyright Configuration

### Strict mode settings

```json
{
    "typeCheckingMode": "strict",
    "reportMissingTypeStubs": false,
    "reportUnknownMemberType": false
}
```

Key strict flags:
- `reportUnusedImport`: Error on unused imports.
- `reportUntypedFunctionDecorator`: Require typed decorators.
- `reportMissingParameterType`: Every parameter must be annotated.
- `reportMissingReturnType`: Every function must have a return type.
- `reportUnknownParameterType`: No inferred `Unknown` types in parameters.

### Standard mode

The default for most projects. Catches real errors without excessive noise.
Upgrade to strict when the team is comfortable with type annotations.

## TypedDict

For dictionary-shaped data with known keys:

```python
from typing import TypedDict, NotRequired

class UserConfig(TypedDict):
    name: str
    email: str
    theme: NotRequired[str]  # optional key

# Usage
config: UserConfig = {"name": "alice", "email": "a@b.com"}
config["theme"] = "dark"  # OK
config["unknown"] = "x"  # type error
```

### Total vs non-total

```python
class RequiredFields(TypedDict):
    id: int
    name: str

class OptionalFields(TypedDict, total=False):
    bio: str
    avatar: str

class User(RequiredFields, OptionalFields):
    pass  # id and name required; bio and avatar optional
```

## Protocol (Structural Typing)

Define interfaces based on behavior, not inheritance:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Serializable(Protocol):
    def to_dict(self) -> dict[str, str]: ...

def save(obj: Serializable) -> None:
    data = obj.to_dict()  # type-safe
    ...

# Any class with to_dict() satisfies Serializable — no explicit inheritance
class User:
    def to_dict(self) -> dict[str, str]:
        return {"name": self.name}

save(User())  # OK — User satisfies Serializable structurally
```

Use Protocol over ABC when you want structural typing (duck typing with
type safety).

## Generic Types

```python
from typing import Generic, TypeVar

T = TypeVar("T")

class Repository(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def add(self, item: T) -> None:
        self._items.append(item)

    def get_all(self) -> list[T]:
        return list(self._items)

# Usage
repo: Repository[User] = Repository()
repo.add(User())  # OK
repo.add("string")  # type error
```

### Bounded type variables

```python
from typing import TypeVar

class Animal: ...
class Dog(Animal): ...

T = TypeVar("T", bound=Animal)

def feed(animal: T) -> T:
    ...  # guaranteed to receive an Animal subclass, returns same type
```

## TYPE_CHECKING Pattern

Avoid circular imports by guarding type-only imports:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from project.models import User  # only imported during type checking

def process(user: User) -> str:  # works because annotations are strings
    ...
```

Rules:
- Always pair with `from __future__ import annotations`.
- Only use for imports needed exclusively for type annotations.
- Never use for imports that are needed at runtime.

## Common Type Patterns

### Callable

```python
from collections.abc import Callable

Handler = Callable[[str, int], bool]  # takes (str, int), returns bool
```

### Literal and narrowing

```python
from typing import Literal

def set_mode(mode: Literal["read", "write", "append"]) -> None: ...

def process(value: str | int) -> str:
    if isinstance(value, str):
        return value.upper()  # narrowed to str
    return str(value)  # narrowed to int
```

Use `assert_never()` in exhaustive match/switch default cases.
