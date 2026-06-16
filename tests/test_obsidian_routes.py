"""Test Obsidian routing endpoints."""
import os
import sys
import tempfile
import unittest
from fastapi.testclient import TestClient

import importlib.util
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Load server.py module explicitly as server_app to avoid collision with the 'server' directory
server_file_path = os.path.join(parent_dir, "server.py")
spec = importlib.util.spec_from_file_location("server_app", server_file_path)
server_app = importlib.util.module_from_spec(spec)
sys.modules["server_app"] = server_app
spec.loader.exec_module(server_app)

class TestObsidianRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server_app.app)

    def test_status_unconfigured(self):
        old_val = server_app.CFG.get("obsidian_vault_path")
        server_app.CFG["obsidian_vault_path"] = ""
        try:
            response = self.client.get("/memory/obsidian/status")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "unconfigured")
            self.assertEqual(data["path"], "")
        finally:
            if old_val is not None:
                server_app.CFG["obsidian_vault_path"] = old_val

    def test_status_error(self):
        old_val = server_app.CFG.get("obsidian_vault_path")
        server_app.CFG["obsidian_vault_path"] = "C:\\invalid_directory_path_xyz_123"
        try:
            response = self.client.get("/memory/obsidian/status")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "error")
            self.assertEqual(data["path"], "C:\\invalid_directory_path_xyz_123")
        finally:
            if old_val is not None:
                server_app.CFG["obsidian_vault_path"] = old_val

    def test_status_connected_and_sync(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_val = server_app.CFG.get("obsidian_vault_path")
            server_app.CFG["obsidian_vault_path"] = tmpdir
            try:
                # 1. Test status connected
                response = self.client.get("/memory/obsidian/status")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["status"], "connected")
                self.assertEqual(data["path"], tmpdir)

                # 2. Test sync endpoint
                response = self.client.post("/memory/obsidian/sync")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["status"], "success")
                self.assertTrue(os.path.exists(data["file_path"]))
                
                # Check it default writes to the root if Inbox doesn't exist
                self.assertEqual(data["file_path"], os.path.join(tmpdir, "Mizune Memory.md"))

                # Now create Inbox directory
                os.makedirs(os.path.join(tmpdir, "Inbox"))
                response = self.client.post("/memory/obsidian/sync")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["status"], "success")
                self.assertEqual(data["file_path"], os.path.join(tmpdir, "Inbox", "Mizune Memory.md"))
                self.assertTrue(os.path.exists(data["file_path"]))
            finally:
                if old_val is not None:
                    server_app.CFG["obsidian_vault_path"] = old_val

if __name__ == "__main__":
    unittest.main()
