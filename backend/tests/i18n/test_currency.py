"""Tests for the per-tenant currency formatting utility (E52; Requirements §1).

The currency formatter is a pure helper that the tenant model (E52 #241) and
the amount display components (E52 #243) both rely on. These tests pin down
the exact contract so neither side has to re-derive it from the implementation.
"""

from decimal import Decimal

import pytest

from app.i18n.currency import (
    DEFAULT_SUPPORTED_CURRENCY_CODES,
    InvalidCurrencyCodeError,
    format_currency,
    is_supported_currency_code,
    normalize_currency_code,
    supported_currency_codes,
)


class TestNormalizeCurrencyCode:
    def test_uppercases_lowercase_input(self):
        assert normalize_currency_code("usd") == "USD"

    def test_strips_surrounding_whitespace(self):
        assert normalize_currency_code("  inr  ") == "INR"

    def test_passes_through_valid_uppercase_code(self):
        assert normalize_currency_code("AUD") == "AUD"

    def test_accepts_three_letter_uppercase_codes_outside_default_set(self):
        # The formatter accepts any syntactically valid ISO 4217 code; the
        # *default supported* list is just a curated subset of well-known ones.
        assert normalize_currency_code("JPY") == "JPY"
        assert normalize_currency_code("CHF") == "CHF"

    @pytest.mark.parametrize(
        "bad_code",
        [
            "",
            "us",
            "usdd",
            "us1",
            "123",
            "US-",
            "us$",
            "U$D",
        ],
    )
    def test_rejects_malformed_string_codes(self, bad_code: str) -> None:
        with pytest.raises(InvalidCurrencyCodeError):
            normalize_currency_code(bad_code)

    @pytest.mark.parametrize("bad_code", [None, 123, 1.5, ["USD"], ("USD",), {"USD"}])
    def test_rejects_non_string_codes(self, bad_code: object) -> None:
        with pytest.raises(InvalidCurrencyCodeError):
            normalize_currency_code(bad_code)

    def test_invalid_code_error_subclasses_value_error(self):
        # Callers that broadly catch ValueError keep working with the new error.
        with pytest.raises(ValueError):
            normalize_currency_code("")


class TestSupportedCurrencyCodes:
    def test_default_set_is_non_empty_frozen(self):
        assert DEFAULT_SUPPORTED_CURRENCY_CODES
        # Frozen so callers cannot accidentally mutate the module-level default.
        with pytest.raises(AttributeError):
            DEFAULT_SUPPORTED_CURRENCY_CODES.add("XYZ")  # type: ignore[attr-defined]

    def test_default_set_contains_platform_home_currency(self):
        # Requirements §1 + demo seed: INR is the home-market currency.
        assert "INR" in DEFAULT_SUPPORTED_CURRENCY_CODES
        assert "USD" in DEFAULT_SUPPORTED_CURRENCY_CODES

    def test_supported_currency_codes_returns_frozenset(self):
        result = supported_currency_codes()
        assert isinstance(result, frozenset)
        assert result == DEFAULT_SUPPORTED_CURRENCY_CODES

    def test_supported_currency_codes_accepts_additional_codes(self):
        result = supported_currency_codes(["CHF", "JPY"])
        assert "CHF" in result
        assert "JPY" in result
        # Original defaults still present.
        assert "USD" in result
        # The helper does not mutate module state.
        assert "CHF" not in DEFAULT_SUPPORTED_CURRENCY_CODES

    def test_is_supported_currency_code_for_known_code(self):
        assert is_supported_currency_code("USD") is True

    def test_is_supported_currency_code_for_unknown_but_valid_code(self):
        # Valid ISO 4217 shape but not in the curated default set.
        assert is_supported_currency_code("JPY") is False

    def test_is_supported_currency_code_for_bad_input(self):
        assert is_supported_currency_code("usd") is False  # case sensitive
        assert is_supported_currency_code(None) is False
        assert is_supported_currency_code(123) is False
        assert is_supported_currency_code("") is False


class TestFormatCurrency:
    def test_formats_two_decimal_amount_with_thousands_separators(self):
        assert format_currency(1234.56, "USD") == "1,234.56 USD"

    def test_formats_seven_digit_amount_with_multiple_groups(self):
        assert format_currency(1234567.89, "INR") == "1,234,567.89 INR"

    def test_formats_amount_with_single_decimal_digit(self):
        assert format_currency(1234.5, "USD") == "1,234.5 USD"

    def test_integer_amount_omits_fractional_part(self):
        assert format_currency(1234, "USD") == "1,234 USD"

    def test_zero_amount_renders_as_zero(self):
        assert format_currency(0, "GBP") == "0 GBP"

    def test_zero_decimal_amount_renders_without_trailing_fraction(self):
        # Decimal('100.00') should normalise to Decimal('1E+2') and render as
        # "100" rather than the trailing-zero-heavy "100.00".
        assert format_currency(Decimal("100.00"), "USD") == "100 USD"

    def test_negative_amount_renders_with_leading_minus(self):
        assert format_currency(-1234.56, "EUR") == "-1,234.56 EUR"

    def test_negative_integer_amount_renders_with_leading_minus(self):
        assert format_currency(-42, "AUD") == "-42 AUD"

    def test_accepts_decimal_amount_with_full_precision(self):
        # High-precision Decimal values must not be silently rounded.
        assert format_currency(Decimal("1234567.89"), "INR") == "1,234,567.89 INR"

    def test_accepts_any_iso_4217_shape_code(self):
        # JPY is not in the curated default set, but the formatter still
        # accepts it because it is a valid ISO 4217 code.
        assert format_currency(123, "JPY") == "123 JPY"

    def test_uppercases_lowercase_currency_code(self):
        assert format_currency(100, "usd") == "100 USD"

    def test_strips_whitespace_around_currency_code(self):
        assert format_currency(100, " usd ") == "100 USD"

    def test_amount_with_no_integer_part_renders_leading_zero(self):
        assert format_currency(Decimal("0.5"), "USD") == "0.5 USD"

    def test_billion_amount_renders_with_all_groups(self):
        assert format_currency(1_000_000_000, "AUD") == "1,000,000,000 AUD"

    @pytest.mark.parametrize(
        "bad_code",
        ["", "US", "usdd", "123", "us1", "US$", None, 123, ["USD"]],
    )
    def test_rejects_invalid_currency_code(self, bad_code: object) -> None:
        with pytest.raises(InvalidCurrencyCodeError):
            format_currency(100, bad_code)

    @pytest.mark.parametrize("bad_amount", ["abc", None, True, False, [], object()])
    def test_rejects_non_numeric_amount(self, bad_amount: object) -> None:
        with pytest.raises(ValueError):
            format_currency(bad_amount, "USD")

    @pytest.mark.parametrize("bad_amount", [float("inf"), float("-inf"), float("nan")])
    def test_rejects_non_finite_amount(self, bad_amount: float) -> None:
        with pytest.raises(ValueError):
            format_currency(bad_amount, "USD")

    def test_rejects_bool_amount_explicitly(self):
        # ``bool`` is a subclass of ``int``; the formatter must not silently
        # turn ``True`` into ``"1 USD"``.
        with pytest.raises(ValueError, match="bool"):
            format_currency(True, "USD")  # type: ignore[arg-type]

    def test_format_returns_string(self):
        result = format_currency(0, "USD")
        assert isinstance(result, str)
