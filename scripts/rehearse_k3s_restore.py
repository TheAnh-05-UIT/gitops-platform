"""Check a staged SQLite backup in a disposable, caller-approved directory."""

import argparse
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory


class RecoveryError(ValueError):
    """A recovery artifact failed a check suitable for sanitized evidence."""


def _local(path):
    if path.as_posix().startswith("//") or path.is_symlink():
        raise RecoveryError("The rehearsal only accepts ordinary local paths")
    resolved = path.resolve(strict=True)
    if resolved != path.absolute():
        raise RecoveryError("The rehearsal only accepts ordinary local paths")
    return resolved


def _required_file(path):
    try:
        return _local(path).is_file() and path.stat().st_size > 0
    except FileNotFoundError:
        return False


def check_bundle(bundle, scratch):
    """Inspect database integrity and verify token presence without reading it."""
    bundle, scratch = _local(bundle), _local(scratch)
    if not bundle.is_dir() or not scratch.is_dir():
        raise RecoveryError("Bundle and scratch must be existing directories")
    if scratch.is_relative_to(bundle) or bundle.is_relative_to(scratch):
        raise RecoveryError("Bundle and scratch must be separate directories")
    if any(path.is_relative_to(Path("/var/lib/rancher/k3s")) for path in (bundle, scratch)):
        raise RecoveryError("Use staged files outside the active K3s data directory")

    token = bundle / "server/token"
    database = bundle / "server/db/state.db"
    if not _required_file(token):
        raise RecoveryError("A nonempty server token file is required")
    if not _required_file(database):
        raise RecoveryError("A nonempty SQLite state database is required")
    if _required_file(database.with_suffix(".db-journal")):
        raise RecoveryError("A rollback journal requires a fresh quiesced backup")

    with TemporaryDirectory(prefix="k3s-sqlite-", dir=scratch) as temp:
        destination = Path(temp) / database.name
        shutil.copyfile(database, destination)
        wal = database.with_suffix(".db-wal")
        if _required_file(wal):
            shutil.copyfile(wal, destination.with_suffix(".db-wal"))
        try:
            with closing(sqlite3.connect(destination.as_uri() + "?mode=ro", uri=True)) as db:
                db.execute("PRAGMA trusted_schema=OFF")
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise RecoveryError("The restored copy failed SQLite validation")
                kine_table = db.execute(
                    "SELECT 1 FROM sqlite_schema WHERE name = 'kine' AND type = 'table'"
                ).fetchone()
                marker = db.execute("SELECT 1 FROM kine LIMIT 1").fetchone() if kine_table else None
                if marker is None:
                    raise RecoveryError("The restored copy has no Kine records")
        except sqlite3.DatabaseError as error:
            raise RecoveryError("The restored copy failed SQLite validation") from error
    return {"sqlite_integrity": "PASS", "kine_records": "PASS", "server_token_present": "PASS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--scratch-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check_bundle(args.bundle, args.scratch_dir)
    except RecoveryError as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}))
        return 1
    except OSError:
        print(json.dumps({"status": "FAIL", "reason": "Could not access private rehearsal files"}))
        return 1
    print(json.dumps({"status": "PASS", **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
