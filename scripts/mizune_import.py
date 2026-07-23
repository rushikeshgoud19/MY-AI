#!/usr/bin/env python3
"""
Z3.1 SOVEREIGN — Mizune Self-Import (Phase Z3.1).

Reconstitutes Mizune from a checksummed export tar.gz archive into a clean target directory.
Verifies file SHA256 integrity, compares SQLite table row counts, enforces path-traversal safety,
protects non-empty target directories with an overwrite guard, and displays the "WHO SHE IS" readout.

Pure Python stdlib only. No external dependencies.
"""

import os
import sys
import json
import tarfile
import hashlib
import sqlite3
import argparse
import shutil


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def is_safe_path(base_dir: str, path: str) -> bool:
    base_abs = os.path.abspath(base_dir)
    target_abs = os.path.abspath(os.path.join(base_dir, path))
    return target_abs == base_abs or target_abs.startswith(base_abs + os.sep)


def get_sqlite_table_counts(filepath: str) -> dict:
    counts = {}
    try:
        abs_path = os.path.abspath(filepath)
        conn = sqlite3.connect(f"file:{abs_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for (tbl,) in tables:
            if tbl.startswith("sqlite_"):
                continue
            try:
                cnt = cursor.execute(f'SELECT count(*) FROM "{tbl}"').fetchone()[0]
                counts[tbl] = cnt
            except Exception as te:
                counts[tbl] = f"error: {te}"
        conn.close()
    except Exception as e:
        counts["_error"] = str(e)
    return counts


def import_mizune(archive_path: str, target_dir: str, force: bool = False):
    target_dir = os.path.normpath(target_dir)
    archive_path = os.path.normpath(archive_path)

    if not os.path.exists(archive_path):
        print(f"Error: Archive file '{archive_path}' not found!")
        sys.exit(1)

    # 1. Target Directory Overwrite Guard
    if os.path.exists(target_dir) and os.listdir(target_dir):
        if not force:
            print(f"Refused: Target directory '{target_dir}' is non-empty. Use --force to overwrite.")
            sys.exit(1)
        else:
            print(f"Warning: Overwriting non-empty target directory '{target_dir}' (--force supplied)...")

    os.makedirs(target_dir, exist_ok=True)

    print(f"Opening archive '{archive_path}'...")
    with tarfile.open(archive_path, "r:gz") as tar:
        members = tar.getmembers()

        # 2. Path Traversal Security Check
        for m in members:
            if not is_safe_path(target_dir, m.name):
                raise ValueError(f"CRITICAL SECURITY ALERT: Path traversal attempt detected in member '{m.name}'!")

        # 3. Read Manifest
        try:
            manifest_file = tar.extractfile("manifest.json")
            if not manifest_file:
                raise ValueError("manifest.json missing from archive root!")
            manifest = json.load(manifest_file)
        except Exception as e:
            print(f"Error reading manifest.json from archive: {e}")
            sys.exit(1)

        print(f"Manifest loaded (Schema: {manifest.get('schema_version')}, Created: {manifest.get('created_at')}, Mizune SHA: {manifest.get('mizune_version')}).")

        # 4. Safe Extraction
        print(f"Extracting {len(members)} entries into '{target_dir}'...")
        for m in members:
            # Re-verify path safety before extract
            dest_path = os.path.join(target_dir, m.name)
            if not is_safe_path(target_dir, m.name):
                raise ValueError(f"Path traversal blocked: {m.name}")
            tar.extract(m, path=target_dir)

    # 5. SHA256 Integrity Verification
    mismatches = []
    verified_count = 0
    manifest_files = manifest.get("files", [])

    for f_entry in manifest_files:
        rel_path = f_entry["path"]
        expected_sha = f_entry["sha256"]
        dest_file = os.path.normpath(os.path.join(target_dir, rel_path))

        if not os.path.exists(dest_file):
            mismatches.append((rel_path, "MISSING"))
            continue

        actual_sha = compute_sha256(dest_file)
        if actual_sha != expected_sha:
            mismatches.append((rel_path, f"SHA MISMATCH (expected {expected_sha[:8]}, got {actual_sha[:8]})"))
        else:
            verified_count += 1

    if mismatches:
        print("\nINTEGRITY FAILED! Mismatched or missing files:")
        for r_path, err in mismatches:
            print(f" - {r_path}: {err}")
        sys.exit(1)

    print(f"\nINTEGRITY OK ({verified_count} files verified)")

    # 6. SQLite Table Row Count Comparison Table
    print("\n=== SQLITE ROW COUNT VERIFICATION TABLE ===")
    print(f"{'FILE':<45} | {'MANIFEST TABLES':<25} | {'RESTORED TABLES':<25} | {'STATUS'}")
    print("-" * 110)

    for f_entry in manifest_files:
        if "tables" in f_entry:
            rel_path = f_entry["path"]
            manifest_tables = f_entry["tables"]
            dest_file = os.path.normpath(os.path.join(target_dir, rel_path))
            restored_tables = get_sqlite_table_counts(dest_file)

            diffs = []
            all_keys = sorted(list(set(manifest_tables.keys()) | set(restored_tables.keys())))
            for k in all_keys:
                m_val = manifest_tables.get(k, 0)
                r_val = restored_tables.get(k, 0)
                if m_val != r_val:
                    diffs.append(f"{k}:{m_val}->{r_val}")

            status = "OK" if not diffs else f"DIFF ({', '.join(diffs)})"
            m_summary = str(manifest_tables) if len(str(manifest_tables)) < 25 else f"{len(manifest_tables)} tables"
            r_summary = str(restored_tables) if len(str(restored_tables)) < 25 else f"{len(restored_tables)} tables"

            print(f"{rel_path:<45} | {m_summary:<25} | {r_summary:<25} | {status}")

    # 7. "WHO SHE IS" Profile Readout
    _print_who_she_is(target_dir)


def _print_who_she_is(target_dir: str):
    mem_db = None
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            if f == "mizune_memory.db":
                mem_db = os.path.join(root, f)
                break
        if mem_db:
            break

    print("\n=== WHO SHE IS (RESTORED PROFILE) ===")
    if not mem_db or not os.path.exists(mem_db):
        print("mizune_memory.db not found in restored files.")
        return

    try:
        conn = sqlite3.connect(f"file:{os.path.abspath(mem_db)}?mode=ro", uri=True)
        cursor = conn.cursor()

        # Query preferences table for master name & core directives
        master_name = "Master"
        core_directives_count = 0
        try:
            row = cursor.execute("SELECT val FROM preferences WHERE key='user_profile' OR key='master_profile'").fetchone()
            if row and row[0]:
                try:
                    prof = json.loads(row[0])
                    master_name = prof.get("name") or prof.get("preferred_name") or "Master"
                except Exception:
                    master_name = row[0]
            
            cd_row = cursor.execute("SELECT val FROM preferences WHERE key='core_directives'").fetchone()
            if cd_row and cd_row[0]:
                try:
                    cds = json.loads(cd_row[0])
                    core_directives_count = len(cds) if isinstance(cds, list) else 1
                except Exception:
                    core_directives_count = 1
        except Exception:
            pass

        # Query history table for total turn count
        history_count = 0
        try:
            history_count = cursor.execute("SELECT count(*) FROM history").fetchone()[0]
        except Exception:
            pass

        conn.close()

        print(f"Master Name:     {master_name}")
        print(f"Core Directives: {core_directives_count}")
        print(f"Total History:   {history_count} turns")

    except Exception as e:
        print(f"Error reading restored profile: {e}")


def main():
    parser = argparse.ArgumentParser(description="Mizune Self-Import Utility (Phase Z3.1)")
    parser.add_argument("archive", nargs="?", default="mizune_self.tar.gz", help="Archive path to import")
    parser.add_argument("--target", default="./mizune_restore", help="Target directory for extraction")
    parser.add_argument("--force", action="store_true", help="Allow overwriting non-empty target directory")
    args = parser.parse_args()

    import_mizune(args.archive, args.target, args.force)


if __name__ == "__main__":
    main()
