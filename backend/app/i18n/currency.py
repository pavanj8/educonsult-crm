"""Per-tenant display-currency formatting utility (E52; Requirements §1 Currency).

The CRM exposes a configurable display/reporting currency per tenant (no live FX
conversion). The helpers in this module produce human-readable, locale-neutral
currency strings from a numeric ``amount`` and an ISO 4217 ``currency_code``.

Design constraints (intentionally narrow):

* The backend formatter is pure-Python and dependency-free so it works in every
  deployment target (SaaS, on-prem Docker, SQLite tests).
* The output is unambiguous across locales: ``"<amount> <CODE>"`` (e.g.
  ``"1,234.56 USD"``). Locale-specific symbol placement is intentionally avoided
  because the platform does not store user locale in this iteration and the
  frontend display components (E52 task #3) own locale-aware rendering via
  ``Intl.NumberFormat``.
* Only ISO 4217-style three-letter uppercase codes are accepted. Anything else
  raises :class:`InvalidCurrencyCodeError` so callers (the tenant validation
  layer in E52 task #1 and the API surface in future iterations) can rely on
  a hard contract.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from numbers import Real
from typing import Iterable, Union

AmountLike = Union[int, float, Decimal, Real]

# ISO 4217 three-letter currency codes. The curated subset covers the currencies
# the platform demonstrably needs (the source countries/universities in the
# canonical demo dataset reference INR, USD, EUR, GBP, CAD, AUD directly). The
# helpers below still accept any syntactically-valid ISO 4217 code so that
# future tenants with a different currency do not require a code change here;
# the curated list is the *known* set, not a closed allow-list.
DEFAULT_SUPPORTED_CURRENCY_CODES: frozenset[str] = frozenset(
    {
        "AUD",  # Australian dollar
        "CAD",  # Canadian dollar
        "EUR",  # Euro
        "GBP",  # Pound sterling
        "INR",  # Indian rupee (default for the platform's home market)
        "NZD",  # New Zealand dollar
        "SGD",  # Singapore dollar
        "USD",  # United States dollar
    }
)

_ISO_4217_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")


class InvalidCurrencyCodeError(ValueError):
    """Raised when a currency code is not a syntactically valid ISO 4217 code."""


def supported_currency_codes(
    additional_codes: Iterable[str] | None = None,
) -> frozenset[str]:
    """Return the set of ISO 4217 codes the helper recognises as well-known.

    ``additional_codes`` lets callers (e.g. future tenant onboarding flows) opt
    additional codes into the *known* set without mutating module state. Codes
    not in the returned set are still accepted by :func:`format_currency`
    provided they match the ISO 4217 shape.
    """
    if additional_codes is None:
        return DEFAULT_SUPPORTED_CURRENCY_CODES
    return DEFAULT_SUPPORTED_CURRENCY_CODES | frozenset(additional_codes)


def is_supported_currency_code(code: object) -> bool:
    """Return True when ``code`` is one of the well-known ISO 4217 codes."""
    return isinstance(code, str) and code in supported_currency_codes()


def normalize_currency_code(code: object) -> str:
    """Return the canonical uppercase form of ``code`` or raise.

    Whitespace is stripped and letters are upper-cased; non-letters or a wrong
    length cause :class:`InvalidCurrencyCodeError`. This is the single
    normalisation entry point so tenants can accept user-typed codes (``usd``,
    ``" usd "``) without each caller re-implementing the rules.
    """
    if not isinstance(code, str):
        raise InvalidCurrencyCodeError("Currency code must be a string")
    candidate = code.strip().upper()
    if not _ISO_4217_CODE_PATTERN.match(candidate):
        raise InvalidCurrencyCodeError(
            "Currency code must be a 3-letter uppercase ISO 4217 code"
        )
    return candidate


def format_currency(amount: AmountLike, currency_code: object) -> str:
    """Return a human-readable currency string for ``amount`` in ``currency_code``.

    The numeric ``amount`` may be an ``int``, ``float`` or any other
    :class:`numbers.Real` subclass (including :class:`decimal.Decimal`).
    Non-finite values (``float('inf')`` / ``float('nan')``) and unsupported
    numeric types raise :class:`ValueError` so callers can distinguish them
    from currency-code errors.

    Output format: ``"<amount> <CODE>"`` with thousands separators and up to
    six fractional digits (trailing zeros are dropped). Integer amounts
    render without a fractional part. Negative amounts are rendered with a
    leading minus sign (``"-1,234.56 USD"``), matching common accounting
    convention.
    """
    code = normalize_currency_code(currency_code)
    value = _normalize_amount(amount)
    integer_part, fractional_part = _split_integer_fraction(value)
    return f"{integer_part}.{fractional_part} {code}" if fractional_part else f"{integer_part} {code}"


def _normalize_amount(amount: object) -> Decimal:
    """Coerce ``amount`` into a finite, normalised :class:`Decimal` for formatting.

    The output has no trailing zeros and no scientific notation, which keeps the
    downstream ``format(value, "f")`` rendering predictable.

    Both :class:`numbers.Real` (int, float) and :class:`decimal.Decimal` are
    accepted; :class:`bool` is explicitly rejected because ``bool`` is a subclass
    of ``int`` and silently formatting ``True`` as ``"1 USD"`` would mask
    caller bugs.
    """
    if isinstance(amount, bool):
        raise ValueError("Currency amount must be numeric, not bool")
    if not isinstance(amount, (Real, Decimal)):
        raise ValueError("Currency amount must be a real number")

    try:
        decimal_value = Decimal(str(amount))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Currency amount is not a finite number") from exc

    if not decimal_value.is_finite():
        raise ValueError("Currency amount must be finite")

    if decimal_value == 0:
        return Decimal(0)
    return decimal_value.normalize()


def _split_integer_fraction(value: Decimal) -> tuple[str, str]:
    """Return ``(integer_with_separators, fraction_without_trailing_zeros)``.

    ``format(Decimal, "f")`` yields the canonical fixed-point representation
    after :meth:`Decimal.normalize` strips trailing zeros in
    :func:`_normalize_amount`. Values that need more than the natural
    fractional precision of the input are left alone (no rounding) so the
    formatter never silently drops a digit.
    """
    text = format(value, "f")
    if text.startswith("-"):
        sign = "-"
        body = text[1:]
    else:
        sign = ""
        body = text

    integer_part, _, fractional_part = body.partition(".")
    grouped = _group_thousands(integer_part)
    return f"{sign}{grouped}", fractional_part


def _group_thousands(digits: str) -> str:
    """Insert ``,`` separators every three digits from the right."""
    if len(digits) <= 3:
        return digits
    chunks = []
    index = len(digits)
    while index > 3:
        chunks.append(digits[index - 3 : index])
        index -= 3
    chunks.append(digits[:index])
    return ",".join(reversed(chunks))
