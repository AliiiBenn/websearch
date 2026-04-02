"""Result type for explicit error handling without exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Generic, TypeVar

if TYPE_CHECKING:
    from typing import Any


T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


class Result(Generic[T, E]):
    """Represents either a success (Ok) or failure (Err).

    This is a functional approach to error handling where errors are
    values that can be transformed and composed, rather than exceptions
    that propagate up the call stack.
    """

    __match_args__ = ("is_ok",)

    def is_ok(self) -> bool:
        """Check if this result is Ok."""
        raise NotImplementedError

    def is_err(self) -> bool:
        """Check if this result is Err."""
        raise NotImplementedError

    def ok(self) -> T | None:
        """Unwrap the value if Ok, else None."""
        raise NotImplementedError

    def err(self) -> E | None:
        """Unwrap the error if Err, else None."""
        raise NotImplementedError

    def unwrap(self) -> T:
        """Unwrap the value. Raises if Err."""
        raise NotImplementedError

    def unwrap_err(self) -> E:
        """Unwrap the error. Raises if Ok."""
        raise NotImplementedError

    def unwrap_or(self, default: T) -> T:
        """Unwrap the value or return a default."""
        raise NotImplementedError

    def unwrap_or_else(self, fn: Callable[[E], T]) -> T:
        """Unwrap the value or compute it from the error."""
        raise NotImplementedError

    def map(self, fn: Callable[[T], U]) -> Result[U, E]:
        """Transform the Ok value."""
        raise NotImplementedError

    def map_err(self, fn: Callable[[E], U]) -> Result[T, U]:
        """Transform the Err value."""
        raise NotImplementedError

    def flat_map(self, fn: Callable[[T], Result[U, E]]) -> Result[U, E]:
        """Chain Result-returning functions."""
        raise NotImplementedError

    def flatten(self: Result[Result[U, Any], E]) -> Result[U, E]:
        """Flatten nested Results."""
        raise NotImplementedError

    def contains(self, value: T) -> bool:
        """Check if this Ok contains the given value."""
        raise NotImplementedError

    def contains_err(self, error: E) -> bool:
        """Check if this Err contains the given error."""
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        raise NotImplementedError

    def __repr__(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    """Represents a successful result containing a value."""

    __match_args__ = ("value",)
    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def ok(self) -> T | None:
        return self.value

    def err(self) -> E | None:  # type: ignore[type-arg]
        return None

    def unwrap(self) -> T:
        return self.value

    def unwrap_err(self) -> E:  # type: ignore[type-arg]
        raise ValueError(f"Cannot unwrap_err on Ok({self.value!r})")

    def unwrap_or(self, default: T) -> T:
        return self.value

    def unwrap_or_else(self, fn: Callable[[E], T]) -> T:  # type: ignore[type-arg]
        return self.value

    def map(self, fn: Callable[[T], U]) -> Ok[U]:
        return Ok(fn(self.value))

    def map_err(self, fn: Callable[[E], U]) -> Ok[T]:  # type: ignore[type-arg]
        return self

    def flat_map(self, fn: Callable[[T], Result[U, E]]) -> Result[U, E]:  # type: ignore[type-arg]
        return fn(self.value)

    def flatten(self: Ok[Result[U, E]]) -> Result[U, E]:  # type: ignore[type-arg]
        return self.value

    def contains(self, value: T) -> bool:
        return self.value == value

    def contains_err(self, error: E) -> bool:  # type: ignore[type-arg]
        return False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Ok):
            return self.value == other.value
        return False

    def __repr__(self) -> str:
        return f"Ok({self.value!r})"

    def __bool__(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    """Represents a failed result containing an error."""

    __match_args__ = ("error",)
    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def ok(self) -> T | None:  # type: ignore[type-arg]
        return None

    def err(self) -> E | None:
        return self.error

    def unwrap(self) -> T:  # type: ignore[type-arg]
        raise ValueError(f"Cannot unwrap Err({self.error!r})")

    def unwrap_err(self) -> E:
        return self.error

    def unwrap_or(self, default: T) -> T:
        return default

    def unwrap_or_else(self, fn: Callable[[E], T]) -> T:
        return fn(self.error)

    def map(self, fn: Callable[[T], U]) -> Err[E]:  # type: ignore[type-arg]
        return self

    def map_err(self, fn: Callable[[E], U]) -> Err[U]:
        return Err(fn(self.error))

    def flat_map(self, fn: Callable[[T], Result[U, E]]) -> Err[E]:  # type: ignore[type-arg]
        return self

    def flatten(self: Err[Result[U, Any]]) -> Err[Result[U, Any]]:  # type: ignore[type-arg]
        return self

    def contains(self, value: T) -> bool:  # type: ignore[type-arg]
        return False

    def contains_err(self, error: E) -> bool:
        return self.error == error

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Err):
            return self.error == other.error
        return False

    def __repr__(self) -> str:
        return f"Err({self.error!r})"

    def __bool__(self) -> bool:
        return False
