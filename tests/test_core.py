import io
import logging
import threading
import unittest

from execution_phase_context_manager import PhaseFilter, phase_context


class PhaseContextTests(unittest.TestCase):
    def setUp(self):
        # Capture records without touching the global handler configuration
        # that other tests or the host application may rely on.
        self.records = []

        class Capture(logging.Handler):
            def emit(inner_self, record):
                self.records.append(record)

        self.handler = Capture()
        self.handler.setLevel(logging.DEBUG)
        root = logging.getLogger()
        root.addHandler(self.handler)
        self._old_level = root.level
        root.setLevel(logging.DEBUG)

    def tearDown(self):
        root = logging.getLogger()
        root.removeHandler(self.handler)
        root.setLevel(self._old_level)

    def test_record_gets_phase_inside_block(self):
        with phase_context("run-42"):
            logging.getLogger("example").info("hello")
        self.assertEqual(len(self.records), 1)
        self.assertEqual(self.records[0].phase, "run-42")

    def test_record_outside_block_has_none_phase(self):
        logging.getLogger("example").info("no phase")
        self.assertEqual(len(self.records), 1)
        self.assertIsNone(self.records[0].phase)

    def test_phase_is_cleared_after_block(self):
        with phase_context("run-1"):
            logging.getLogger("example").info("inside")
        logging.getLogger("example").info("outside")
        self.assertEqual(self.records[0].phase, "run-1")
        self.assertIsNone(self.records[1].phase)

    def test_nested_blocks_restore_outer_phase(self):
        with phase_context("outer"):
            logging.getLogger("example").info("a")
            with phase_context("inner"):
                logging.getLogger("example").info("b")
            logging.getLogger("example").info("c")
        self.assertEqual([r.phase for r in self.records], ["outer", "inner", "outer"])

    def test_phase_is_restored_when_block_raises(self):
        with self.assertRaises(RuntimeError):
            with phase_context("boom"):
                logging.getLogger("example").info("before")
                raise RuntimeError("stop")
        logging.getLogger("example").info("after")
        self.assertEqual([r.phase for r in self.records], ["boom", None])

    def test_empty_phase_is_rejected(self):
        with self.assertRaises(ValueError):
            with phase_context(""):
                pass

    def test_non_string_phase_is_rejected(self):
        with self.assertRaises(ValueError):
            with phase_context(123):  # type: ignore[arg-type]
                pass

    def test_threads_do_not_share_phase(self):
        # The filter reads thread-local state, so a phase set in one
        # thread must not appear on records logged from another.
        other_records = []
        ready = threading.Event()
        release = threading.Event()

        def worker():
            ready.set()
            release.wait()
            logging.getLogger("worker").info("from worker")

        thread = threading.Thread(target=worker)
        thread.start()
        ready.wait()
        with phase_context("main-phase"):
            release.set()
            thread.join()
        self.assertEqual(len(self.records), 1)
        self.assertIsNone(self.records[0].phase)
        # The main thread's record inside the block is the one that got
        # the phase; the worker's record is the one captured above.
        self.assertEqual(self.records[0].name, "worker")

    def test_filter_does_not_reject_records(self):
        filt = PhaseFilter()
        record = logging.LogRecord(
            name="x", level=logging.INFO, pathname=__file__, lineno=1,
            msg="m", args=(), exc_info=None,
        )
        self.assertTrue(filt.filter(record))
        self.assertIsNone(record.phase)

    def test_formatter_can_reference_phase(self):
        formatter = logging.Formatter("%(phase)s|%(message)s")
        with phase_context("fmt"):
            logging.getLogger("example").info("hi")
        record = self.records[0]
        self.assertEqual(formatter.format(record), "fmt|hi")

    def test_formatter_handles_missing_phase(self):
        formatter = logging.Formatter("%(phase)s|%(message)s")
        logging.getLogger("example").info("hi")
        record = self.records[0]
        self.assertEqual(formatter.format(record), "None|hi")


if __name__ == "__main__":
    unittest.main()
