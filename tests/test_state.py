import pathlib
import tempfile
import threading
import unittest
from unittest.mock import patch

from netools.state import load_state, remove_instance, save_state, update_instance


class TestState(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = pathlib.Path(self.temp_dir.name) / "state.json"
        
        self.patcher = patch("netools.state.STATE_FILE", self.state_file)
        self.patcher.start()
        
    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()
        
    def test_load_state_default_when_missing(self):
        state = load_state()
        self.assertEqual(state, {"instances": {}, "updated_at": "", "pac_status": "inactive"})
        
    def test_save_and_load_roundtrip(self):
        test_state = {"instances": {"foo": {"port": 1234}}, "updated_at": "now", "pac_status": "active"}
        save_state(test_state)
        loaded = load_state()
        self.assertEqual(loaded, test_state)
        
    def test_update_instance(self):
        update_instance("test_inst", {"port": 9999})
        state = load_state()
        self.assertIn("test_inst", state["instances"])
        self.assertEqual(state["instances"]["test_inst"]["port"], 9999)
        
    def test_remove_instance(self):
        update_instance("test_inst", {"port": 9999})
        remove_instance("test_inst")
        state = load_state()
        self.assertNotIn("test_inst", state["instances"])
        
    def test_concurrent_thread_safety(self):
        def worker(idx):
            update_instance(f"inst_{idx}", {"port": 1000 + idx})
            
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        state = load_state()
        self.assertEqual(len(state["instances"]), 10)
        for i in range(10):
            self.assertIn(f"inst_{i}", state["instances"])
            self.assertEqual(state["instances"][f"inst_{i}"]["port"], 1000 + i)

if __name__ == "__main__":
    unittest.main()
