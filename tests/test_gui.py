"""Tests for Forge Desktop GUI endpoints and controller."""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from forge.db import create_approval, init_db
from forge.gui.app import create_gui_app


class TestDesktopGUI(unittest.TestCase):
    """Test GUI Flask backend routes and API."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="forge_gui_test_")
        self.orig_cwd = os.getcwd()
        os.chdir(self.test_dir)
        init_db()

        self.app = create_gui_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_gui_index_serves_html(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("FORGE", resp.get_data(as_text=True))
        self.assertIn("DESKTOP", resp.get_data(as_text=True))

    def test_workspace_endpoint(self):
        # Create a sample file
        test_file = Path(self.test_dir) / "sample.py"
        test_file.write_text("print('gui test')", encoding="utf-8")

        resp = self.client.get("/api/workspace")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["cwd"], self.test_dir)
        names = [f["name"] for f in data["files"]]
        self.assertIn("sample.py", names)

    def test_file_read_and_save(self):
        sample = Path(self.test_dir) / "app.py"
        sample.write_text("x = 10", encoding="utf-8")

        # Read
        resp = self.client.get("/api/file?path=app.py")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["content"], "x = 10")

        # Save
        save_resp = self.client.post("/api/file", json={"path": "app.py", "content": "x = 20"})
        self.assertEqual(save_resp.status_code, 200)
        self.assertEqual(sample.read_text(encoding="utf-8"), "x = 20")

    def test_models_endpoint(self):
        resp = self.client.get("/api/models")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("ollama", data)
        self.assertIn("current", data)

    def test_approvals_endpoint(self):
        appr_id = create_approval("task_gui", "write_file", {"path": "test.txt"}, "Create test.txt")
        resp = self.client.get("/api/approvals")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        ids = [a["id"] for a in data["approvals"]]
        self.assertIn(appr_id, ids)

        # Action: approve
        action_resp = self.client.post(
            f"/api/approvals/{appr_id}/action", json={"action": "approve"}
        )
        self.assertEqual(action_resp.status_code, 200)
        self.assertEqual(action_resp.get_json()["status"], "updated")


if __name__ == "__main__":
    unittest.main()
