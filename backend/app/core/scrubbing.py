"""Log-level secret scrubbing.

Installs a :class:`logging.Filter` on the root logger that rewrites any
log record whose formatted message contains a known API-key pattern.
The filter runs before a handler writes the record, so both stdout and
any aggregator (Datadog, Loki, etc.) see the scrubbed form.

This is defence-in-depth. The *primary* protection is that BYOK code
paths never put plaintext key material into log calls in the first
place; this filter catches accidents — a stray ``logger.info(payload)``
during debugging, a provider SDK that logs its own headers, a
traceback that happened to capture a local variable.

Wiring: :func:`install_scrubbing_filter` is called once from
:mod:`app.main` before any router is included. The filter is
idempotent — re-installing it is harmless.
"""

from __future__ import annotations

import logging

from app.llm.redaction import redact_secrets

_INSTALLED_SENTINEL = "_byok_scrubber_installed"


class _SecretScrubFilter(logging.Filter):
    """Redacts known API-key patterns from every :class:`LogRecord`.

    The trick is *when* to scrub. Python's ``logging`` defers the
    ``msg % args`` format step until a handler calls
    :meth:`LogRecord.getMessage`. If we only scrub ``record.msg``, an
    exception or object passed via ``args`` whose ``__str__`` contains
    a key still leaks once the handler formats the record.

    The reliable fix: call ``getMessage()`` ourselves, scrub the
    fully-formatted string, write it back to ``record.msg``, and clear
    ``record.args`` so handlers don't try to format again.

    We also scrub ``record.exc_text`` because ``logger.exception()``
    eventually caches a formatted traceback there — and tracebacks can
    carry local variables that hold key material.

    The filter never blocks a record; it always returns True.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Render now, scrub once, neutralize args so handlers don't
            # re-apply %-formatting on something we've already touched.
            rendered = record.getMessage()
            scrubbed = redact_secrets(rendered)
            if scrubbed != rendered or record.args:
                record.msg = scrubbed
                record.args = None

            # exc_text is populated lazily by Formatter.format(); if a
            # previous handler pre-formatted it, scrub that too.
            if record.exc_text:
                record.exc_text = redact_secrets(record.exc_text)
        except Exception:
            # A filter raising would be worse than a leak in this path —
            # it could crash the logger and silence everything. Swallow.
            pass
        return True


def install_scrubbing_filter() -> None:
    """Attach the scrub filter to the root logger and every existing
    handler.

    Idempotent — looks for a sentinel attribute on the root logger to
    detect prior installation. Safe to call from hot reload paths or
    tests that import :mod:`app.main` multiple times.
    """
    root = logging.getLogger()
    if getattr(root, _INSTALLED_SENTINEL, False):
        return

    flt = _SecretScrubFilter()
    root.addFilter(flt)
    for handler in root.handlers:
        handler.addFilter(flt)

    setattr(root, _INSTALLED_SENTINEL, True)
