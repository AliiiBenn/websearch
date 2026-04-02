"""Maybe type for handling optional values without None checks."""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

from websearch.core.types.result import Err, Ok, Result


T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")


class Maybe(Generic[T]):
    """Represents an optional value that may or may not exist.

    This is an alternative to using None directly, providing a functional
    way to chain operations on optional values.
    """

    __match_args__ = ("is_just",)

    def is_just(self) -> bool:
        """Check if this Maybe contains a value."""
        raise NotImplementedError

    def is_nothing(self) -> bool:
        """Check if this Maybe is empty."""
        raise NotImplementedError

    def just_value(self) -> T | None:
        """Get the value if Just, else None."""
        raise NotImplementedError

    def __bool__(self) -> bool:
        """Allow using Maybe in boolean context."""
        return self.is_just()

    def map(self, fn: Callable[[T], U]) -> Maybe[U]:
        """Transform the value if Just."""
        raise NotImplementedError

    def flat_map(self, fn: Callable[[T], Maybe[U]]) -> Maybe[U]:
        """Chain Maybe-returning functions."""
        raise NotImplementedError

    def filter(self, predicate: Callable[[T], bool]) -> Maybe[T]:
        """Keep value only if predicate returns True."""
        raise NotImplementedError

    def get_or_else(self, default: T) -> T:
        """Get the value or a default."""
        raise NotImplementedError

    def get_or_else_from(self, fn: Callable[[], T]) -> T:
        """Get the value or compute it from a function."""
        raise NotImplementedError

    def to_result(self, error: E) -> Result[T, E]:
        """Convert to Result[T, E] with the given error for Nothing."""
        raise NotImplementedError

    def contains(self, value: T) -> bool:
        """Check if this Just contains the given value."""
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        raise NotImplementedError

    def __repr__(self) -> str:
        raise NotImplementedError


class Just(Maybe[T]):
    """Represents a Maybe that contains a value."""

    __slots__ = ("value",)
    __match_args__ = ("value",)

    def __init__(self, value: T) -> None:
        self.value = value

    def is_just(self) -> bool:
        return True

    def is_nothing(self) -> bool:
        return False

    def just_value(self) -> T | None:
        return self.value

    def __bool__(self) -> bool:
        return True

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Just):
            return self.value == other.value
        if isinstance(other, Nothing):
            return False
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Just", self.value))

    def __repr__(self) -> str:
        return f"Just({self.value!r})"

    def map(self, fn: Callable[[T], U]) -> Maybe[U]:
        return Just(fn(self.value))

    def flat_map(self, fn: Callable[[T], Maybe[U]]) -> Maybe[U]:
        return fn(self.value)

    def filter(self, predicate: Callable[[T], bool]) -> Maybe[T]:
        if predicate(self.value):
            return self
        return Nothing()

    def get_or_else(self, default: T) -> T:
        return self.value

    def get_or_else_from(self, fn: Callable[[], T]) -> T:
        return self.value

    def to_result(self, error: E) -> Result[T, E]:
        return Ok(self.value)

    def contains(self, value: T) -> bool:
        return self.value == value


class Nothing(Maybe[T]):
    """Represents a Maybe that contains no value.

    Nothing is used to represent the absence of a value. All instances of
    Nothing are equivalent (as if it were a singleton).
    """

    __slots__ = ()

    def is_just(self) -> bool:
        return False

    def is_nothing(self) -> bool:
        return True

    def just_value(self) -> T | None:  # type: ignore[type-arg]
        return None

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Nothing):
            return True
        if isinstance(other, Just):
            return False
        return NotImplemented

    def __hash__(self) -> int:
        return hash("Nothing")

    def __repr__(self) -> str:
        return "Nothing"

    def map(self, fn: Callable[[T], U]) -> Nothing[U]:  # type: ignore[type-arg]
        return self  # type: ignore[return-value]

    def flat_map(self, fn: Callable[[T], Maybe[U]]) -> Nothing[U]:  # type: ignore[type-arg]
        return self  # type: ignore[return-value]

    def filter(self, predicate: Callable[[T], bool]) -> Nothing[T]:  # type: ignore[type-arg]
        return self

    def get_or_else(self, default: T) -> T:
        return default

    def get_or_else_from(self, fn: Callable[[], T]) -> T:
        return fn()

    def to_result(self, error: E) -> Result[T, E]:  # type: ignore[type-arg]
        return Err(error)

    def contains(self, value: T) -> bool:
        return False
