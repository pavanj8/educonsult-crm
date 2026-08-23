"""Test-only helper for the E49 SMTP-abstraction mock-friendliness test.

Lives under ``tests/email/`` because it is exclusively used by
``tests/email/test_e49_abstraction.py``. The point is to demonstrate
that the abstraction can be intercepted by patching
``<caller_module>.send_email`` rather than by reaching into
``smtplib.SMTP`` — the contract every other consumer of the E49
abstraction relies on (E49 wiring ticket #234, E49 mocked-SMTP tests
#235, and the existing E6 / E8 unit tests).
"""

from app.email.service import send_email


def send_a_via_abstraction(*, to: str, subject: str, body_text: str) -> None:
    """Trivial caller so the patch-from-caller test has a real target.

    The function name intentionally mirrors the future E49 hooks
    (issue #234 will look like ``notify_and_email(...)``) so the
    patch surface is the same shape callers will see.
    """
    send_email(to=to, subject=subject, body_text=body_text)
