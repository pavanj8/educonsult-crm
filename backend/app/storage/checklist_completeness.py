"""Checklist completeness calculation (E27; Journey J20; Requirements §5).

Computes a small :class:`ChecklistCompletenessSummary` from the merged
checklist view returned by the E26
``GET /applications/{application_id}/checklist`` endpoint. The summary
is a pure function of the items list — no DB, no I/O — so it can be
called from the endpoint, from background jobs, or from the test suite
without any setup.

Why a separate helper?
----------------------

The E27 ticket scope is *"upload validation and checklist completeness
calculation"* (issue #178). The merged checklist view (Journey J19)
already tells the frontend whether each row has an upload and what
status that upload is in, but it doesn't tell the frontend *"is the
student done with their documents yet?"* — that is the completeness
calculation, and it lives here so the same logic drives:

* the live ``GET /applications/{id}/checklist`` response (optional —
  the frontend can derive it client-side too),
* the unit tests in ``tests/student_documents/test_checklist_completeness.py``,
  which exercise the helper in isolation,
* any future audit / notification / stage-progression rule that wants
  to know "are all required documents approved yet?" (e.g. unlocking
  the ``OFFER_LETTER`` stage transition).

Design notes
------------

* **Pure function of the input items.** The helper takes any iterable
  of items that quacks like :class:`app.schemas.checklist.ChecklistItemView`
  (``required`` bool + ``upload`` whose ``status`` may be ``None`` or a
  :class:`StudentDocumentStatus` value). It does not import the ORM or
  Pydantic types so it can be tested with simple dataclasses.
* **Required-only counting.** Only ``required=True`` items count toward
  completeness — optional items are excluded so a missing optional
  upload does not block the student. This matches Requirements §5
  ("checklist templates ... required flag") and Journey J22 ("Document
  Verifier approves a document"), where the only thing that gates
  forward progress is the required set.
* **Approved-only "is_complete".** A pending or rejected required item
  keeps the checklist incomplete, even if the student has *uploaded*
  it. This matches the verifier workflow: only an explicit
  approval (Journey J22) counts as "done" — a pending upload is still
  under review, and a rejected one needs the E31 re-upload flow.
* **Zero-required short-circuit.** When there are no required items
  (``is_complete`` would vacuously be True), we still return a
  well-formed summary so callers don't need a special case.

Traceability
------------

* Requirements §5 (per-stage/program checklist templates; required
  flag).
* Journey J20 (Student uploads a document against a checklist item)
  — the completeness summary is what makes "all uploads done" a
  checkable property on top of the per-item upload state.
* Epic E27 (Student Document Upload); this helper is the
  completeness-calculation half. The matching test suite is sibling
  ticket #178.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

__all__ = [
    "ChecklistCompletenessSummary",
    "ChecklistCompletenessItem",
    "compute_checklist_completeness",
]


class ChecklistCompletenessItem(Protocol):
    """Structural type for the items the completeness helper consumes.

    Anything that quacks like this — Pydantic models, dataclasses,
    mocks, plain dicts with ``.required`` / ``.upload`` attributes —
    works without an explicit import of the schema module. Keeping
    this as a :class:`Protocol` is what lets the helper stay pure and
    unit-testable without dragging the ORM or the Pydantic dependency
    graph into every test.
    """

    @property
    def required(self) -> bool: ...

    @property
    def upload(self) -> "ChecklistCompletenessUpload | None": ...


class ChecklistCompletenessUpload(Protocol):
    """Structural type for an item's upload sub-object.

    ``status`` mirrors :class:`app.models.student_document.StudentDocumentStatus`
    (``pending`` / ``approved`` / ``rejected``). The helper compares
    against the string values rather than importing the enum so it
    stays decoupled from the ORM layer (and so tests can pass plain
    strings).
    """

    @property
    def status(self) -> str: ...


def _get_required(item: object) -> bool:
    """Return ``item.required`` for either attribute-style or dict-style access.

    The helper accepts two flavours of input:

    * ORM/Pydantic/dataclass items with a ``.required`` attribute
      (the documented public contract).
    * Plain ``dict`` items — useful when the helper is called against
      the JSON body of a live endpoint response, where Pydantic
      serialisation has already flattened the model to dicts.

    Both are first-class; the ``isinstance(item, dict)`` branch exists
    *only* so the helper can be applied directly to ``response.json()``
    output without an extra reconstruction step in tests and callers.
    """
    if isinstance(item, dict):
        return bool(item.get("required", False))
    return bool(item.required)


def _get_upload(item: object) -> object | None:
    """Return ``item.upload`` for either attribute-style or dict-style access."""
    if isinstance(item, dict):
        return item.get("upload")
    return item.upload


def _get_upload_status(upload: object | None) -> str | None:
    """Return ``upload.status`` (or ``None`` for a missing upload).

    Mirrors :func:`_get_required` for the nested upload object. A
    ``None`` upload (the "no upload yet" case) returns ``None``;
    anything else extracts the status string, treating dict and
    attribute access symmetrically.
    """
    if upload is None:
        return None
    if isinstance(upload, dict):
        status = upload.get("status")
        return str(status) if status is not None else None
    return str(upload.status)


#: The set of upload-status values that count as "the required item is
#: done" for the purposes of completeness. Anything outside this set —
#: ``"pending"``, ``"rejected"``, or no upload at all — leaves the
#: required item incomplete. The check is string-based (rather than
#: against the enum) so the helper stays ORM-free; the strings match
#: :class:`app.models.student_document.StudentDocumentStatus.APPROVED.value`
#: exactly.
_APPROVED_STATUS_VALUE = "approved"


@dataclass(frozen=True)
class ChecklistCompletenessSummary:
    """The aggregate completeness of one application's checklist.

    Attributes
    ----------
    total_items:
        Total number of templates on the checklist (required + optional).
    required_items:
        Number of templates flagged ``required=True``.
    optional_items:
        Number of templates flagged ``required=False``.
    approved_count:
        Number of *required* templates with an upload in
        ``approved`` status. Optional items do not contribute.
    pending_count:
        Number of *required* templates with a ``pending`` upload.
    rejected_count:
        Number of *required* templates with a ``rejected`` upload.
    missing_count:
        Number of *required* templates with no upload yet.
    is_complete:
        ``True`` iff every required template has an approved upload
        (i.e. ``approved_count == required_items``). Vacuously
        ``True`` when there are no required templates.
    """

    total_items: int
    required_items: int
    optional_items: int
    approved_count: int
    pending_count: int
    rejected_count: int
    missing_count: int
    is_complete: bool


def compute_checklist_completeness(
    items: Iterable[ChecklistCompletenessItem],
) -> ChecklistCompletenessSummary:
    """Return a :class:`ChecklistCompletenessSummary` for ``items``.

    Iterates ``items`` exactly once; safe to pass a generator (we use
    it only via the count accumulators below). The input shape matches
    what the E26 endpoint returns in its ``items`` list — every row
    has a ``required`` flag and an ``upload`` whose ``status`` is
    either ``None`` (no upload yet) or one of
    :class:`StudentDocumentStatus`'s string values.

    Counting rules (see module docstring for the rationale):

    * ``total_items`` counts every item, required or optional.
    * ``required_items`` / ``optional_items`` partition the totals.
    * ``approved_count``, ``pending_count``, ``rejected_count``, and
      ``missing_count`` all count only *required* items. Optional
      items with an upload do not contribute (they're not gating
      progress).
    * ``is_complete`` is ``approved_count == required_items`` (which
      is vacuously ``True`` when there are zero required items).

    Examples
    --------
    Empty checklist::

        >>> compute_checklist_completeness([])
        ChecklistCompletenessSummary(
            total_items=0, required_items=0, optional_items=0,
            approved_count=0, pending_count=0, rejected_count=0,
            missing_count=0, is_complete=True,
        )

    One required template with no upload::

        >>> # ... pending_count=0, rejected_count=0,
        >>> # ... missing_count=1, is_complete=False
    """
    total_items = 0
    required_items = 0
    optional_items = 0
    approved_count = 0
    pending_count = 0
    rejected_count = 0
    missing_count = 0

    for item in items:
        total_items += 1
        if _get_required(item):
            required_items += 1
            upload = _get_upload(item)
            status = _get_upload_status(upload) if upload is not None else None
            if status is None:
                # No upload at all OR an upload with no resolvable status
                # (defensive: the E26 schema guarantees one or the other,
                # but a future refactor must not silently mis-classify).
                missing_count += 1
            elif status == _APPROVED_STATUS_VALUE:
                approved_count += 1
            elif status == "pending":
                pending_count += 1
            elif status == "rejected":
                rejected_count += 1
            # Any other status (forward-compat enum value) is treated as
            # "not done" — we deliberately do not raise so a future enum
            # addition cannot crash a built/deployed release.
        else:
            optional_items += 1

    is_complete = approved_count == required_items

    return ChecklistCompletenessSummary(
        total_items=total_items,
        required_items=required_items,
        optional_items=optional_items,
        approved_count=approved_count,
        pending_count=pending_count,
        rejected_count=rejected_count,
        missing_count=missing_count,
        is_complete=is_complete,
    )
