"""Unit tests for the browser's process boundary; no Qt installation is needed."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from browser.browser_adapter import BrowserAdapter, BROWSER_ENTRY


class FakeProcess:
    def __init__(self, running=True):
        self.running = running

    def poll(self):
        return None if self.running else 0


class BrowserAdapterTests(unittest.TestCase):
    def test_launch_passes_url_to_browser_and_isolates_data_dir(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = BrowserAdapter(td)
            process = FakeProcess()
            with patch("browser.browser_adapter.subprocess.Popen", return_value=process) as popen:
                returned = adapter.launch("https://example.com/path?q=private")
            self.assertIs(returned, process)
            self.assertEqual(popen.call_args.args[0][0], os.sys.executable)
            self.assertEqual(Path(popen.call_args.args[0][1]), BROWSER_ENTRY)
            self.assertEqual(popen.call_args.args[0][-1], "https://example.com/path?q=private")
            self.assertEqual(popen.call_args.kwargs["env"]["DILARA_BROWSER_DATA"], str(Path(td).resolve()))
            self.assertTrue(adapter.is_running())

    def test_duplicate_launch_is_rejected(self):
        adapter = BrowserAdapter()
        process = FakeProcess()
        with patch("browser.browser_adapter.subprocess.Popen", return_value=process) as popen:
            adapter.launch()
            with self.assertRaisesRegex(RuntimeError, "already running"):
                adapter.launch()
        popen.assert_called_once()

    def test_exited_process_can_be_relaunched(self):
        adapter = BrowserAdapter()
        process = FakeProcess(running=False)
        with patch("browser.browser_adapter.subprocess.Popen", return_value=process) as popen:
            adapter.launch()
            self.assertFalse(adapter.is_running())
            adapter.launch()
        self.assertEqual(popen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
