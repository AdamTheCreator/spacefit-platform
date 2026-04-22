"""Request-scoped logging helpers.

Provides a ``ContextVar`` for the current request's ID and a
``logging.Filter`` that attaches the ID to every ``LogRecord`` so logs
from deep inside the call stack can be correlated with the HTTP request
that triggered them.

Wiring lives in :mod:`app.main` — the middleware sets the ContextVar on
every request, the filter reads it on every log emission, and the
formatter in whichever handler is configured can include
``%(request_id)s`` in its format string.

The filter is installed idempotently alongside
:func:`app.core.scrubbing.install_scrubbing_filter`.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_INSTALLED_SENTINEL = "_request_id_filter_installed"


class _RequestIdFilter(logging.Filter):
    """Attach ``request_id`` to every ``LogRecord``.

    Reads the current value of :data:`request_id_var` at filter time so
    the correct ID is picked up regardless of which task is emitting
    the log.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def install_request_id_filter() -> None:
    """Attach the request-ID filter to the root logger and handlers.

    Idempotent. Safe to call during hot reload or from tests.
    """
    root = logging.getLogger()
    if getattr(root, _INSTALLED_SENTINEL, False):
        return

    flt = _RequestIdFilter()
    root.addFilter(flt)
    for handler in root.handlers:
        handler.addFilter(flt)

    setattr(root, _INSTALLED_SENTINEL, True)
