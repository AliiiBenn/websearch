"""Tests for Result type."""

import pytest
from websearch.core.types.result import Ok, Err, Result


class TestOk:
    """Tests for Ok variant."""

    def test_is_ok_returns_true(self):
        result = Ok(42)
        assert result.is_ok() is True

    def test_is_err_returns_false(self):
        result = Ok(42)
        assert result.is_err() is False

    def test_ok_returns_value(self):
        result = Ok(42)
        assert result.ok() == 42

    def test_err_returns_none(self):
        result = Ok("hello")
        assert result.err() is None

    def test_unwrap_returns_value(self):
        result = Ok(42)
        assert result.unwrap() == 42

    def test_unwrap_err_raises(self):
        result = Ok(42)
        with pytest.raises(ValueError, match="Cannot unwrap_err on Ok"):
            result.unwrap_err()

    def test_unwrap_or_returns_value(self):
        result = Ok(42)
        assert result.unwrap_or(100) == 42

    def test_unwrap_or_else_returns_value(self):
        result = Ok(42)
        assert result.unwrap_or_else(lambda e: 100) == 42

    def test_map_transforms_value(self):
        result = Ok(21)
        mapped = result.map(lambda x: x * 2)
        assert mapped == Ok(42)

    def test_map_err_does_nothing(self):
        result: Result[int, str] = Ok(42)
        mapped = result.map_err(lambda e: e.upper())
        assert mapped == Ok(42)

    def test_flat_map_chains_result(self):
        def divide_by_two(x: int) -> Result[int, str]:
            if x == 0:
                return Err("division by zero")
            return Ok(x // 2)

        result = Ok(10)
        chained = result.flat_map(divide_by_two)
        assert chained == Ok(5)

    def test_flat_map_with_err_in_fn(self):
        def risky(x: int) -> Result[int, str]:
            if x < 0:
                return Err("negative not allowed")
            return Ok(x * 2)

        result = Ok(-5)
        chained = result.flat_map(risky)
        assert chained == Err("negative not allowed")

    def test_flatten_unwraps_nested(self):
        inner: Result[int, str] = Ok(42)
        outer = Ok(inner)
        assert outer.flatten() == Ok(42)

    def test_flatten_with_err_inner(self):
        inner: Result[int, str] = Err("error")
        outer: Result[Result[int, str], str] = Ok(inner)
        assert outer.flatten() == Err("error")

    def test_contains_true(self):
        result = Ok(42)
        assert result.contains(42) is True

    def test_contains_false(self):
        result = Ok(42)
        assert result.contains(100) is False

    def test_contains_err_always_false(self):
        result: Result[int, str] = Ok(42)
        assert result.contains_err("error") is False

    def test_eq_with_same_value(self):
        assert Ok(42) == Ok(42)

    def test_eq_with_different_value(self):
        assert Ok(42) != Ok(100)

    def test_eq_with_err(self):
        assert Ok(42) != Err("error")

    def test_repr(self):
        assert repr(Ok(42)) == "Ok(42)"

    def test_match_ok(self):
        result: Result[int, str] = Ok(42)
        match result:
            case Ok(value):
                assert value == 42
            case Err():
                pytest.fail("Should not match Err")

    def test_value_attribute(self):
        ok = Ok(42)
        assert ok.value == 42

    def test_hashable(self):
        """Ok instances with same value should be hashable."""
        assert hash(Ok(42)) == hash(Ok(42))
        s = {Ok(1), Ok(2), Ok(1)}
        assert len(s) == 2

    def test_immutability(self):
        """Ok should be immutable (frozen dataclass)."""
        ok = Ok([1, 2, 3])
        with pytest.raises(AttributeError):
            ok.value = [4, 5, 6]


class TestErr:
    """Tests for Err variant."""

    def test_is_ok_returns_false(self):
        result = Err("error")
        assert result.is_ok() is False

    def test_is_err_returns_true(self):
        result = Err("error")
        assert result.is_err() is True

    def test_ok_returns_none(self):
        result = Err("error")
        assert result.ok() is None

    def test_err_returns_error(self):
        result = Err("error")
        assert result.err() == "error"

    def test_unwrap_raises(self):
        result = Err("error")
        with pytest.raises(ValueError, match="Cannot unwrap Err"):
            result.unwrap()

    def test_unwrap_err_returns_error(self):
        result = Err("error")
        assert result.unwrap_err() == "error"

    def test_unwrap_or_returns_default(self):
        result: Result[int, str] = Err("error")
        assert result.unwrap_or(100) == 100

    def test_unwrap_or_else_computes_default(self):
        result: Result[int, str] = Err("error")
        computed = result.unwrap_or_else(lambda e: len(e) * 10)
        assert computed == 50  # len("error") * 10

    def test_map_does_nothing(self):
        result: Result[int, str] = Err("error")
        mapped = result.map(lambda x: x * 2)
        assert mapped == Err("error")

    def test_map_err_transforms_error(self):
        result: Result[int, str] = Err("error")
        mapped = result.map_err(lambda e: e.upper())
        assert mapped == Err("ERROR")

    def test_flat_map_does_nothing(self):
        def risky(x: int) -> Result[int, str]:
            if x < 0:
                return Err("negative")
            return Ok(x * 2)

        result: Result[int, str] = Err("original error")
        chained = result.flat_map(risky)
        assert chained == Err("original error")

    def test_flatten_preserves_err(self):
        inner: Result[int, str] = Err("error")
        outer: Result[Result[int, str], str] = Err(inner)
        # Err flatten is a no-op since we can't unwrap an Err
        assert outer.flatten() == Err(inner)

    def test_contains_always_false(self):
        result: Result[int, str] = Err("error")
        assert result.contains(42) is False

    def test_contains_err_true(self):
        result: Result[int, str] = Err("error")
        assert result.contains_err("error") is True

    def test_contains_err_false(self):
        result: Result[int, str] = Err("error")
        assert result.contains_err("different") is False

    def test_eq_with_same_error(self):
        assert Err("error") == Err("error")

    def test_eq_with_different_error(self):
        assert Err("error") != Err("different")

    def test_eq_with_ok(self):
        assert Err("error") != Ok(42)

    def test_repr(self):
        assert repr(Err("error")) == "Err('error')"

    def test_match_err(self):
        result: Result[int, str] = Err("error")
        match result:
            case Ok():
                pytest.fail("Should not match Ok")
            case Err(error):
                assert error == "error"

    def test_error_attribute(self):
        err = Err("error")
        assert err.error == "error"

    def test_hashable(self):
        """Err instances with same error should be hashable."""
        assert hash(Err("error")) == hash(Err("error"))
        s = {Err("a"), Err("b"), Err("a")}
        assert len(s) == 2


class TestResultChaining:
    """Tests for chaining multiple Result operations."""

    def test_and_then_chain(self):
        def parse_int(s: str) -> Result[int, ValueError]:
            try:
                return Ok(int(s))
            except ValueError as e:
                return Err(e)

        def double(x: int) -> Result[int, ValueError]:
            return Ok(x * 2)

        result = Ok("42").flat_map(parse_int).flat_map(double)
        assert result == Ok(84)

    def test_and_then_chain_with_error(self):
        def parse_int(s: str) -> Result[int, ValueError]:
            try:
                return Ok(int(s))
            except ValueError as e:
                return Err(e)

        def double(x: int) -> Result[int, ValueError]:
            return Ok(x * 2)

        result = Ok("not a number").flat_map(parse_int).flat_map(double)
        assert isinstance(result, Err)

    def test_map_maintains_error(self):
        def failing_parse(s: str) -> Result[int, str]:
            return Err(f"cannot parse: {s}")

        result = failing_parse("42").map(lambda x: x * 2)
        assert result == Err("cannot parse: 42")

    def test_recover_from_error(self):
        def safe_divide(x: int, y: int) -> Result[int, str]:
            if y == 0:
                return Err("division by zero")
            return Ok(x // y)

        result = safe_divide(10, 0)
        recovered = result.map_err(lambda e: f"Error: {e}")
        assert recovered == Err("Error: division by zero")


class TestResultPatternMatching:
    """Tests for pattern matching with Result."""

    def test_match_ok_branch(self):
        result: Result[int, str] = Ok(42)
        matched = None
        match result:
            case Ok(value) if value > 0:
                matched = f"positive: {value}"
            case Ok(value):
                matched = f"non-positive: {value}"
            case Err(error):
                matched = f"error: {error}"
        assert matched == "positive: 42"

    def test_match_err_branch(self):
        result: Result[int, str] = Err("not found")
        matched = None
        match result:
            case Ok(value):
                matched = f"got: {value}"
            case Err(error):
                matched = f"error: {error}"
        assert matched == "error: not found"

    def test_match_with_guard(self):
        def classify(x: int) -> Result[str, str]:
            if x > 0:
                return Ok("positive")
            elif x < 0:
                return Err("negative not allowed")
            else:
                return Err("zero not allowed")

        result = classify(-5)
        match result:
            case Ok(label):
                matched = label
            case Err(e):
                matched = f"rejected: {e}"
        assert matched == "rejected: negative not allowed"


class TestResultWithComplexTypes:
    """Tests for Result with complex generic types."""

    def test_with_list(self):
        result: Result[list[int], str] = Ok([1, 2, 3])
        assert result.map(lambda x: sum(x)) == Ok(6)

    def test_with_dict(self):
        result: Result[dict[str, int], str] = Ok({"a": 1, "b": 2})
        assert result.map(lambda d: d["a"]) == Ok(1)

    def test_with_nested_tuple(self):
        result: Result[tuple[int, str], float] = Ok((42, "hello"))
        assert result.map(lambda t: t[0]) == Ok(42)

    def test_with_optional_value(self):
        from typing import Optional
        result: Result[Optional[str], int] = Ok(None)
        assert result.is_ok()
        assert result.ok() is None

    def test_with_none_error(self):
        from typing import Optional
        result: Result[int, Optional[str]] = Err(None)
        assert result.is_err()
        assert result.err() is None


class TestResultBooleanContext:
    """Tests for using Result in boolean context."""

    def test_ok_is_truthy(self):
        result: Result[int, str] = Ok(42)
        if result:
            assert True
        else:
            pytest.fail("Ok should be truthy")

    def test_err_is_falsey(self):
        result: Result[int, str] = Err("error")
        if result:
            pytest.fail("Err should be falsey")
        else:
            assert True
