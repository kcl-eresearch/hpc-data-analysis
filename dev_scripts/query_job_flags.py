#!/usr/bin/env python3
"""Investigate the flags column in create_job_table to identify interactive vs batch jobs.

Slurm stores job flags as a bitmask in the `flags` column. Known flag bits from
Slurm source code (src/common/slurm_protocol_defs.h) include:

Common job flags (may vary by Slurm version):
- 0x0001: KILL_INV_DEP - Kill on invalid dependency
- 0x0002: NO_KILL_INV_DEP - Don't kill on invalid dependency
- 0x0004: HAS_STATE_DIR - Has state directory
- 0x0008: BACKFILL_TEST - Used for backfill testing
- 0x0010: GRES_ENFORCE_BIND - Enforce GRES binding
- 0x0020: TEST_NOW_ONLY - Test scheduling only
- 0x0040: SPREAD_JOB - Spread job across nodes
- 0x0080: USE_MIN_NODES - Use minimum nodes
- 0x0100: JOB_KILL_HURRY - Kill job quickly (no epilog)
- 0x0200: TRES_STR_CALC - TRES string calculated
- 0x0400: SIB_JOB_FLUSH - Sibling job flush
- 0x0800: HET_JOB_FLAG - Heterogeneous job
- 0x1000: JOB_NTASKS_SET - ntasks explicitly set
- 0x2000: JOB_CPUS_SET - cpus explicitly set
- 0x4000: BF_WHOLE_NODE_TEST - Whole node test
- 0x8000: TOP_PRIO_TMP - Temporary top priority
- 0x10000: JOB_ACCRUE_OVER - Accrue limit reached
- 0x20000: GRES_DISABLE_BIND - Disable GRES binding
- 0x40000: JOB_WAS_RUNNING - Job was running
- 0x80000: RESET_ACCRUE_TIME - Reset accrue time
- 0x100000: CRON_JOB - Cron/scrontab job
- 0x200000: JOB_MEM_SET - Memory explicitly set
- 0x400000: JOB_RESIZED - Job was resized
- 0x800000: USE_DEFAULT_ACCT - Using default account
- 0x1000000: USE_DEFAULT_PART - Using default partition
- 0x2000000: USE_DEFAULT_QOS - Using default QOS
- 0x4000000: USE_DEFAULT_WCKEY - Using default wckey
- 0x8000000: JOB_DEPENDENT - Job is dependent
- 0x10000000: JOB_PROM - Job promoted

Note: Interactive jobs may be identified by:
1. Checking if they have an "interactive" step (id_step = -6)
2. Partition name (some clusters have interactive partitions)
3. Time limit patterns (interactive often has shorter limits)
4. Job name patterns

This script explores the actual flag values in the database to help understand
what's being used.

Data source: create_job_table (flags column)

Saves output to output_job_flags.txt
"""

import sys
from pathlib import Path
import mysql.connector
import yaml

