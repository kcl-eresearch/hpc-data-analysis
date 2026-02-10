#!/usr/bin/env python3
"""Debug memory values for a few specific jobs."""

import sys
from pathlib import Path
import mysql.connector
import re
import yaml

# Paths relative to script location (allows running from any directory)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
OUTPUT_FILE = SCRIPT_DIR / "output_memory.txt"

def parse_tres_value(tres_string, tres_id):
    if not tres_string:
        return 0
    try:
        for pair in tres_string.split(','):
            if '=' in pair:
                tid, value = pair.split('=', 1)
                if int(tid) == tres_id:
                    return int(value)
    except (ValueError, AttributeError):
        pass
    return 0

with open(CONFIG_FILE, "r") as f:
    config = yaml.safe_load(f)
mysql_conf = config["mysql"]
conn = mysql.connector.connect(
    host=mysql_conf["host"],
    user=mysql_conf["user"],
    password=mysql_conf["password"],
    database=mysql_conf["database"],
)
cursor = conn.cursor()

with open(OUTPUT_FILE, 'w') as f:
    def out(text=""):
        print(text)
        print(text, file=f)

    # Get a few jobs with their steps
    cursor.execute("""
        SELECT j.id_job, j.job_db_inx, j.tres_req, a.user
        FROM create_job_table j
        JOIN create_assoc_table a ON j.id_assoc = a.id_assoc
        WHERE j.time_submit >= UNIX_TIMESTAMP('2025-01-01')
          AND j.time_submit < UNIX_TIMESTAMP('2025-01-02')
          AND j.state = 3
        LIMIT 5
    """)

    jobs = list(cursor)

    out("=== JOB MEMORY ANALYSIS ===\n")

    for id_job, job_db_inx, tres_req, user in jobs:
        out(f"Job {id_job} (user: {user})")
        out(f"  tres_req: {tres_req}")

        reqmem_raw = parse_tres_value(tres_req, 2)
        out(f"  Requested memory (raw value from tres_req): {reqmem_raw}")
        out(f"  If MB: {reqmem_raw} MB = {reqmem_raw / 1024:.2f} GB")

        # Get steps for this job
        cursor.execute("""
            SELECT id_step, tres_usage_in_max
            FROM create_step_table
            WHERE job_db_inx = %s
        """, (job_db_inx,))

        steps = list(cursor)
        out(f"  Steps ({len(steps)}):")

        max_mem = 0
        for step_id, tres_usage in steps:
            mem_raw = parse_tres_value(tres_usage, 2)
            if mem_raw > max_mem:
                max_mem = mem_raw
            out(f"    Step {step_id}: tres_usage_in_max = {tres_usage}")
            out(f"      Memory (raw): {mem_raw}")
            if mem_raw > 0:
                out(f"      If bytes: {mem_raw / 1024 / 1024:.2f} MB")
                out(f"      If KB: {mem_raw / 1024:.2f} MB = {mem_raw / 1024 / 1024:.2f} GB")

        out(f"  Max memory across steps (raw): {max_mem}")
        if max_mem > 0 and reqmem_raw > 0:
            # Try different unit interpretations
            out(f"  Efficiency if maxrss=bytes, reqmem=MB: {max_mem / (reqmem_raw * 1024 * 1024) * 100:.2f}%")
            out(f"  Efficiency if maxrss=KB, reqmem=MB: {(max_mem * 1024) / (reqmem_raw * 1024 * 1024) * 100:.2f}%")
            out(f"  Efficiency if both in same units: {max_mem / reqmem_raw * 100:.2f}%")
        out()

cursor.close()
conn.close()
print(f"\nOutput saved to {OUTPUT_FILE}", file=sys.stderr)
