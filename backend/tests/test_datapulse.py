import io
import json
import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Test databases and JWT keys never reuse local application credentials.
TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="datapulse-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(TEST_DIRECTORY.name) / "tests.db")
os.environ["SECRET_KEY"] = "datapulse-test-only-key-with-at-least-32-characters"
os.environ["SMTP_ENABLED"] = "false"
os.environ["DEMO_MODE"] = "false"

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import delete, func, inspect, select

from database import Base, engine
from database.db import SessionLocal
from main import app
from core.senha_hash import criar_hash_senha
from models import (
    AnalyticsResult, AuditLog, BackgroundTask, DataRecord, Dataset, EmailDelivery, KPI,
    Favorite, IngestionJob, Notification, Report, Schedule, User,
)
from routes.api import login_attempts
from services.ingestion import ImportProblem, PublicHTTPSConnection, parse_file
from services.operations import dispatch_schedules, process_task, process_email, recover_interrupted, heartbeat, worker_ready
from models.entities import utcnow

PREFIX = "/api/v1"
for name in ("datapulse", "httpx", "alembic"):
    logging.getLogger(name).setLevel(logging.ERROR)


class DataPulseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.migration_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        command.upgrade(cls.migration_config, "head")

    @classmethod
    def tearDownClass(cls):
        engine.dispose()
        TEST_DIRECTORY.cleanup()

    def setUp(self):
        with SessionLocal() as db:
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(delete(table))
            db.commit()
        login_attempts.clear()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        response = self.client.post(PREFIX + "/auth/register", json={
            "name": "Test Admin", "username": "admin", "email": "admin@example.test",
            "password": "Test-only-password-123",
        })
        self.assertEqual(response.status_code, 201, response.text)
        self.admin = response.json()["data"]
        self.client.headers["Authorization"] = "Bearer " + self.admin["access_token"]

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    def post(self, path, body, status=201):
        response = self.client.post(PREFIX + path, json=body)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()["data"]

    def dataset(self, columns=None):
        return self.post("/datasets", {"name": "Test dataset", "columns": columns or []})

    def upload(self, dataset_id, rows, status=201, filename="data.json"):
        content = json.dumps(rows).encode() if not isinstance(rows, bytes) else rows
        response = self.client.post(PREFIX + "/ingestion/import", data={"dataset_id": dataset_id},
                                    files={"file": (filename, content, "application/octet-stream")})
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def seed_sales(self):
        dataset = self.dataset([
            {"name": "amount", "kind": "number", "required": True},
            {"name": "date", "kind": "date", "required": True},
            {"name": "category", "kind": "string"},
        ])
        self.upload(dataset["id"], [
            {"amount": 10, "date": "2026-01-01", "category": " A "},
            {"amount": 20, "date": "2026-01-02", "category": "A"},
            {"amount": 60, "date": "2026-02-01", "category": "B"},
        ])
        return dataset["id"]

    def test_notification_history_read_state_is_personal_and_persistent(self):
        dataset_id = self.seed_sales()
        kpi = self.post("/kpis", {"name": "Limit KPI", "query": {"dataset_id": dataset_id, "aggregation": "sum", "field": "amount"}})
        member = self.post("/users", {
            "name": "Viewer", "username": "reader", "email": "reader@example.test",
            "password": "Test-only-password-123",
        })
        self.post("/alerts", {"name": "Limit", "kpi_id": kpi["id"], "operator": "gt", "threshold": 50})
        events = self.client.get(PREFIX + "/notifications").json()
        self.assertEqual(events["meta"]["unread"], 2)  # import and alert
        alert = events["data"][0]
        self.assertEqual(alert["kind"], "alert")
        self.assertEqual(self.client.patch(PREFIX + f"/notifications/{alert['id']}/read").status_code, 200)
        self.assertEqual(self.client.get(PREFIX + "/notifications").json()["meta"]["unread"], 1)
        token = self.post("/auth/login", {
            "username": member["username"], "password": "Test-only-password-123",
        }, 200)["access_token"]
        headers = {"Authorization": "Bearer " + token}
        self.assertEqual(self.client.get(PREFIX + "/notifications", headers=headers).json()["meta"]["unread"], 1)
        self.assertEqual(self.client.patch(PREFIX + f"/notifications/{alert['id']}/read", headers=headers).status_code, 404)
        self.post("/notifications/read-all", {}, 200)
        self.assertEqual(self.client.get(PREFIX + "/notifications").json()["meta"]["unread"], 0)
        self.assertEqual(self.client.get(PREFIX + "/notifications", headers=headers).json()["meta"]["unread"], 1)
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(Notification).where(Notification.id == alert["id"])).read_at is not None, True)

    def test_alert_events_only_on_transitions(self):
        dataset_id = self.seed_sales()
        kpi = self.post("/kpis", {"name": "Revenue", "query": {"dataset_id": dataset_id, "aggregation": "sum", "field": "amount"}})
        alert = self.post("/alerts", {"name": "Limit", "kpi_id": kpi["id"], "operator": "gt", "threshold": 50})
        self.upload(dataset_id, [{"amount": 5, "date": "2026-03-01", "category": "C"}])
        events = self.client.get(PREFIX + "/notifications").json()["data"]
        self.assertEqual(len([event for event in events if event["kind"] == "alert"]), 1)
        self.client.patch(PREFIX + f"/alerts/{alert['id']}", json={
            "name": "Limit", "kpi_id": kpi["id"], "operator": "gt", "threshold": 50, "enabled": False,
        })
        events = self.client.get(PREFIX + "/notifications").json()["data"]
        self.assertEqual(len([event for event in events if event["kind"] == "alert"]), 2)

    def test_favorites_round_trip_filters_and_ownership(self):
        dataset_id = self.seed_sales()
        query = {"dataset_id": dataset_id, "aggregation": "sum", "field": "amount",
                 "filters": [{"field": "category", "operator": "eq", "value": "A"}]}
        favorite = self.post("/favorites", {"name": "Saved filter", "query": query})
        self.assertEqual(self.client.get(PREFIX + "/favorites").json()["data"][0]["query"]["filters"], query["filters"])
        self.assertEqual(self.client.post(PREFIX + "/favorites", json={"name": "Saved filter", "query": query}).status_code, 409)
        self.post("/users", {
            "name": "Reader", "username": "reader", "email": "reader@example.test",
            "password": "Test-only-password-123",
        })
        token = self.post("/auth/login", {
            "username": "reader", "password": "Test-only-password-123",
        }, 200)["access_token"]
        headers = {"Authorization": "Bearer " + token}
        self.assertEqual(self.client.get(PREFIX + "/favorites", headers=headers).json()["data"], [])
        self.assertEqual(self.client.delete(PREFIX + f"/favorites/{favorite['id']}", headers=headers).status_code, 404)
        self.assertEqual(self.client.delete(PREFIX + f"/favorites/{favorite['id']}").status_code, 200)
        self.assertEqual(self.client.get(PREFIX + "/favorites").json()["data"], [])

    def test_background_import_durable_job_and_payload_cleanup(self):
        dataset = self.dataset()
        response = self.client.post(PREFIX + "/ingestion/import",
            data={"dataset_id": dataset["id"], "background": "true"},
            files={"file": ("async.json", b'[{"amount": 12}]', "application/json")})
        self.assertEqual(response.status_code, 202, response.text)
        job = response.json()["data"]
        self.assertEqual(job["status"], "queued")
        with SessionLocal() as db:
            task = db.scalar(select(BackgroundTask))
            self.assertIsNotNone(task.file_content)
            self.assertFalse(worker_ready(db))
            heartbeat(db)
            self.assertTrue(worker_ready(db))
            self.assertTrue(process_task(db))
            self.assertFalse(process_task(db))
            db.expire_all()
            self.assertIsNone(db.get(BackgroundTask, task.id).file_content)
        detail = self.client.get(PREFIX + f"/ingestion/jobs/{job['id']}").json()["data"]
        self.assertEqual((detail["status"], detail["imported_rows"]), ("completed", 1))
        tasks = self.client.get(PREFIX + "/operations/tasks").json()["data"]
        self.assertNotIn("file_content", tasks[0])

    def test_background_permission_revocation_and_crash_recovery(self):
        dataset = self.dataset()
        response = self.client.post(PREFIX + "/ingestion/import", data={"dataset_id": dataset["id"], "background": True},
            files={"file": ("data.json", b'[{"amount": 1}]')})
        job_id = response.json()["data"]["id"]
        with SessionLocal() as db:
            db.get(User, self.admin["user"]["id"]).active = False
            db.commit()
            self.assertTrue(process_task(db))
            self.assertEqual(db.get(IngestionJob, job_id).status, "failed")
            task = db.scalar(select(BackgroundTask))
            task.status = "running"
            db.commit()
            recover_interrupted(db)
            self.assertEqual(db.get(BackgroundTask, task.id).status, "failed")
            self.assertIsNone(db.get(BackgroundTask, task.id).file_content)
            self.assertEqual(db.scalar(select(func.count()).select_from(DataRecord)), 0)

    def test_background_task_failure_gives_safe_actionable_diagnostic(self):
        dataset = self.dataset()
        with SessionLocal() as db:
            task = BackgroundTask(
               kind="report",
               dataset_id=dataset["id"],
               payload={"name": "Broken report", "query": {"dataset_id": dataset["id"]}},
               created_by=self.admin["user"]["id"],
            )
            db.add(task)
            db.commit()
            task_id = task.id
            with patch("services.operations.execute_query", side_effect=RuntimeError("private detail")):
               self.assertTrue(process_task(db))
            db.expire_all()
            failed_task = db.get(BackgroundTask, task_id)
            self.assertEqual(failed_task.status, "failed")
            self.assertEqual(
               failed_task.error,
               "Falha interna (RuntimeError). Consulte os logs do worker.",
            )
            self.assertNotIn("private detail", failed_task.error)

    def test_schedules_generate_real_snapshots_without_duplicate_dispatch(self):
        dataset_id = self.seed_sales()
        schedule = self.post("/schedules", {"name": "Weekly report", "kind": "report", "dataset_id": dataset_id,
            "interval_minutes": 10080, "query": {"dataset_id": dataset_id, "aggregation": "sum", "field": "amount"}})
        with SessionLocal() as db:
            db.get(Schedule, schedule["id"]).next_run_at = utcnow()
            db.commit()
            dispatch_schedules(db)
            dispatch_schedules(db)
            self.assertEqual(db.scalar(select(func.count()).select_from(BackgroundTask)), 1)
            process_task(db)
            self.assertEqual(db.scalar(select(Report)).result["value"], 90)
            self.assertEqual(db.get(Schedule, schedule["id"]).last_status, "completed")
        self.assertEqual(self.client.patch(PREFIX + f"/schedules/{schedule['id']}", json={"enabled": False}).status_code, 200)
        self.assertFalse(self.client.get(PREFIX + "/schedules").json()["data"][0]["enabled"])

    def test_schedule_validation_and_role_guards(self):
        dataset_id = self.seed_sales()
        common = {"name": "Invalid", "kind": "import", "dataset_id": dataset_id, "interval_minutes": 15}
        self.assertEqual(self.client.post(PREFIX + "/schedules", json=common).status_code, 422)
        self.assertEqual(self.client.post(PREFIX + "/schedules", json={**common, "interval_minutes": 1}).status_code, 422)
        self.assertEqual(self.client.post(PREFIX + "/schedules", json={**common, "kind": "report"}).status_code, 422)
        self.post("/users", {
            "name": "Reader", "username": "reader", "email": "reader@example.test",
            "password": "Test-only-password-123",
        })
        token = self.post("/auth/login", {
            "username": "reader", "password": "Test-only-password-123",
        }, 200)["access_token"]
        headers = {"Authorization": "Bearer " + token}
        for path in ("/schedules", "/operations/tasks", "/operations/emails"):
            self.assertEqual(self.client.get(PREFIX + path, headers=headers).status_code, 403)

    def test_scheduled_api_import_uses_existing_allowlist_validation(self):
        from models import DataSource
        dataset = self.dataset()
        with SessionLocal() as db:
            source = DataSource(name="API", kind="api", url="https://public.example.test/data", created_by=self.admin["user"]["id"])
            db.add(source)
            db.flush()
            db.get(Dataset, dataset["id"]).source_id = source.id
            db.commit()
        with patch("services.operations.check_api_url", return_value="public.example.test"):
            schedule = self.post("/schedules", {"name": "API import", "kind": "import", "dataset_id": dataset["id"], "interval_minutes": 15})
            with SessionLocal() as db:
                db.get(Schedule, schedule["id"]).next_run_at = utcnow()
                db.commit()
                dispatch_schedules(db)
                with patch("services.ingestion.fetch_api", return_value=b'[{"amount":42}]'):
                    process_task(db)
                self.assertEqual(db.scalar(select(IngestionJob)).imported_rows, 1)

    def test_smtp_queue_retries_and_csv_attachment(self):
        from services.events import notify
        from services.operations import send_email
        dataset_id = self.seed_sales()
        report = self.post("/reports", {"name": "Report", "query": {"dataset_id": dataset_id}})
        with patch("services.events.SMTP_ENABLED", True):
            with SessionLocal() as db:
                notify(db, "report", "Report ready", "Actual snapshot", "/reports", user_id=self.admin["user"]["id"], email=True, report_id=report["id"])
                db.commit()
        with patch("services.operations.config.SMTP_ENABLED", True):
            with SessionLocal() as db:
                with patch("services.operations.send_email", side_effect=OSError("test failure")):
                    self.assertTrue(process_email(db))
                delivery = db.scalar(select(EmailDelivery))
                self.assertEqual((delivery.status, delivery.attempts), ("queued", 1))
                self.assertIn("Falha SMTP", delivery.error)
                delivery.next_attempt_at = utcnow()
                db.commit()
                with patch("services.operations.send_email") as send:
                    self.assertTrue(process_email(db))
                    send.assert_called_once()
                self.assertEqual(delivery.status, "sent")
                with patch("services.operations.config.SMTP_FROM", "test@example.test"), patch("services.operations.smtplib.SMTP") as smtp:
                    send_email(delivery, db.get(User, delivery.user_id), db.get(Report, report["id"]))
                    smtp.return_value.__enter__.return_value.starttls.assert_called_once()
                    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
                    self.assertEqual(next(message.iter_attachments()).get_content_type(), "text/csv")

    def test_worker_singleton_lock_and_backup_restore(self):
        from backup import copy_database, retain_backups, verify
        from worker import worker_lock
        directory = Path(TEST_DIRECTORY.name)
        with worker_lock(directory / "test.lock"):
            with self.assertRaises(RuntimeError):
                with worker_lock(directory / "test.lock"):
                    pass
        backup = directory / "restore-test.backup"
        restored = directory / "restored.db"
        dated_backups = [directory / f"datapulse-test-{index}.backup" for index in range(3)]
        try:
            copy_database(Path(TEST_DIRECTORY.name) / "tests.db", backup)
            self.assertEqual(verify(backup), "0004")
            copy_database(backup, restored)
            self.assertEqual(verify(restored), "0004")
            for index, path in enumerate(dated_backups):
                copy_database(backup, path)
                os.utime(path, (index, index))
            self.assertEqual(retain_backups(directory, 2), [dated_backups[0]])
            self.assertTrue(dated_backups[0].exists())
            self.assertEqual(retain_backups(directory, 2, apply=True), [dated_backups[0]])
            self.assertFalse(dated_backups[0].exists())
            self.assertTrue(all(path.exists() for path in dated_backups[1:]))
            with self.assertRaises(FileExistsError):
                copy_database(backup, restored)
            with self.assertRaises(ValueError):
                copy_database(backup, backup)
        finally:
            for path in (backup, restored, *dated_backups):
                path.unlink(missing_ok=True)

    def test_smtp_failure_is_bounded_and_interrupted_delivery_is_not_resent(self):
        from services.events import notify
        with patch("services.events.SMTP_ENABLED", True):
            with SessionLocal() as db:
                notify(db, "alert", "Test alert", "Real test rule", "/alerts", email=True)
                db.commit()
        with patch("services.operations.config.SMTP_ENABLED", True), patch("services.operations.send_email", side_effect=OSError("test")):
            with SessionLocal() as db:
                delivery = db.scalar(select(EmailDelivery))
                for _ in range(3):
                    delivery.next_attempt_at = utcnow()
                    db.commit()
                    process_email(db)
                self.assertEqual((delivery.status, delivery.attempts), ("failed", 3))
                delivery.status = "sending"
                db.commit()
                recover_interrupted(db)
                self.assertEqual(delivery.status, "failed")
                self.assertIn("incerta", delivery.error)
                self.assertFalse(process_email(db))

    def test_report_schedule_warns_when_smtp_disabled_after_creation(self):
        dataset_id = self.seed_sales()
        with patch("routes.operations.SMTP_ENABLED", True):
            schedule = self.post("/schedules", {"name": "Email report", "kind": "report", "dataset_id": dataset_id,
                "query": {"dataset_id": dataset_id}, "interval_minutes": 15, "email_report": True})
        with SessionLocal() as db:
            db.get(Schedule, schedule["id"]).next_run_at = utcnow()
            db.commit()
            dispatch_schedules(db)
            with patch("services.operations.config.SMTP_ENABLED", False):
                process_task(db)
            task = db.scalar(select(BackgroundTask))
            self.assertEqual(task.status, "completed_with_errors")
            self.assertIn("SMTP", task.error)
            self.assertIsNotNone(db.get(Report, task.report_id))

    def test_queue_capacity_and_admin_failure_metrics(self):
        dataset = self.dataset()
        with SessionLocal() as db:
            owner = db.scalar(select(User))
            db.add_all([BackgroundTask(kind="import", dataset_id=dataset["id"], created_by=owner.id)
                        for _ in range(100)])
            db.commit()
        response = self.client.post(PREFIX + "/ingestion/import",
            data={"dataset_id": dataset["id"], "background": "true"},
            files={"file": ("sample.json", b'[{"x":1}]', "application/json")})
        self.assertEqual(response.status_code, 429)
        metrics = self.client.get(PREFIX + "/operations/metrics").json()["data"]
        self.assertEqual(metrics["tasks"]["queued"], 100)
        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(IngestionJob)), 0)
        self.post("/users", {
            "name": "Viewer", "username": "viewer", "email": "viewer@example.test",
            "password": "Test-only-password-123",
        })
        token = self.post("/auth/login", {
            "username": "viewer", "password": "Test-only-password-123",
        }, 200)["access_token"]
        self.assertEqual(self.client.get(PREFIX + "/operations/metrics",
            headers={"Authorization": "Bearer " + token}).status_code, 403)

    def test_standalone_worker_cli_becomes_ready(self):
        environment = {**os.environ, "WORKER_LOCK_PATH": str(Path(TEST_DIRECTORY.name) / "worker-smoke.lock")}
        process = subprocess.Popen([sys.executable, "-m", "worker"], cwd=Path(__file__).resolve().parents[1],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        online = False
        try:
            deadline = time.monotonic() + 15
            while process.poll() is None and time.monotonic() < deadline:
                with SessionLocal() as db:
                    online = worker_ready(db)
                if online:
                    break
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                output, _ = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                output, _ = process.communicate(timeout=10)
        self.assertTrue(online, output)

    def test_health_readiness_and_cors_delete(self):
        self.assertEqual(self.client.get("/ready").status_code, 200)
        response = self.client.options(PREFIX + "/favorites/1", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE",
        })
        self.assertEqual(response.status_code, 200)

    def test_migrations_match_models_and_preserve_unrelated_tables(self):
        self.assertFalse(command.check(self.migration_config))
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE unrelated_fixture (id INTEGER PRIMARY KEY)")
        try:
            command.downgrade(self.migration_config, "0003")
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "INSERT INTO users "
                    "(id, created_at, name, email, password_hash, role, active, token_version, bootstrap_key) "
                    "VALUES (100, CURRENT_TIMESTAMP, 'Migrated member', 'admin@other.example', "
                    "'hash', 'viewer', 1, 0, NULL)"
                )
            command.upgrade(self.migration_config, "head")
            with SessionLocal() as db:
                migrated = db.get(User, 100)
                self.assertEqual(migrated.username, "admin-2")

            command.downgrade(self.migration_config, "base")
            self.assertIn("unrelated_fixture", inspect(engine).get_table_names())
            command.upgrade(self.migration_config, "head")
            self.assertIn("data_records", inspect(engine).get_table_names())
        finally:
            with engine.begin() as connection:
                connection.exec_driver_sql("DROP TABLE unrelated_fixture")

    def test_authentication_roles_and_revocation(self):
        member = self.post("/users", {
            "name": "Viewer", "username": "viewer", "email": "viewer@example.test",
            "password": "Test-only-password-123",
        })
        viewer = self.post("/auth/login", {
            "username": "viewer", "password": "Test-only-password-123",
        }, 200)
        self.assertEqual(member["role"], "viewer")
        self.assertEqual(viewer["user"]["role"], "viewer")
        headers = {"Authorization": "Bearer " + viewer["access_token"]}
        response = self.client.post(PREFIX + "/sources", json={"name": "Denied", "kind": "csv"}, headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get(PREFIX + "/users", headers=headers).status_code, 403)
        response = self.client.patch(PREFIX + f"/users/{viewer['user']['id']}",
                                     json={"role": "editor", "active": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(PREFIX + "/sources", headers=headers).status_code, 401)
        viewer = self.post("/auth/login", {
            "username": "viewer", "password": "Test-only-password-123",
        }, 200)
        headers = {"Authorization": "Bearer " + viewer["access_token"]}
        response = self.client.post(PREFIX + "/sources", json={"name": "Allowed", "kind": "csv"}, headers=headers)
        self.assertEqual(response.status_code, 201)
        self.client.patch(PREFIX + f"/users/{viewer['user']['id']}", json={"role": "editor", "active": False})
        self.assertEqual(self.client.get(PREFIX + "/sources", headers=headers).status_code, 401)
        self.assertEqual(self.client.get(PREFIX + "/sources", headers={"Authorization": "Bearer broken"}).status_code, 401)
        self.assertEqual(self.client.get(PREFIX + "/sources", headers={"Authorization": ""}).status_code, 401)
        self.assertNotIn("password_hash", self.admin["user"])
        self.assertEqual(self.client.patch(PREFIX + f"/users/{self.admin['user']['id']}",
                                          json={"role": "viewer"}).status_code, 422)
        self.assertFalse(self.client.get(PREFIX + "/auth/setup").json()["data"]["registration_open"])
        self.assertEqual(self.client.post(PREFIX + "/auth/register", json={
            "name": "Outsider", "username": "outsider", "email": "outsider@example.test",
            "password": "Test-only-password-123",
        }).status_code, 403)

    def test_only_admin_can_create_public_demo_account_and_guide_exposes_credentials(self):
        demo_email = "demo@example.test"
        demo_password = "Public-demo-password-123"
        with SessionLocal() as db:
            db.add(User(
                name="Legacy demo",
                username="demo",
                email=demo_email,
                password_hash=criar_hash_senha(demo_password),
                role="editor",
                active=True,
                bootstrap_key="demo",
            ))
            db.commit()

        with (
            patch("routes.api.DEMO_MODE", True),
            patch("routes.api.DEMO_USERNAME", "demo"),
            patch("routes.api.DEMO_EMAIL", demo_email),
            patch("routes.api.DEMO_PASSWORD", demo_password),
        ):
            self.assertEqual(self.client.get(PREFIX + "/auth/demo").json()["data"], {
                "available": False,
            })
            self.assertEqual(self.client.post(PREFIX + "/auth/login", json={
                "username": "demo",
                "password": demo_password,
            }).status_code, 401)
            status = self.client.get(PREFIX + "/users/demo")
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["data"], {
                "enabled": True,
                "created": False,
                "active": True,
                "available": False,
                "username": "demo",
                "email": demo_email,
            })
            created = self.client.post(PREFIX + "/users/demo", json={})
            self.assertEqual(created.status_code, 201, created.text)
            self.assertEqual(created.json()["data"]["user"]["role"], "editor")
            self.assertTrue(created.json()["data"]["sample_data_created"])
            self.assertNotIn("password_hash", created.json()["data"]["user"])
            self.assertTrue(created.json()["data"]["user"]["is_public_demo"])

            guide = self.client.get(PREFIX + "/auth/demo")
            self.assertEqual(guide.status_code, 200)
            self.assertEqual(guide.json()["data"], {
                "available": True,
                "username": "demo",
                "password": demo_password,
                "role": "editor",
            })
            demo = self.post("/auth/login", {"username": "demo", "password": demo_password}, 200)
            duplicate = self.client.post(PREFIX + "/users/demo", json={})
            self.assertEqual(duplicate.status_code, 409)

        self.assertEqual(demo["user"]["role"], "editor")
        demo_headers = {"Authorization": "Bearer " + demo["access_token"]}
        datasets = self.client.get(PREFIX + "/datasets", headers=demo_headers).json()["data"]
        self.assertEqual(len(datasets), 1)
        with SessionLocal() as db:
            dataset = db.scalar(select(Dataset))
            records = db.scalar(select(func.count(DataRecord.id)))
            kpi = db.scalar(select(KPI))
            self.assertEqual(records, 36)
            self.assertEqual(kpi.name, "Receita total")
            self.assertEqual(kpi.dataset_id, dataset.id)

        self.assertEqual(self.client.post(
            PREFIX + "/sources",
            json={"name": "Minha fonte", "kind": "csv"},
            headers=demo_headers,
        ).status_code, 201)
        self.assertEqual(self.client.get(PREFIX + "/users", headers=demo_headers).status_code, 403)
        self.assertEqual(self.client.post(PREFIX + "/auth/password", json={
            "current_password": demo_password,
            "new_password": "Different-public-password-123",
        }, headers=demo_headers).status_code, 403)
        self.assertEqual(self.client.patch(
            PREFIX + f"/users/{demo['user']['id']}",
            json={"role": "admin", "active": True},
        ).status_code, 422)

        viewer = self.post("/users", {
            "name": "Viewer",
            "username": "viewer",
            "email": "viewer@example.test",
            "password": "Viewer-password-123",
        })
        viewer_login = self.post("/auth/login", {
            "username": viewer["username"],
            "password": "Viewer-password-123",
        }, 200)
        viewer_headers = {"Authorization": "Bearer " + viewer_login["access_token"]}
        self.assertEqual(self.client.post(
            PREFIX + "/users/demo", json={}, headers=viewer_headers,
        ).status_code, 403)

    def test_public_demo_account_creation_requires_demo_mode(self):
        with patch("routes.api.DEMO_MODE", False):
            response = self.client.post(PREFIX + "/users/demo", json={})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(self.client.get(PREFIX + "/auth/demo").json()["data"], {
                "available": False,
            })

    def test_password_change_rotates_tokens_and_rejects_bad_current_password(self):
        token = self.admin["access_token"]
        response = self.client.post(PREFIX + "/auth/password", json={
            "current_password": "not-the-current-password",
            "new_password": "Another-test-password-456",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(PREFIX + "/auth/me", headers={
            "Authorization": "Bearer " + token,
        }).status_code, 200)

        response = self.client.post(PREFIX + "/auth/password", json={
            "current_password": "Test-only-password-123",
            "new_password": "Another-test-password-456",
        })
        self.assertEqual(response.status_code, 200, response.text)
        new_token = response.json()["data"]["access_token"]
        self.assertEqual(self.client.get(PREFIX + "/auth/me", headers={
            "Authorization": "Bearer " + token,
        }).status_code, 401)
        self.assertEqual(self.client.get(PREFIX + "/auth/me", headers={
            "Authorization": "Bearer " + new_token,
        }).status_code, 200)
        self.assertEqual(self.client.post(PREFIX + "/auth/login", json={
            "username": "admin", "password": "Test-only-password-123",
        }).status_code, 401)
        self.assertEqual(self.client.post(PREFIX + "/auth/login", json={
            "username": "admin", "password": "Another-test-password-456",
        }).status_code, 200)
        new_login = self.client.post(PREFIX + "/auth/login", json={
            "username": "admin", "password": "Another-test-password-456",
        }).json()["data"]
        session_headers = {"Authorization": "Bearer " + new_login["access_token"]}
        self.assertEqual(self.client.post(PREFIX + "/auth/logout", headers=session_headers).status_code, 200)
        self.assertEqual(self.client.get(PREFIX + "/auth/me", headers=session_headers).status_code, 401)

    def test_profile_update_normalizes_username_and_keeps_contact_email_optional(self):
        response = self.client.patch(PREFIX + "/auth/profile", json={
            "username": "New.Admin", "email": None,
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["username"], "new.admin")
        self.assertIsNone(response.json()["data"]["email"])
        self.assertEqual(self.client.post(PREFIX + "/auth/login", json={
            "username": "new.admin", "password": "Test-only-password-123",
        }).status_code, 200)
        self.assertEqual(self.client.post(PREFIX + "/auth/login", json={
            "username": "admin", "password": "Test-only-password-123",
        }).status_code, 401)

        self.post("/users", {
            "name": "Member",
            "username": "member",
            "password": "Member-password-123",
        })
        duplicate = self.client.patch(PREFIX + "/auth/profile", json={
            "username": "MEMBER",
        })
        self.assertEqual(duplicate.status_code, 409)

    def test_admin_password_reset_returns_one_time_password_and_revokes_sessions(self):
        member = self.post("/users", {
            "name": "Member",
            "username": "member",
            "password": "Member-password-123",
        })
        login = self.post("/auth/login", {
            "username": "member",
            "password": "Member-password-123",
        }, 200)
        old_headers = {"Authorization": "Bearer " + login["access_token"]}
        reset = self.client.post(PREFIX + f"/users/{member['id']}/password-reset", json={})
        self.assertEqual(reset.status_code, 200, reset.text)
        temporary_password = reset.json()["data"]["temporary_password"]
        self.assertGreaterEqual(len(temporary_password), 10)
        self.assertEqual(self.client.get(PREFIX + "/auth/me", headers=old_headers).status_code, 401)
        self.assertEqual(self.client.post(PREFIX + "/auth/login", json={
            "username": "member", "password": temporary_password,
        }).status_code, 200)
        self.assertEqual(self.client.post(
            PREFIX + f"/users/{self.admin['user']['id']}/password-reset",
            json={},
        ).status_code, 422)

        viewer = self.post("/users", {
            "name": "Viewer",
            "username": "viewer",
            "password": "Viewer-password-123",
        })
        viewer_login = self.post("/auth/login", {
            "username": "viewer",
            "password": "Viewer-password-123",
        }, 200)
        viewer_headers = {"Authorization": "Bearer " + viewer_login["access_token"]}
        self.assertEqual(self.client.post(
            PREFIX + f"/users/{member['id']}/password-reset",
            json={},
            headers=viewer_headers,
        ).status_code, 403)

    def test_demo_data_restore_only_replaces_synthetic_dataset(self):
        unrelated_dataset_id = self.seed_sales()
        self.post("/reports", {
            "name": "Keep report",
            "query": {"dataset_id": unrelated_dataset_id, "aggregation": "sum", "field": "amount"},
        })
        with (
            patch("routes.api.DEMO_MODE", True),
            patch("routes.api.DEMO_USERNAME", "portfolio-demo"),
            patch("routes.api.DEMO_EMAIL", None),
            patch("routes.api.DEMO_PASSWORD", "Public-demo-password-123"),
        ):
            created = self.client.post(PREFIX + "/users/demo", json={})
            self.assertEqual(created.status_code, 201, created.text)
            demo_user_id = created.json()["data"]["user"]["id"]
            restored = self.client.post(PREFIX + "/users/demo/restore-data", json={})
            self.assertEqual(restored.status_code, 200, restored.text)
            self.assertTrue(restored.json()["data"]["created"])
            self.assertEqual(restored.json()["data"]["records"], 36)

            with SessionLocal() as db:
                from services.demo import DEMO_DATASET_DESCRIPTION
                demo_dataset = db.scalar(select(Dataset).where(
                    Dataset.created_by == demo_user_id,
                    Dataset.description == DEMO_DATASET_DESCRIPTION,
                ))
                sample_job = db.scalar(select(IngestionJob).where(
                    IngestionJob.dataset_id == demo_dataset.id,
                ))
                db.add(DataRecord(
                    dataset_id=demo_dataset.id,
                    job_id=sample_job.id,
                    fingerprint="d" * 64,
                    data={"data": "extra"},
                ))
                db.add(BackgroundTask(
                    kind="import",
                    status="queued",
                    dataset_id=demo_dataset.id,
                    created_by=demo_user_id,
                ))
                db.commit()
                demo_dataset_id = demo_dataset.id

            blocked = self.client.post(PREFIX + "/users/demo/restore-data", json={})
            self.assertEqual(blocked.status_code, 409)
            with SessionLocal() as db:
                task = db.scalar(select(BackgroundTask).where(
                    BackgroundTask.dataset_id == demo_dataset_id,
                ))
                db.delete(task)
                db.commit()

            restored = self.client.post(PREFIX + "/users/demo/restore-data", json={})
            self.assertEqual(restored.status_code, 200, restored.text)
            self.assertFalse(restored.json()["data"]["created"])
            self.assertEqual(restored.json()["data"]["records"], 36)

        with SessionLocal() as db:
            self.assertEqual(db.scalar(select(func.count(DataRecord.id)).where(
                DataRecord.dataset_id == demo_dataset_id,
            )), 36)
            self.assertEqual(db.scalar(select(func.count(DataRecord.id)).where(
                DataRecord.dataset_id == unrelated_dataset_id,
            )), 3)
            self.assertEqual(db.scalar(select(func.count(Report.id))), 1)

    def test_login_and_input_validation(self):
        self.post("/auth/login", {"username": "ADMIN", "password": "Test-only-password-123"}, 200)
        self.assertEqual(self.client.post(PREFIX + "/auth/login", json={
            "username": "admin", "password": "wrong",
        }).status_code, 401)
        self.assertEqual(self.client.post(PREFIX + "/auth/login", json={
            "email": "admin@example.test", "password": "Test-only-password-123",
        }).status_code, 422)
        response = self.client.post(PREFIX + "/auth/register", json={
            "name": "Invalid", "username": "invalid username", "password": "x",
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn("error", response.json())
        self.assertNotIn('"input"', response.text)
        for _ in range(16):
            response = self.client.post(PREFIX + "/auth/login", json={
                "username": "nonexistent", "password": "x",
            })
        self.assertEqual(response.status_code, 429)

    def test_username_login_does_not_require_contact_email(self):
        created = self.post("/users", {
            "name": "No Email", "username": "no-email", "password": "No-email-password-123",
        })
        self.assertIsNone(created["email"])
        login = self.post("/auth/login", {
            "username": "NO-EMAIL", "password": "No-email-password-123",
        }, 200)
        self.assertEqual(login["user"]["username"], "no-email")

    def test_password_whitespace_is_preserved(self):
        self.post("/users", {
            "name": "Member", "username": "member", "password": "  Test-only-password-123  ",
        })
        self.assertEqual(self.client.post(PREFIX + "/auth/login", json={
            "username": "member", "password": "Test-only-password-123",
        }).status_code, 401)
        self.post("/auth/login", {
            "username": "member", "password": "  Test-only-password-123  ",
        }, 200)

    def test_ingestion_normalization_dedup_validation_and_persistence(self):
        dataset = self.dataset([
            {"name": "amount", "kind": "number", "required": True},
            {"name": "name", "kind": "string"},
        ])
        job = self.upload(dataset["id"], [
            {"amount": " 10 ", "name": " Alice "}, {"amount": 10, "name": "Alice"},
            {"amount": "invalid", "name": "Bob"}, {"amount": 20, "extra": "unknown"},
            {"amount": None, "name": "Null"},
        ])["data"]
        self.assertEqual((job["total_rows"], job["imported_rows"], job["duplicate_rows"], job["rejected_rows"]),
                         (5, 1, 1, 3))
        self.assertEqual(job["status"], "completed_with_errors")
        self.assertEqual(len(job["errors"]), 3)
        self.assertNotIn("'invalid'", json.dumps(job["errors"]))
        self.assertTrue(job["created_at"].endswith("+00:00"))
        duplicate = self.upload(dataset["id"], [{"amount": 10, "name": "Alice"}])["data"]
        self.assertEqual(duplicate["duplicate_rows"], 1)
        records = self.client.get(PREFIX + f"/datasets/{dataset['id']}/records").json()["data"]
        self.assertEqual(records[0]["data"], {"amount": 10, "name": "Alice"})
        with SessionLocal() as db:
            self.assertEqual(len(list(db.scalars(select(DataRecord)))), 1)
            self.assertIsNotNone(db.scalar(select(AuditLog).where(AuditLog.action == "import")))
        job_response = self.client.get(PREFIX + f"/ingestion/jobs/{job['id']}")
        self.assertEqual(job_response.json()["data"]["status"], "completed_with_errors")

    def test_csv_excel_and_inferred_schema(self):
        dataset = self.dataset()
        job = self.upload(dataset["id"], b"date;amount;category\n2026-01-01;10;A\n2026-02-01;20;B\n", filename="data.csv")["data"]
        self.assertEqual(job["imported_rows"], 2)
        schema = self.client.get(PREFIX + f"/datasets/{dataset['id']}").json()["data"]["schema"]
        self.assertEqual([column["kind"] for column in schema], ["date", "number", "string"])
        workbook = Workbook()
        workbook.active.append(["date", "amount", "category"])
        workbook.active.append(["2026-03-01", 30, "C"])
        workbook.create_sheet("Not the first sheet").append(["unrelated"])
        workbook.active = 1
        content = io.BytesIO()
        workbook.save(content)
        job = self.upload(dataset["id"], content.getvalue(), filename="data.xlsx")["data"]
        self.assertEqual(job["imported_rows"], 1)

    def test_failed_import_is_tracked_and_atomic(self):
        dataset = self.dataset()
        response = self.upload(dataset["id"], b'{"bad":"not an array"}', status=422)
        job = response["error"]["details"]["job"]
        self.assertEqual(job["status"], "failed")
        self.assertEqual(self.client.get(PREFIX + "/ingestion/jobs").json()["meta"]["total"], 1)
        self.assertEqual(self.client.get(PREFIX + "/analytics/summary").json()["data"]["records"], 0)
        self.assertEqual(parse_file(b"a,b\n1,2\n", "a.csv"), [{"a": "1", "b": "2"}])
        for content, name in [(b"a,a\n1,2", "x.csv"), (b"a,b\n1", "x.csv"),
                              (b"[NaN]", "x.json"), (b"not-excel", "x.xlsx"),
                              (b"[" * 1100 + b"0" + b"]" * 1100, "nested.json"),
                              (b"[]", "x.json"), (b"x", "x.txt")]:
            with self.subTest(name=name, content=content):
                with self.assertRaises(ImportProblem):
                    parse_file(content, name)
        response = self.client.post(PREFIX + "/ingestion/import", data={"dataset_id": dataset["id"]},
                                    files={"file": ("large.csv", b"x" * (5 * 1024 * 1024 + 1))})
        self.assertEqual(response.status_code, 413)

    def test_analytics_aggregations_filters_and_grouping(self):
        dataset_id = self.seed_sales()
        for aggregation, expected in [("sum", 90), ("avg", 30), ("min", 10), ("max", 60), ("count", 3)]:
            with self.subTest(aggregation=aggregation):
                result = self.post("/analytics/query", {
                    "dataset_id": dataset_id, "aggregation": aggregation, "field": "amount",
                }, 200)
                self.assertEqual(result["value"], expected)
        result = self.post("/analytics/query", {
            "dataset_id": dataset_id, "aggregation": "sum", "field": "amount",
            "group_by": ["category"], "filters": [{"field": "amount", "operator": "gte", "value": 20}],
        }, 200)
        self.assertEqual(result["value"], 80)
        self.assertEqual([g["value"] for g in result["groups"]], [20, 60])
        result = self.post("/analytics/query", {
            "dataset_id": dataset_id, "filters": [{"field": "date", "operator": "eq", "value": "2026-01-01"}],
        }, 200)
        self.assertEqual(result["value"], 1)
        with SessionLocal() as db:
            self.assertIsNotNone(db.scalar(select(AnalyticsResult)))

    def test_unsafe_and_incompatible_queries_are_rejected(self):
        dataset_id = self.seed_sales()
        cases = [
            {"sql": "DROP TABLE users"}, {"field": "amount; DROP TABLE users"},
            {"aggregation": "sum", "field": "category"}, {"group_by": ["missing"]},
            {"date_field": "amount"}, {"aggregation": "median"},
            {"filters": [{"field": "amount", "operator": "gt", "value": "not a number"}]},
            {"filters": [{"field": "category", "operator": "contains", "value": None}]},
        ]
        for body in cases:
            with self.subTest(body=body):
                response = self.client.post(PREFIX + "/analytics/query", json={"dataset_id": dataset_id, **body})
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get(PREFIX + "/datasets").status_code, 200)

    def test_trends_comparison_and_insufficient_data(self):
        dataset_id = self.seed_sales()
        response = self.client.get(PREFIX + "/analytics/trends", params={
            "dataset_id": dataset_id, "date_field": "date", "field": "amount", "aggregation": "sum",
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["data"]
        self.assertEqual((result["previous"], result["current"], result["growth_percent"], result["direction"]),
                         (30, 60, 100, "up"))
        self.assertEqual(len(result["series"]), 2)
        self.assertEqual(self.client.get(PREFIX + "/analytics/trends", params={
            "dataset_id": dataset_id, "date_field": "date", "period": "invalid",
        }).status_code, 422)
        from services.analytics import compare_series
        self.assertIsNone(compare_series([{"value": 0}, {"value": 5}])["growth_percent"])
        self.assertEqual(compare_series([])["direction"], "insufficient_data")

    def test_kpis_alerts_reports_summary_and_export(self):
        dataset_id = self.seed_sales()
        query = {"dataset_id": dataset_id, "aggregation": "sum", "field": "amount"}
        kpi = self.post("/kpis", {"name": "Revenue", "query": query, "target": 200})
        alert = self.post("/alerts", {"name": "Revenue limit", "kpi_id": kpi["id"], "operator": "gt", "threshold": 100})
        self.assertFalse(alert["triggered"])
        self.upload(dataset_id, [{"amount": 50, "date": "2026-03-01", "category": "C"}])
        self.assertTrue(self.client.get(PREFIX + "/alerts").json()["data"][0]["triggered"])
        self.assertEqual(self.client.get(PREFIX + "/kpis").json()["data"][0]["value"], 140)
        report = self.post("/reports", {"name": "Revenue report", "query": query})
        self.assertEqual(report["result"]["value"], 140)
        exported = self.client.get(PREFIX + f"/reports/{report['id']}/export")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("140", exported.text)
        self.assertIn("text/csv", exported.headers["Content-Type"])
        summary = self.client.get(PREFIX + "/analytics/summary").json()["data"]
        self.assertEqual((summary["records"], summary["active_alerts"]), (4, 1))
        self.assertEqual(
            (summary["user_imports"], summary["analytics_queries"], summary["reports"]),
            (2, 0, 1),
        )
        self.assertEqual(summary["kpis"][0]["value"], 140)

    def test_statistical_anomalies_are_not_simulated_or_duplicated(self):
        dataset = self.dataset()
        rows = [{"index": n, "amount": 10 if n < 11 else 1000} for n in range(12)]
        self.upload(dataset["id"], rows)
        insights = self.client.get(PREFIX + "/insights").json()["data"]
        self.assertEqual(len(insights), 1)
        self.assertEqual(insights[0]["details"]["anomaly_count"], 1)
        self.assertEqual(insights[0]["details"]["sample_size"], 12)
        self.upload(dataset["id"], rows)
        self.assertEqual(len(self.client.get(PREFIX + "/insights").json()["data"]), 1)

    def test_api_host_allowlist_public_ip_and_real_job(self):
        self.assertEqual(self.client.post(PREFIX + "/sources", json={
            "name": "Unsafe", "kind": "api", "url": "https://127.0.0.1/data",
        }).status_code, 422)
        with patch("services.ingestion.API_ALLOWED_HOSTS", {"api.example.test"}):
            source = self.post("/sources", {
                "name": "API", "kind": "api", "url": "https://api.example.test/data",
            })
            dataset = self.post("/datasets", {"name": "API dataset", "source_id": source["id"]})
            # Only the transport is mocked; all parsing, validation and persistence are real.
            with patch("services.ingestion.PublicHTTPSConnection") as connection:
                response = connection.return_value.getresponse.return_value
                response.status = 200
                response.getheader.return_value = "identity"
                response.read.return_value = b'[{"amount":42}]'
                imported = self.client.post(PREFIX + "/ingestion/import", data={"dataset_id": dataset["id"]})
                self.assertEqual(imported.status_code, 201, imported.text)
                self.assertEqual(imported.json()["data"]["imported_rows"], 1)
            with patch("services.ingestion.socket.getaddrinfo", return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
            ]):
                with self.assertRaises(ImportProblem):
                    PublicHTTPSConnection("api.example.test").connect()

    def test_pagination_conflicts_foreign_keys_and_missing_resources(self):
        self.post("/sources", {"name": "Source A", "kind": "csv"})
        self.post("/sources", {"name": "Source B", "kind": "json"})
        response = self.client.get(PREFIX + "/sources?page=2&page_size=1").json()
        self.assertEqual((response["meta"]["total"], len(response["data"]), response["meta"]["page"]), (2, 1, 2))
        self.assertEqual(self.client.get(PREFIX + "/sources?page_size=101").status_code, 422)
        conflict = self.client.post(PREFIX + "/sources", json={"name": "Source A", "kind": "csv"})
        self.assertEqual(conflict.status_code, 409)
        self.assertNotIn("INSERT", conflict.text)
        self.assertEqual(self.client.post(PREFIX + "/datasets", json={"name": "Missing", "source_id": 999}).status_code, 404)
        for path in ["/datasets/999", "/ingestion/jobs/999", "/reports/999/export"]:
            self.assertEqual(self.client.get(PREFIX + path).status_code, 404)
        with SessionLocal() as db:
            self.assertEqual(len(list(db.scalars(select(User)))), 1)
            self.assertEqual(len(list(db.scalars(select(Dataset)))), 0)

    def test_management_updates_preserve_schema_and_reevaluate_alerts(self):
        source = self.post("/sources", {"name": "Source", "kind": "csv"})
        self.assertEqual(self.client.patch(PREFIX + f"/sources/{source['id']}", json={
            "name": "Renamed source", "kind": "json",
        }).status_code, 200)
        dataset_id = self.seed_sales()
        response = self.client.patch(PREFIX + f"/datasets/{dataset_id}", json={
            "name": "Renamed dataset", "description": "Updated", "source_id": source["id"],
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["data"]["schema"]), 3)
        self.assertEqual(self.client.patch(PREFIX + f"/datasets/{dataset_id}", json={
            "name": "No schema replacement", "columns": [],
        }).status_code, 422)
        kpi = self.post("/kpis", {"name": "Revenue", "query": {
            "dataset_id": dataset_id, "aggregation": "sum", "field": "amount",
        }})
        alert = self.post("/alerts", {"name": "Limit", "kpi_id": kpi["id"], "operator": "gt", "threshold": 50})
        self.assertTrue(alert["triggered"])
        response = self.client.patch(PREFIX + f"/kpis/{kpi['id']}", json={
            "name": "Average revenue", "query": {
                "dataset_id": dataset_id, "aggregation": "avg", "field": "amount",
            },
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(self.client.get(PREFIX + "/alerts").json()["data"][0]["triggered"])
        response = self.client.patch(PREFIX + f"/alerts/{alert['id']}", json={
            "name": "Updated limit", "kpi_id": kpi["id"], "operator": "gt", "threshold": 10, "enabled": False,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["triggered"])

    def test_import_row_byte_and_analytics_group_limits(self):
        dataset = self.dataset()
        records = [{"index": n} for n in range(10000)]
        job = self.upload(dataset["id"], records)["data"]
        self.assertEqual(job["imported_rows"], 10000)
        response = self.upload(dataset["id"], [{"index": 10000}], status=422)
        self.assertEqual(response["error"]["details"]["job"]["status"], "failed")
        self.assertEqual(self.client.get(PREFIX + "/analytics/summary").json()["data"]["records"], 10000)
        self.assertEqual(self.client.post(PREFIX + "/analytics/query", json={
            "dataset_id": dataset["id"], "group_by": ["index"],
        }).status_code, 422)
        result = self.post("/analytics/query", {
            "dataset_id": dataset["id"], "group_by": ["index"],
            "filters": [{"field": "index", "operator": "lt", "value": 500}],
        }, 200)
        self.assertEqual(len(result["groups"]), 500)
        with self.assertRaises(ImportProblem):
            parse_file(json.dumps(records + [{"index": 10000}]).encode(), "large.json")
        content = b'[{"a":1}]'
        exact_limit = content + b" " * (5 * 1024 * 1024 - len(content))
        self.assertEqual(parse_file(exact_limit, "max.json"), [{"a": 1}])
        with self.assertRaises(ImportProblem):
            parse_file(exact_limit + b" ", "too-large.json")


if __name__ == "__main__":
    unittest.main()
