"""Public surface for execution-phase-context-manager.

Only :class:`PhaseFilter` and :func:`phase_context` are exported.  The
filter is intentionally a plain :class:`logging.Filter` so it composes with
any handler configuration a caller already has; the context manager is the
only supported way to install it because the filter mutates shared thread
local state.
"""

from .core import PhaseFilter, phase_context

__all__ = ["PhaseFilter", "phase_context"]
