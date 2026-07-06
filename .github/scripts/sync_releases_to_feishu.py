#!/usr/bin/env python3
"""
Sync GitHub Releases to Feishu Bitable (incremental)
Reads config from environment variables.
"""

import os
import re
import sys
import time
import json
import requests
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# ===== Configuration from environment =====
USER_TOKEN = os.environ.get("FEISHU_USER_TOKEN", "")
APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN", "")
TABLE_ID = os.environ.get("FEISHU_TABLE_ID", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")

# Column names (modify if your table uses different names)
COL_VERSION = "版本号"
COL_FEATURES = "新功能"
COL_CONTRIBUTORS = "贡献者"
COL_TIMESTAMP = "时间戳"

# Rate limit sleep (seconds)
SLEEP = 0.2

# ===== API endpoints =====
FEISHU_API = "https://open.feishu.cn/open-apis"


def get_fields(token: str, app: str, table: str) -> Dict[str, str]:
    """Fetch field name -> field ID mapping."""
    url = f"{FEISHU_API}/bitable/v1/apps/{app}/tables/{table}/fields"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to get fields: {data}")
    return {f["field_name"]: f["field_id"] for f in data.get("data", {}).get("items", [])}


def list_records(token: str, app: str, table: str) -> List[Dict]:
    """Fetch all records from the table (with pagination)."""
    url = f"{FEISHU_API}/bitable/v1/apps/{app}/tables/{table}/records"
    headers = {"Authorization": f"Bearer {token}"}
    all_records = []
    page_token = None
    while True:
        params = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Failed to list records: {data}")
        items = data.get("data", {}).get("items", [])
        all_records.extend(items)
        if not data.get("data", {}).get("has_more"):
            break
        page_token = data["data"]["page_token"]
        time.sleep(SLEEP)
    return all_records


def add_record(token: str, app: str, table: str, fields: Dict[str, object]) -> Dict:
    """Add a new record."""
    url = f"{FEISHU_API}/bitable/v1/apps/{app}/tables/{table}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"fields": fields})
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Add record failed: {data}")
    return data


def update_record(token: str, app: str, table: str, record_id: str, fields: Dict[str, object]) -> Dict:
    """Update an existing record."""
    url = f"{FEISHU_API}/bitable/v1/apps/{app}/tables/{table}/records/{record_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.put(url, headers=headers, json={"fields": fields})
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Update record failed: {data}")
    return data


def get_releases(repo: str) -> List[Dict]:
    """Fetch all non-draft GitHub releases, sorted newest first."""
    url = f"https://api.github.com/repos/{repo}/releases"
    resp = requests.get(url)
    resp.raise_for_status()
    releases = resp.json()
    releases = [r for r in releases if not r.get("draft", False)]
    releases.sort(key=lambda x: x["published_at"], reverse=True)
    return releases


def parse_body(body: str) -> Tuple[str, str]:
    """
    Extract 'features' and 'contributors' from release body.
    Supports:
      - Explicit prefix: 'Contributors:' or 'Authors:' (Chinese)
      - Standalone line with Chinese names separated by 、 or ，
      - GitHub @mentions
    """
    if not body:
        return "", ""

    # 1. Explicit prefix (Chinese)
    m = re.search(r'(?:Contributors|Authors)[：:]\s*(.+)', body, re.IGNORECASE)
    if m:
        contributors = m.group(1).strip()
        feature_text = body.replace(m.group(0), "").strip()
    else:
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        contributors = ""
        # 2. Standalone Chinese name line
        for ln in reversed(lines):
            if re.search(r'[\u4e00-\u9fa5]+[、，,]\s*[\u4e00-\u9fa5]+', ln) and not re.match(r'^[-*#\s]+', ln):
                contributors = ln
                feature_text = "\n".join([l for l in lines if l != ln])
                break
        else:
            # 3. GitHub @mentions
            mentions = re.findall(r'@([A-Za-z0-9_-]+)', body)
            if mentions:
                seen = set()
                unique = []
                for m in mentions:
                    if m not in seen:
                        seen.add(m)
                        unique.append(m)
                contributors = ", ".join(unique)  # comma-separated
                feature_text = body.strip()
            else:
                contributors = ""
                feature_text = body.strip()

    # Clean extra blank lines
    lines = [ln.strip() for ln in feature_text.splitlines() if ln.strip()]
    feature_text = "\n".join(lines)
    return feature_text, contributors


def format_date(dt: datetime) -> str:
    """Format datetime to YYYY-MM-DD."""
    return dt.strftime("%Y-%m-%d")


def main():
    # Validate environment
    if not all([USER_TOKEN, APP_TOKEN, TABLE_ID, REPO]):
        print("ERROR: Missing environment variables. Need:")
        print("  FEISHU_USER_TOKEN, FEISHU_APP_TOKEN, FEISHU_TABLE_ID, GITHUB_REPOSITORY")
        sys.exit(1)

    print("Fetching field mapping...")
    field_map = get_fields(USER_TOKEN, APP_TOKEN, TABLE_ID)
    required = [COL_VERSION, COL_FEATURES, COL_CONTRIBUTORS, COL_TIMESTAMP]
    for col in required:
        if col not in field_map:
            print(f"ERROR: Column '{col}' not found in table. Available: {list(field_map.keys())}")
            sys.exit(1)
    print("  Field mapping OK")

    print(f"Fetching GitHub releases from {REPO}...")
    releases = get_releases(REPO)
    print(f"  Found {len(releases)} releases")

    print("Fetching existing records from Feishu...")
    records = list_records(USER_TOKEN, APP_TOKEN, TABLE_ID)
    existing = {}
    for rec in records:
        ver = rec.get("fields", {}).get(COL_VERSION)
        if ver:
            existing[ver] = rec["record_id"]
    print(f"  Found {len(existing)} existing records")

    print("\nStarting sync (only new releases will be added)...")
    count = 0
    for idx, rel in enumerate(releases, 1):
        ver = rel["tag_name"]
        if ver in existing:
            print(f"[{idx}/{len(releases)}] {ver} already exists, skipping")
            continue

        pub = datetime.strptime(rel["published_at"], "%Y-%m-%dT%H:%M:%SZ")
        body = rel.get("body") or ""
        features, contributors = parse_body(body)

        fields_data = {
            COL_VERSION: ver,
            COL_FEATURES: features,
            COL_CONTRIBUTORS: contributors,
            COL_TIMESTAMP: format_date(pub)
        }

        print(f"[{idx}/{len(releases)}] Adding {ver} ...")
        try:
            result = add_record(USER_TOKEN, APP_TOKEN, TABLE_ID, fields_data)
            rec_id = result.get("data", {}).get("record", {}).get("record_id")
            print(f"  Success, record ID: {rec_id}")
            count += 1
        except Exception as e:
            print(f"  Failed: {e}")

        if idx < len(releases):
            time.sleep(SLEEP)

    print(f"\nDone! Added {count} new release(s).")


if __name__ == "__main__":
    main()