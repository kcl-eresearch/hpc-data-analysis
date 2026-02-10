#!/usr/bin/env python3
"""Query table_defs_table to see if it contains schema definitions."""

import sys
from pathlib import Path
import mysql.connector
import yaml

# Paths relative to script location (allows running from any directory)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
OUTPUT_FILE = SCRIPT_DIR / "output_table_defs.txt"

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
    out("TABLE_DEFS_TABLE - Schema definitions stored by Slurm")
    out("=" * 80)
    out()

    cursor.execute("SELECT table_name, definition FROM table_defs_table")
    for row in cursor:
        table_name, definition = row
        out(f"=== {table_name} ===")
        out(definition)
        out()

cursor.close()
conn.close()
print(f"\nOutput saved to {OUTPUT_FILE}", file=sys.stderr)
