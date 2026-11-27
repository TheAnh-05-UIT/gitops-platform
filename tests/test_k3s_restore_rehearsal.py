import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.rehearse_k3s_restore import RecoveryError, check_bundle


class K3sBackupRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(TemporaryDirectory())
        self.bundle = Path(self.root) / "backup"
        self.database = self.bundle / "server/db/state.db"
        self.database.parent.mkdir(parents=True)
        self.token = self.bundle / "server/token"
        self.token.write_text("synthetic-control-plane-token", encoding="utf-8")
        self.scratch = Path(self.root) / "isolated-restore"
        self.scratch.mkdir()

    def test_fixture_database_round_trip_preserves_input(self):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("CREATE TABLE kine (name TEXT, value BLOB)")
            connection.execute("INSERT INTO kine VALUES (?, ?)", ("marker", b"synthetic object"))
            connection.commit()

        before = self.database.read_bytes()
        self.assertEqual(check_bundle(self.bundle, self.scratch), {
            "sqlite_integrity": "PASS", "kine_records": "PASS", "server_token_present": "PASS",
        })
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_includes_required_wal_state_without_touching_input(self):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA wal_autocheckpoint=0")
            connection.execute("CREATE TABLE kine (name TEXT)")
            connection.execute("INSERT INTO kine VALUES ('marker')")
            connection.commit()
            wal = self.database.with_suffix(".db-wal")
            before = wal.read_bytes()
            self.assertEqual(check_bundle(self.bundle, self.scratch)["kine_records"], "PASS")
            self.assertEqual(wal.read_bytes(), before)

    def test_missing_token_stops_before_copying(self):
        self.token.unlink()
        self.database.write_bytes(b"test")
        with self.assertRaisesRegex(RecoveryError, "server token"):
            check_bundle(self.bundle, self.scratch)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_integrity_failure_never_prints_database_content(self):
        self.database.write_bytes(b"synthetic secret")
        with self.assertRaisesRegex(RecoveryError, "^The restored copy failed SQLite validation$"):
            check_bundle(self.bundle, self.scratch)

    def test_empty_kine_table_is_not_a_usable_candidate(self):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("CREATE TABLE kine (name TEXT)")
        with self.assertRaisesRegex(RecoveryError, "Kine records"):
            check_bundle(self.bundle, self.scratch)

    def test_rollback_journal_requires_new_quiesced_backup(self):
        self.database.write_bytes(b"test")
        self.database.with_suffix(".db-journal").write_bytes(b"test journal")
        with self.assertRaisesRegex(RecoveryError, "quiesced backup"):
            check_bundle(self.bundle, self.scratch)

    def test_scratch_must_be_separate_from_bundle(self):
        with self.assertRaisesRegex(RecoveryError, "separate"):
            check_bundle(self.bundle, self.database.parent)
