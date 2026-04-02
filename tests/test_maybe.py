"""Tests for Maybe type."""

import pytest
from websearch.core.types.maybe import Just, Nothing, Maybe


class TestJust:
    """Tests for Just variant."""

    def test_is_just_returns_true(self):
        maybe = Just(42)
        assert maybe.is_just() is True

    def test_is_nothing_returns_false(self):
        maybe = Just(42)
        assert maybe.is_nothing() is False

    def test_just_value_returns_value(self):
        maybe = Just(42)
        assert maybe.just_value() == 42

    def test_bool_is_true(self):
        maybe = Just(42)
        assert bool(maybe) is True

    def test_map_transforms_value(self):
        maybe = Just(21)
        mapped = maybe.map(lambda x: x * 2)
        assert mapped == Just(42)

    def test_map_preserves_just(self):
        maybe: Maybe[int] = Just(0)
        mapped = maybe.map(lambda x: x + 1)
        assert mapped == Just(1)

    def test_flat_map_chains(self):
        def safe_divide(x: int, y: int) -> Maybe[float]:
            if y == 0:
                return Nothing()
            return Just(x / y)

        maybe = Just(10).flat_map(lambda x: safe_divide(x, 2))
        assert maybe == Just(5.0)

    def test_flat_map_with_nothing(self):
        def first_element(lst: list) -> Maybe[int]:
            if lst:
                return Just(lst[0])
            return Nothing()

        maybe = Just([]).flat_map(first_element)
        assert maybe == Nothing()

    def test_filter_keeps_matching(self):
        maybe = Just(42)
        filtered = maybe.filter(lambda x: x > 10)
        assert filtered == Just(42)

    def test_filter_removes_non_matching(self):
        maybe = Just(5)
        filtered = maybe.filter(lambda x: x > 10)
        assert filtered == Nothing()

    def test_get_or_else_returns_value(self):
        maybe = Just(42)
        assert maybe.get_or_else(100) == 42

    def test_get_or_else_from_returns_value(self):
        maybe = Just(42)
        assert maybe.get_or_else_from(lambda: 100) == 42

    def test_to_result_wraps_in_ok(self):
        maybe: Maybe[int] = Just(42)
        result = maybe.to_result("error")
        assert result.is_ok() and result.ok() == 42

    def test_contains_true(self):
        maybe = Just(42)
        assert maybe.contains(42) is True

    def test_contains_false(self):
        maybe = Just(42)
        assert maybe.contains(100) is False

    def test_eq_with_same_value(self):
        assert Just(42) == Just(42)

    def test_eq_with_different_value(self):
        assert Just(42) != Just(100)

    def test_eq_with_nothing(self):
        assert Just(42) != Nothing()

    def test_repr(self):
        assert repr(Just(42)) == "Just(42)"

    def test_value_attribute(self):
        just = Just(42)
        assert just.value == 42


class TestNothing:
    """Tests for Nothing variant."""

    def test_is_just_returns_false(self):
        assert Nothing().is_just() is False

    def test_is_nothing_returns_true(self):
        assert Nothing().is_nothing() is True

    def test_just_value_returns_none(self):
        assert Nothing().just_value() is None

    def test_bool_is_false(self):
        assert bool(Nothing()) is False

    def test_map_does_nothing(self):
        maybe: Maybe[int] = Nothing()
        mapped = maybe.map(lambda x: x * 2)
        assert mapped == Nothing()

    def test_flat_map_does_nothing(self):
        maybe: Maybe[int] = Nothing()
        chained = maybe.flat_map(lambda x: Just(x * 2))
        assert chained == Nothing()

    def test_filter_does_nothing(self):
        maybe: Maybe[int] = Nothing()
        filtered = maybe.filter(lambda x: x > 10)
        assert filtered == Nothing()

    def test_get_or_else_returns_default(self):
        assert Nothing().get_or_else(100) == 100

    def test_get_or_else_from_computes(self):
        call_count = 0
        def compute():
            nonlocal call_count
            call_count += 1
            return 42
        result = Nothing().get_or_else_from(compute)
        assert result == 42
        assert call_count == 1

    def test_to_result_wraps_in_err(self):
        maybe: Maybe[int] = Nothing()
        result = maybe.to_result("error")
        assert result.is_err() and result.err() == "error"

    def test_contains_always_false(self):
        assert Nothing().contains(42) is False

    def test_eq_with_nothing_instance(self):
        assert Nothing() == Nothing()

    def test_eq_with_nothing_class(self):
        # Nothing() (instance) should equal Nothing() (instance)
        assert Nothing() == Nothing()

    def test_eq_with_just(self):
        assert Nothing() != Just(42)

    def test_repr(self):
        assert repr(Nothing()) == "Nothing"


