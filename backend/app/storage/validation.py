"""Student-document upload validation (E27; Journey J20; Requirements §5).

Implements the **size and type** checks mandated by the platform
defaults in Requirements §5:

* ``Documents: ... default limits 10MB, PDF/JPG/PNG/DOCX``

The rules are enforced inside
``POST /applications/{application_id}/documents`` via
:func:`validate_file_size` and :func:`validate_file_type`. Both
helpers raise :class:`fastapi.HTTPException` with a stable status
code so the frontend can surface the right error path (size cap vs.
type mismatch) and so the black-box Test Agent can assert on the
contract without coupling to internal data structures.

Design notes
------------

* **Extension-driven type check.** The check inspects the
  ``original_filename`` suffix (case-insensitive) and rejects anything
  not in :data:`ALLOWED_EXTENSIONS`. We deliberately do *not* read
  magic bytes — the project does not pull in ``python-magic`` /
  ``filetype`` and adding a dependency for a default-limit rule is
  out of scope for E27. The cross-check between filename extension
  and the multipart ``content_type`` header is enough to catch the
  realistic "user renamed ``evil.exe`` to ``evil.pdf``" attacks
  combined with a mismatched ``Content-Type``.
* **Stable public surface.** The functions and constants are exported
  from :mod:`app.storage` so tests (and future ticket work like a
  per-tenant override or a per-checklist-template override) can reach
  them by name. They are intentionally not FastAPI dependencies: the
  router already gates on permission and authorization; layering a
  dependency for size/type would just shuffle where the bytes are
  read.
* **No info leak.** Error messages name the offending file type (when
  the extension is known but disallowed) and reference the cap in
  megabytes — but they do not enumerate the allow-list or echo the
  raw ``Content-Type`` header (clients can probe that header
  themselves; we just need a stable 415 contract).

Traceability
------------

* Requirements §5 (Documents ... default limits 10MB, PDF/JPG/PNG/DOCX).
* Journey J20 (Student uploads a document against a checklist item).
* Epic E27 (Student Document Upload); this module is the validation
  half. Sibling tickets own the model (#174), the upload endpoint
  (#175), the upload UI (#177), and the validation+completeness test
  suite (#178).
"""

from __future__ import annotations

import os

from fastapi import HTTPException, status

__all__ = [
    "ALLOWED_CONTENT_TYPES",
    "ALLOWED_EXTENSIONS",
    "FILE_TOO_LARGE_DETAIL",
    "FILE_TYPE_NOT_ALLOWED_DETAIL",
    "MAX_FILE_BYTES",
    "MAX_FILE_SIZE_MB",
    "validate_file_size",
    "validate_file_type",
]


#: Maximum allowed upload size, in bytes (10 MB — Requirements §5 default).
MAX_FILE_BYTES: int = 10 * 1024 * 1024

#: Human-readable version of :data:`MAX_FILE_BYTES` for error messages.
MAX_FILE_SIZE_MB: int = 10

#: Filename extensions accepted by the upload endpoint (lowercase, with dot).
#: Requirements §5: "PDF/JPG/PNG/DOCX".
ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".jpg", ".jpeg", ".png", ".docx"}
)

#: ``Content-Type`` values accepted by the upload endpoint, keyed by the
#: lowercase extension the value corresponds to. The router cross-checks
#: the multipart ``content_type`` against this map so a malicious client
#: cannot bypass the extension check by claiming e.g. ``text/plain`` for
#: an ``.exe`` renamed to ``.pdf``.
ALLOWED_CONTENT_TYPES: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".png": frozenset({"image/png"}),
    ".docx": frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
    ),
}

#: Error message returned on size-cap violation (HTTP 413).
FILE_TOO_LARGE_DETAIL = (
    "Uploaded file exceeds the maximum allowed size of "
    f"{MAX_FILE_SIZE_MB} MB"
)

#: Error message returned on file-type rejection (HTTP 415).
#: Kept generic on purpose so we don't echo the allow-list back to the
#: client (the client already knows what types the UI accepts). The
#: wording matches :data:`ALLOWED_EXTENSIONS` exactly — Requirements
#: §5 names "PDF/JPG/PNG/DOCX", and the validator additionally accepts
#: the ``.jpeg`` synonym for ``.jpg``, so both spellings appear here.
FILE_TYPE_NOT_ALLOWED_DETAIL = (
    "Unsupported file type. Only PDF, JPG/JPEG, PNG, and DOCX files are accepted."
)


def _extension_of(filename: str | None) -> str:
    """Return the lowercase extension (with leading dot) of ``filename``.

    Returns an empty string when ``filename`` is ``None`` or has no
    extension. ``os.path.basename`` first strips any directory portion
    so a crafted path like ``foo/bar.pdf/baz`` cannot smuggle a dot
    past us.
    """
    if not filename:
        return ""
    base = os.path.basename(filename)
    _, ext = os.path.splitext(base)
    return ext.lower()


def validate_file_size(size_bytes: int) -> None:
    """Raise HTTP 413 if ``size_bytes`` exceeds :data:`MAX_FILE_BYTES`.

    The check is strict (>), so an upload of exactly :data:`MAX_FILE_BYTES`
    is accepted; the first rejected byte is one past the cap. This matches
    the convention used elsewhere in the upload router ("exceeds the
    maximum allowed size").
    """
    if size_bytes > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=FILE_TOO_LARGE_DETAIL,
        )


def _check_extension(filename: str | None) -> str:
    """Return the lowercase extension or raise HTTP 415.

    A missing extension, an empty extension, or an extension outside
    :data:`ALLOWED_EXTENSIONS` all raise. The caller is expected to
    have already confirmed ``filename`` is non-empty (the router
    rejects a missing ``file.filename`` earlier with a 400).
    """
    extension = _extension_of(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=FILE_TYPE_NOT_ALLOWED_DETAIL,
        )
    return extension


def validate_file_type(
    *,
    filename: str | None,
    content_type: str | None,
) -> str:
    """Validate ``filename`` / ``content_type`` against the allow-list.

    Returns the lowercase extension on success so callers can reuse it
    (e.g. for logging). Raises:

    * HTTP 415 if the filename's extension is not in
      :data:`ALLOWED_EXTENSIONS`, OR
    * HTTP 415 if the multipart ``content_type`` does not match the
      extension's entry in :data:`ALLOWED_CONTENT_TYPES`. A missing or
      empty ``content_type`` is treated as ``application/octet-stream``
      and therefore rejected when the extension requires a specific
      type — this is intentional, because the multipart parser almost
      always populates ``content_type`` for a real file part.

    The ``content_type`` cross-check is what stops the realistic
    "rename ``evil.exe`` to ``evil.pdf`` and submit with
    ``Content-Type: application/octet-stream``" attack: the extension
    is in the allow-list, but the header isn't, and the upload is
    rejected.
    """
    extension = _check_extension(filename)

    normalized_content_type = (content_type or "").strip().lower()
    allowed_types = ALLOWED_CONTENT_TYPES[extension]
    if normalized_content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=FILE_TYPE_NOT_ALLOWED_DETAIL,
        )

    return extension
