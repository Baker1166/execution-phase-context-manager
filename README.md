# execution-phase-context-manager

Label every log record emitted inside a block with a shared phase identifier, so records from one run can be grouped without threading an explicit tag through every call site.

```python
import logging

from execution_phase_context_manager import phase_context

logging.basicConfig(format="%(phase)s %(name)s %(message)s")

with phase_context("import-2024-06-01"):
    logging.getLogger("loader").info("reading rows")
    logging.getLogger("loader").info("validating rows")

logging.getLogger("loader").info("done")
```

The first two lines are prefixed with `import-2024-06-01`; the last line is prefixed with `None`.

## Why this exists

The usual way to group log records per run is to pass a run id into every logging call, or to build a `LoggerAdapter` for each subsystem. Both leak the identifier into function signatures and force callers to remember it. A `logging.Filter` is the one stdlib hook that sees every record from every logger, so this library installs a single filter on the root logger and lets a context manager set the phase on a `threading.local`.

The trade-off: the phase is global to the thread, not to a logger object. If two unrelated parts of a thread log at the same time, they share the phase. That is the point for run grouping, but it means the library is not suitable for labelling records with a per-call tag. Use `LoggerAdapter` for that.

## Edge cases

- A phase is required to be a non-empty `str`; `phase_context("")` and `phase_context(123)` raise `ValueError` immediately rather than producing unlabelled-looking records.
- Nested `with` blocks restore the outer phase on exit, including when the inner block raises.
- Threads do not share phases. A phase set in one thread is invisible to another thread's records.
- Records logged outside any block get `record.phase = None` so a `%(phase)s` format string does not raise.
