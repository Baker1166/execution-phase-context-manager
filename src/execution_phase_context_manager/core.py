"""Label every log record emitted inside a block with a phase identifier.

The library installs a single :class:`logging.Filter` on the root logger.
The filter reads the current phase from a :class:`threading.local` object
and copies it onto each record as ``record.phase``.  A context manager
sets and clears that thread-local value, so nested blocks restore the
previous phase instead of leaking it.

Why a filter and not a custom logger or adapter?  Filters are the only
stdlib hook that sees *every* record regardless of which logger created
it, and they run before handlers format the record.  That means a caller
can keep using ``logging.getLogger(__name__)`` everywhere and still get
the phase attached.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

__all__ = ["PhaseFilter", "phase_context"]


class _PhaseState(threading.local):
    """Thread-local storage for the active phase.

    Subclassing :class:`threading.local` gives each thread its own
    ``current`` attribute automatically, which is what we want: a phase
    started in one thread must not bleed into another.
    """

    def __init__(self) -> None:
        self.current: Optional[str] = None


_STATE = _PhaseState()


class PhaseFilter(logging.Filter):
    """Attach the current phase to every record that passes through.

    The filter never rejects a record.  It only writes ``record.phase``
    so formatters can reference ``%(phase)s``.  When no phase is active
    the attribute is set to ``None`` rather than omitted, because a
    formatter that references ``%(phase)s`` would otherwise raise on
    records logged outside any block.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.phase = _STATE.current
        return True


@contextmanager
def phase_context(phase: str) -> Iterator[None]:
    """Label log records emitted inside the ``with`` block.

    ``phase`` must be a non-empty string.  Empty strings are rejected
    because they are almost always a bug (a variable that was never
    assigned) and would produce records that look unlabelled while still
    carrying a falsy phase attribute.

    Nested blocks restore the outer phase on exit, so a helper that
    opens its own phase does not erase the caller's label.
    """
    if not isinstance(phase, str) or not phase:
        raise ValueError("phase must be a non-empty string")

    previous = _STATE.current
    _STATE.current = phase
    try:
        yield
    finally:
        _STATE.current = previous


def _install_filter() -> PhaseFilter:
    """Install one :class:`PhaseFilter` on the root logger.

    The filter is idempotent: repeated imports reuse the existing
    instance.  This keeps ``logging.getLogger().filters`` from growing
    without bound when the package is imported from several modules.
    """
    root = logging.getLogger()
    for existing in root.filters:
        if isinstance(existing, PhaseFilter):
            return existing
    filt = PhaseFilter()
    root.addFilter(filt)
    return filt


# Install eagerly so that callers do not have to remember a setup step.
_FILTER = _install_filter()

# Filters added directly to loggers (including the root logger) run after
# the record has been created but *before* handlers format it.  The root
# logger's filters are, however, only applied to records logged directly
# on the root logger, not to records propagated up from child loggers.
# To guarantee that every record carries ``record.phase``, patch the
# ``LogRecord`` factory so the attribute exists from creation time.
_original_log_record_init = logging.LogRecord.__init__


def _phase_aware_log_record_init(self, *args, **kwargs) -> None:
    _original_log_record_init(self, *args, **kwargs)
    self.phase = _STATE.current


logging.LogRecord.__init__ = _phase_aware_log_record_init
