#!/usr/bin/env python3
"""Query to see what job states exist in the database (recent jobs only for speed)."""

import sys
from pathlib import Path
import mysql.connector
import yaml

# Paths relative to script location (allows running from any directory)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
OUTPUT_FILE = SCRIPT_DIR / "output_job_states.txt"

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

    out("=== JOB STATES IN DATABASE (Jan 2025) ===")
    out("state_code, count")
    cursor.execute("""
        SELECT state, COUNT(*) as cnt
        FROM create_job_table
        WHERE time_submit >= UNIX_TIMESTAMP('2025-01-01')
          AND time_submit < UNIX_TIMESTAMP('2025-02-01')
        GROUP BY state
        ORDER BY cnt DESC
    """)
    for row in cursor:
        out(f"{row[0]}, {row[1]}")

    out("\nTo find what each code means, run:")
    out("  sacct -j <job_id> -o JobID,State")
    out("for a job with that state, then compare with the code above.")

cursor.close()
conn.close()
print(f"\nOutput saved to {OUTPUT_FILE}", file=sys.stderr)