# Paths relative to script location (allows running from any directory)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
OUTPUT_FILE = SCRIPT_DIR / "output_job_flags.txt"

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
    out("PART 1: Distribution of flags values")
    out("=" * 80)
    out()
    out("Top 30 most common flags values (recent jobs, Jan 2025):")
    cursor.execute("""
        SELECT flags, COUNT(*) as cnt
        FROM create_job_table
        WHERE time_submit >= UNIX_TIMESTAMP('2025-01-01')
          AND time_submit < UNIX_TIMESTAMP('2025-02-01')
        GROUP BY flags
        ORDER BY cnt DESC
        LIMIT 30
    """)
    out(f"  {'flags (decimal)':>20}  {'flags (hex)':>15}  {'count':>12}  {'%':>8}")
    rows = list(cursor)
    total = sum(r[1] for r in rows)
    for flags, cnt in rows:
        pct = (cnt / total * 100) if total else 0
        out(f"  {flags:>20}  {hex(flags):>15}  {cnt:>12}  {pct:>7.2f}%")
    out()
    out(f"  Total jobs in sample: {total}")

    # Decode individual bits for the most common values
    out()
    out("=" * 80)
    out("PART 2: Bit analysis of common flag values")
    out("=" * 80)
    out()

    # Known flag bits (from Slurm source)
    flag_names = {
        0x0001: "KILL_INV_DEP",
        0x0002: "NO_KILL_INV_DEP",
        0x0004: "HAS_STATE_DIR",
        0x0008: "BACKFILL_TEST",
        0x0010: "GRES_ENFORCE_BIND",
        0x0020: "TEST_NOW_ONLY",
        0x0040: "SPREAD_JOB",
        0x0080: "USE_MIN_NODES",
        0x0100: "JOB_KILL_HURRY",
        0x0200: "TRES_STR_CALC",
        0x0400: "SIB_JOB_FLUSH",
        0x0800: "HET_JOB_FLAG",
        0x1000: "JOB_NTASKS_SET",
        0x2000: "JOB_CPUS_SET",
        0x4000: "BF_WHOLE_NODE_TEST",
        0x8000: "TOP_PRIO_TMP",
        0x10000: "JOB_ACCRUE_OVER",
        0x20000: "GRES_DISABLE_BIND",
        0x40000: "JOB_WAS_RUNNING",
        0x80000: "RESET_ACCRUE_TIME",
        0x100000: "CRON_JOB",
        0x200000: "JOB_MEM_SET",
        0x400000: "JOB_RESIZED",
        0x800000: "USE_DEFAULT_ACCT",
        0x1000000: "USE_DEFAULT_PART",
        0x2000000: "USE_DEFAULT_QOS",
        0x4000000: "USE_DEFAULT_WCKEY",
        0x8000000: "JOB_DEPENDENT",
        0x10000000: "JOB_PROM",
    }

    def decode_flags(flags_val):
        """Decode flag bits into names."""
        bits = []
        for bit, name in sorted(flag_names.items()):
            if flags_val & bit:
                bits.append(name)
        return bits

    # Get top 10 unique flag values
    unique_flags = sorted(set(r[0] for r in rows[:15]))
    for flags in unique_flags:
        out(f"Flags = {flags} (0x{flags:08x}):")
        bits = decode_flags(flags)
        if bits:
            for bit_name in bits:
                out(f"    - {bit_name}")
        else:
            out("    (no known bits set)")
        out()

    # Part 3: Check for interactive step correlation
    out("=" * 80)
    out("PART 3: Jobs with 'interactive' step (id_step = -6)")
    out("=" * 80)
    out()
    out("Checking if jobs with interactive steps have distinct flag patterns...")

    cursor.execute("""
        SELECT j.flags, COUNT(DISTINCT j.job_db_inx) as job_count
        FROM create_job_table j
        JOIN create_step_table s ON j.job_db_inx = s.job_db_inx
        WHERE s.id_step = -6  -- interactive step
        GROUP BY j.flags
        ORDER BY job_count DESC
    """)
    rows = list(cursor)
    if rows:
        out(f"  {'flags (decimal)':>20}  {'flags (hex)':>15}  {'job_count':>12}")
        for flags, cnt in rows:
            out(f"  {flags:>20}  {hex(flags):>15}  {cnt:>12}")
    else:
        out("  No jobs found with interactive steps")

    # Part 4: Check partition patterns
    out()
    out("=" * 80)
    out("PART 4: Jobs by partition (looking for interactive partitions)")
    out("=" * 80)
    out()
    cursor.execute("""
        SELECT partition, COUNT(*) as cnt
        FROM create_job_table
        WHERE time_submit >= UNIX_TIMESTAMP('2025-01-01')
          AND time_submit < UNIX_TIMESTAMP('2025-02-01')
        GROUP BY partition
        ORDER BY cnt DESC
    """)
    out(f"  {'partition':<30}  {'count':>12}")
    for row in cursor:
        out(f"  {str(row[0]):<30}  {row[1]:>12}")

    # Part 5: Sample jobs with different flag values to see patterns
    out()
    out("=" * 80)
    out("PART 5: Sample jobs with common flag values")
    out("=" * 80)
    out()
    out("Comparing job characteristics for different flag values:")

    # Get top 3 most common flag values
    cursor.execute("""
        SELECT flags, COUNT(*) as cnt
        FROM create_job_table
        WHERE time_submit >= UNIX_TIMESTAMP('2025-01-01')
          AND time_submit < UNIX_TIMESTAMP('2025-02-01')
        GROUP BY flags
        ORDER BY cnt DESC
        LIMIT 3
    """)
    top_flags = [r[0] for r in cursor]

    for flags_val in top_flags:
        out(f"\n--- Jobs with flags = {flags_val} (0x{flags_val:08x}) ---")
        cursor.execute("""
            SELECT id_job, partition, timelimit, cpus_req, job_name
            FROM create_job_table
            WHERE flags = %s
              AND time_submit >= UNIX_TIMESTAMP('2025-01-01')
              AND time_submit < UNIX_TIMESTAMP('2025-02-01')
            ORDER BY RAND()
            LIMIT 5
        """, (flags_val,))
        out(f"  {'id_job':>12}  {'partition':<20}  {'timelimit':>10}  {'cpus':>5}  job_name")
        for row in cursor:
            out(f"  {row[0]:>12}  {str(row[1]):<20}  {row[2]:>10}  {row[3]:>5}  {row[4]}")

cursor.close()
conn.close()
print(f"\nOutput saved to {OUTPUT_FILE}", file=sys.stderr)
