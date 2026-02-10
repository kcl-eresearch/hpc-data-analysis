#!/usr/bin/env python3
"""Sample CPU time variables from create_step_table.

CPU time is stored directly in columns (not TRES-encoded):
- user_sec, user_usec: user-space CPU time
- sys_sec, sys_usec: kernel/system CPU time
"""

import sys
from pathlib import Path
import mysql.connector
import yaml

# Paths relative to script location (allows running from any directory)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
OUTPUT_FILE = SCRIPT_DIR / "output_cpu_time.txt"

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

    out("=" * 80)
    out("CPU TIME VARIABLES IN create_step_table")
    out("=" * 80)
    out("Columns: user_sec, user_usec, sys_sec, sys_usec")
    out("  - user_sec/usec: CPU time spent in user space")
    out("  - sys_sec/usec: CPU time spent in kernel/system calls")
    out("  - Total CPU time = user_sec + sys_sec + (user_usec + sys_usec) / 1,000,000")
    out()

    cursor.execute("""
        SELECT
            job_db_inx,
            id_step,
            step_name,
            user_sec,
            user_usec,
            sys_sec,
            sys_usec
        FROM create_step_table
        WHERE user_sec > 0 OR sys_sec > 0
        ORDER BY job_db_inx DESC
        LIMIT 10
    """)

    out("Sample steps (10 most recent with CPU time > 0):")
    out()
    out(f"  {'job_db_inx':>12}  {'id_step':>8}  {'step_name':>12}  {'user_sec':>10}  {'user_usec':>10}  {'sys_sec':>10}  {'sys_usec':>10}  {'total_cpu':>12}")
    out(f"  {'-'*12}  {'-'*8}  {'-'*12}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*12}")

    for row in cursor:
        job_db_inx, id_step, step_name, user_sec, user_usec, sys_sec, sys_usec = row
        total_cpu = user_sec + sys_sec + (user_usec + sys_usec) / 1_000_000
        out(f"  {job_db_inx:>12}  {id_step:>8}  {str(step_name):>12}  {user_sec:>10}  {user_usec:>10}  {sys_sec:>10}  {sys_usec:>10}  {total_cpu:>12.2f}")

cursor.close()
conn.close()
print(f"\nOutput saved to {OUTPUT_FILE}", file=sys.stderr)
