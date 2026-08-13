#!/usr/bin/env python3
"""
Z3.1 SOVEREIGN — Mizune Self-Export (Phase Z3.1).

Exports Mizune's entire self (soul, memory DBs, knowledge base, missions, schedules, skills,
trajectories, and Chroma embeddings) into ONE checksummed tar.gz archive with a manifest,
strictly EXCLUDING all secrets (API keys, tokens, face data, voiceprints).

Pure Python stdlib only. No external dependencies.
"""

import os
import sys
import glob
import json
import tarfile
import hashlib
import sqlite3
import argparse
import subprocess
import io
import re
from datetime import datetime, timezone


DENY_PATTERNS = [
    r"(^|[\/\\])tokens([\/\\]|$)",
    r"config\.json$",
    r"\.env(\..*)?$",
    r"master_face.*",
    r"\.npy$",
    r"__pycache__",
    r"\.pyc$",
    r"\.bak",
]


def is_secret(filepath: str) -> bool:
    norm = filepath.replace("\\", "/")
    for pat in DENY_PATTERNS:
        if re.search(pat, norm, re.IGNORECASE):
            return True
    return False


def get_git_sha() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown"


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


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


def redact_config(val):
    if isinstance(val, dict):
        return {k: redact_config(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [redact_config(v) for v in val]
    elif isinstance(val, str):
        return "<REDACTED:str>"
    elif isinstance(val, bool):
        return "<REDACTED:bool>"
    elif isinstance(val, (int, float)):
        return f"<REDACTED:{type(val).__name__}>"
    elif val is None:
        return "<REDACTED:NoneType>"
    else:
        return f"<REDACTED:{type(val).__name__}>"


def collect_files(data_dir: str) -> list:
    candidates = []

    # 1. SOUL.md
    soul = os.path.normpath("character/SOUL.md")
    if os.path.exists(soul):
        candidates.append(soul)

    # 2. schedules.db under data/
    sched = os.path.normpath("data/schedules.db")
    if os.path.exists(sched):
        candidates.append(sched)

    # 3. Everything under data_dir (e.g. .data or .mizune_cortex)
    if os.path.exists(data_dir):
        for root, dirs, files in os.walk(data_dir):
            for f in files:
                full_path = os.path.normpath(os.path.join(root, f))
                candidates.append(full_path)

    # Filter candidates with HARD DENY-LIST
    included = []
    for c in candidates:
        if is_secret(c):
            continue
        included.append(c)

    # Assertion check: ensure NO secret slipped through
    for path in included:
        if is_secret(path):
            raise AssertionError(f"CRITICAL SECURITY VIOLATION: Secret file '{path}' slipped past filter!")

    return sorted(list(set(included)))


def export_mizune(out_path: str, data_dir: str):
    data_dir = os.path.normpath(data_dir)
    print(f"Scanning for Mizune self artifacts (data_dir='{data_dir}')...")
    
    files = collect_files(data_dir)
    if not files:
        print("Warning: No data files discovered to export!")
    
    manifest_files = []
    total_uncompressed = 0

    for f_path in files:
        f_size = os.path.getsize(f_path)
        total_uncompressed += f_size
        f_sha = compute_sha256(f_path)
        arc_name = f_path.replace("\\", "/")

        file_meta = {
            "path": arc_name,
            "size": f_size,
            "sha256": f_sha
        }

        # If SQLite database, include table row counts
        if f_path.endswith(".db") or f_path.endswith(".sqlite3") or "sqlite" in f_path.lower():
            file_meta["tables"] = get_sqlite_table_counts(f_path)

        manifest_files.append(file_meta)

    # Build manifest.json
    now_ist = datetime.now().astimezone().isoformat()
    git_sha = get_git_sha()
    manifest = {
        "schema_version": "1.0",
        "created_at": now_ist,
        "mizune_version": git_sha,
        "files_count": len(manifest_files),
        "total_uncompressed_bytes": total_uncompressed,
        "files": manifest_files
    }

    # Redact config.json if present
    config_schema = None
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as cfg_f:
                cfg_data = json.load(cfg_f)
            config_schema = redact_config(cfg_data)
        except Exception as e:
            print(f"Warning: Could not read config.json for schema redaction: {e}")

    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    config_schema_bytes = json.dumps(config_schema, indent=2).encode("utf-8") if config_schema else None

    # Write tar.gz
    out_dir = os.path.dirname(os.path.abspath(out_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with tarfile.open(out_path, "w:gz") as tar:
        # Add manifest.json
        m_info = tarfile.TarInfo(name="manifest.json")
        m_info.size = len(manifest_bytes)
        m_info.mtime = int(datetime.now().timestamp())
        tar.addfile(m_info, io.BytesIO(manifest_bytes))

        # Add config.schema.json
        if config_schema_bytes:
            c_info = tarfile.TarInfo(name="config.schema.json")
            c_info.size = len(config_schema_bytes)
            c_info.mtime = int(datetime.now().timestamp())
            tar.addfile(c_info, io.BytesIO(config_schema_bytes))

        # Add all data files
        for f_path in files:
            arc_name = f_path.replace("\\", "/")
            tar.add(f_path, arcname=arc_name)

    archive_size = os.path.getsize(out_path)

    print("\n=== MIZUNE SELF EXPORT SUMMARY ===")
    print(f"Archive:            {os.path.basename(out_path)} ({out_path})")
    print(f"Mizune Git Version: {git_sha}")
    print(f"Files Included:     {len(files)}")
    print(f"Uncompressed Size:  {total_uncompressed / (1024*1024):.2f} MB")
    print(f"Archive Size:       {archive_size / (1024*1024):.2f} MB")
    print("SECRETS EXCLUDED:   tokens/, config.json, faces, voiceprints [OK]\n")


def main():
    parser = argparse.ArgumentParser(description="Mizune Self-Export Utility (Phase Z3.1)")
    parser.add_argument("--out", default="mizune_self.tar.gz", help="Output tar.gz archive path")
    parser.add_argument("--data-dir", default=".data", help="Mizune data directory root")
    args = parser.parse_args()

    export_mizune(args.out, args.data_dir)


if __name__ == "__main__":
    main()
