#!/usr/bin/env python3
"""Dump the MySQL Slurm database schema (tables and columns)."""

import sys
from pathlib import Path
import mysql.connector
import yaml

# Paths relative to script location (allows running from any directory)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
OUTPUT_FILE = SCRIPT_DIR / "output_schema.txt"

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

    # Get all tables
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    out("=== TABLES ===")
    for table in tables:
        out(f"  {table}")

    # Get columns for each table
    for table in tables:
        out(f"\n  === {table} ===")
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        for row in cursor.fetchall():
            col_name = row[0]
            col_type = row[1]
            out(f"  {col_name:<30} {col_type}")

cursor.close()
conn.close()
print(f"\nOutput saved to {OUTPUT_FILE}", file=sys.stderr)