class TestMaybeChaining:
    """Tests for chaining multiple Maybe operations."""

    def test_map_chain(self):
        maybe = Just(10).map(lambda x: x + 5).map(lambda x: x * 2)
        assert maybe == Just(30)

    def test_flat_map_chain(self):
        def half(x: int) -> Maybe[float]:
            return Just(x / 2)

        def stringify(x: float) -> Maybe[str]:
            return Just(str(x))

        maybe = Just(20).flat_map(half).flat_map(stringify)
        assert maybe == Just("10.0")

    def test_filter_chain(self):
        maybe = Just(15).filter(lambda x: x > 10).filter(lambda x: x % 2 == 1)
        assert maybe == Just(15)

    def test_filter_rejects_early(self):
        maybe = Just(9).filter(lambda x: x > 10).filter(lambda x: x % 2 == 1)
        assert maybe == Nothing()

    def test_map_after_filter(self):
        maybe = Just(12).filter(lambda x: x > 10).map(lambda x: x * 2)
        assert maybe == Just(24)

    def test_map_after_filter_nothing(self):
        maybe = Just(5).filter(lambda x: x > 10).map(lambda x: x * 2)
        assert maybe == Nothing()


class TestMaybePatternMatching:
    """Tests for pattern matching with Maybe."""

    def test_match_just(self):
        maybe: Maybe[int] = Just(42)
        matched = None
        match maybe:
            case Just(value):
                matched = value
            case Nothing():
                matched = None
        assert matched == 42

    def test_match_nothing(self):
        maybe: Maybe[int] = Nothing()
        matched = "default"
        match maybe:
            case Just(value):
                matched = value
            case Nothing():
                matched = "nothing here"
        assert matched == "nothing here"

    def test_match_just_with_guard(self):
        maybe: Maybe[int] = Just(42)
        matched = None
        match maybe:
            case Just(value) if value > 0:
                matched = "positive"
            case Just(value):
                matched = "non-positive"
            case Nothing():
                matched = "nothing"
        assert matched == "positive"


class TestMaybeWithComplexTypes:
    """Tests for Maybe with complex generic types."""

    def test_with_list(self):
        maybe: Maybe[list[int]] = Just([1, 2, 3])
        assert maybe.map(lambda x: sum(x)) == Just(6)

    def test_with_dict(self):
        maybe: Maybe[dict[str, int]] = Just({"a": 1, "b": 2})
        assert maybe.map(lambda d: d["a"]) == Just(1)

    def test_with_none_value(self):
        maybe: Maybe[None] = Just(None)
        assert maybe.is_just()
        assert maybe.just_value() is None

    def test_with_string(self):
        maybe: Maybe[str] = Just("hello")
        assert maybe.map(str.upper) == Just("HELLO")


class TestMaybeBooleanContext:
    """Tests for using Maybe in boolean context."""

    def test_just_is_truthy(self):
        maybe = Just(42)
        if maybe:
            assert True
        else:
            pytest.fail("Just should be truthy")

    def test_nothing_is_falsey(self):
        maybe: Maybe[int] = Nothing()
        if maybe:
            pytest.fail("Nothing should be falsey")
        else:
            assert True

    def test_just_with_none_is_truthy(self):
        maybe: Maybe[None] = Just(None)
        assert bool(maybe) is True

    def test_just_with_zero_is_truthy(self):
        maybe: Maybe[int] = Just(0)
        assert bool(maybe) is True

    def test_just_with_empty_string_is_truthy(self):
        maybe: Maybe[str] = Just("")
        assert bool(maybe) is True

    def test_just_with_empty_list_is_truthy(self):
        maybe: Maybe[list] = Just([])
        assert bool(maybe) is True


class TestMaybeConversions:
    """Tests for converting between Maybe and other types."""

    def test_to_result_with_error(self):
        maybe: Maybe[int] = Nothing()
        result = maybe.to_result("was nothing")
        assert result.is_err() and result.err() == "was nothing"

    def test_to_result_just(self):
        maybe: Maybe[int] = Just(42)
        result = maybe.to_result("error")
        assert result.is_ok() and result.ok() == 42


class TestMaybeEdgeCases:
    """Edge case tests for Maybe."""

    def test_filter_preserves_nothing(self):
        """filter on Nothing should return Nothing regardless of predicate."""
        result: Maybe[int] = Nothing()
        for pred in [lambda x: True, lambda x: False, lambda x: x > 10]:
            assert result.filter(pred) == Nothing()

    def test_just_none_value(self):
        """Test that Just(None) is different from Nothing."""
        maybe_none: Maybe[None] = Just(None)
        assert maybe_none.is_just()
        assert maybe_none.just_value() is None
        assert maybe_none != Nothing()

    def test_nothing_instances_are_equal(self):
        """Multiple Nothing instances should be equal."""
        n1 = Nothing()
        n2 = Nothing()
        assert n1 == n2

    def test_nothing_is_hashable(self):
        """Nothing should be hashable."""
        s = {Nothing(), Nothing()}
        assert len(s) == 1

    def test_just_is_hashable(self):
        """Just values should be hashable."""
        s = {Just(1), Just(2), Just(1)}
        assert len(s) == 2
