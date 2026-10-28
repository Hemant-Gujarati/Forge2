"""Tests for Phase 2, 3, 4, and 5: SQLite, approvals, Android API, and Telegram bot."""

import tempfile
import shutil
from pathlib import Path
import unittest

from forge.db import (
    init_db, create_task, update_task_status, get_task, list_tasks,
    create_approval, get_approval, list_pending_approvals, update_approval_status,
    create_pairing_token, verify_pairing_token
)
from forge.approvals import ApprovalManager, is_destructive_action, format_action_summary
from forge.server.api import create_app
from forge.server.tasks import TaskQueue
from forge.server.whatsapp import split_telegram_message


class TestDatabaseAndApprovals(unittest.TestCase):
    """Test SQLite persistence and safety approval logic."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_forge.db"
        init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_task_crud(self):
        tid = create_task(prompt="Refactor login", provider="ollama", model="llama3.2", db_path=self.db_path)
        t = get_task(tid, db_path=self.db_path)
        self.assertIsNotNone(t)
        self.assertEqual(t["status"], "pending")
        self.assertEqual(t["prompt"], "Refactor login")

        update_task_status(tid, "done", result="Refactored cleanly", db_path=self.db_path)
        t2 = get_task(tid, db_path=self.db_path)
        self.assertEqual(t2["status"], "done")
        self.assertEqual(t2["result"], "Refactored cleanly")
        self.assertIsNotNone(t2["completed_at"])

        all_tasks = list_tasks(db_path=self.db_path)
        self.assertEqual(len(all_tasks), 1)

    def test_approval_workflow(self):
        aid = create_approval(
            action_type="write_file",
            action_summary="Write dangerous file",
            action_payload={"path": "evil.sh", "content": "rm -rf /"},
            task_id="t123",
            db_path=self.db_path,
        )
        appr = get_approval(aid, db_path=self.db_path)
        self.assertIsNotNone(appr)
        self.assertEqual(appr["status"], "pending")
        self.assertEqual(appr["action_payload"]["path"], "evil.sh")

        pending = list_pending_approvals(db_path=self.db_path)
        self.assertEqual(len(pending), 1)

        # Approve
        res = update_approval_status(aid, "approved", db_path=self.db_path)
        self.assertTrue(res)

        appr_after = get_approval(aid, db_path=self.db_path)
        self.assertEqual(appr_after["status"], "approved")
        self.assertEqual(len(list_pending_approvals(db_path=self.db_path)), 0)

    def test_safe_vs_destructive_actions(self):
        self.assertTrue(is_destructive_action("write_file"))
        self.assertTrue(is_destructive_action("edit_file"))
        self.assertTrue(is_destructive_action("delete_file"))
        self.assertTrue(is_destructive_action("run_command"))
        self.assertTrue(is_destructive_action("git_commit"))

        self.assertFalse(is_destructive_action("read_file"))
        self.assertFalse(is_destructive_action("list_directory"))
        self.assertFalse(is_destructive_action("find_files"))
        self.assertFalse(is_destructive_action("search_text"))
        self.assertFalse(is_destructive_action("git_status"))

    def test_pairing_tokens(self):
        token = create_pairing_token(client_name="Test Phone", db_path=self.db_path)
        self.assertTrue(verify_pairing_token(token, db_path=self.db_path))
        self.assertFalse(verify_pairing_token("fake_token", db_path=self.db_path))


class TestAndroidRestApi(unittest.TestCase):
    """Test all Android REST API endpoints (Phase 5)."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_api.db"
        init_db(self.db_path)

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "online")
        self.assertIn("default_provider", data)

    def test_pair_endpoint(self):
        resp = self.client.post("/v1/pair", json={"client_name": "Pixel 9 Pro"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "paired")
        self.assertTrue(data["token"].startswith("frg_"))

        token = data["token"]

        # Call authenticated tasks endpoint with this token
        auth_headers = {"Authorization": f"Bearer {token}"}
        tasks_resp = self.client.get("/v1/tasks", headers=auth_headers)
        self.assertEqual(tasks_resp.status_code, 200)
        self.assertIn("tasks", tasks_resp.get_json())

    def test_unauthenticated_request_rejected(self):
        resp = self.client.get("/v1/tasks")
        self.assertEqual(resp.status_code, 401)


class TestTelegramMessageSplitting(unittest.TestCase):
    """Test Telegram message length safeguards (Phase 4)."""

    def test_split_long_message(self):
        long_text = "A" * 9000
        chunks = split_telegram_message(long_text, max_length=4000)
        self.assertTrue(len(chunks) >= 3)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4000)


if __name__ == "__main__":
    unittest.main()
