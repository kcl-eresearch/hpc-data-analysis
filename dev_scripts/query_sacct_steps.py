#!/usr/bin/env python3
"""Investigate what sacct reports at the job-level vs step-level, and cross-reference
with MySQL database fields (including submit_line).

Background on Slurm job steps (from https://slurm.schedmd.com/job_launch.html):

- **Batch step** (.batch): Created automatically when a job is submitted via `sbatch`.
  Runs the batch script on the first allocated node.

- **Normal/srun steps** (.0, .1, .2, ...): Created each time `srun` is called.
  Can be called from within an sbatch script, or directly to launch a job.

- **Extern step** (.extern): Created for every job to track resources used outside
  of Slurm steps on the allocated nodes.

This means we expect three patterns in sacct output:
  A) job-level + .batch only         → sbatch job, script did not call srun
  B) job-level + .0 only             → direct srun job (no batch script)
  C) job-level + .batch + .0 [+ .1]  → sbatch job whose script called srun

In the MySQL step table, special steps (batch, extern, interactive) have
negative id_step values. Normal srun steps have id_step >= 0.

This script:
1. Discovers special step IDs from the database
2. Finds example jobs for each of the three patterns above
3. Shows sacct output AND submit_line for each, so we can verify:
   - Is TotalCPU populated at the job level? Does it aggregate across steps?
   - Is MaxRSS populated at the job level, or only at step level?
   - Does the submit_line confirm the submission method?

Must be run on the cluster (needs both MySQL access and sacct).

Saves output to output_sacct_steps.txt
"""

import subprocess
import sys
from pathlib import Path
import mysql.connector
import yaml

# Find project root by searching upward for config.yaml
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
while not (PROJECT_ROOT / "config.yaml").exists():
    if PROJECT_ROOT == PROJECT_ROOT.parent:
        sys.exit("ERROR: Could not find config.yaml in any parent directory.")
    PROJECT_ROOT = PROJECT_ROOT.parent

sys.path.insert(0, str(PROJECT_ROOT / "src"))
from hpc_data_analysis.slurm_utils import discover_special_steps

CONFIG_FILE = PROJECT_ROOT / "config.yaml"
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "output_sacct_steps.txt"
FIELDS = "JobID,JobName,State,Elapsed,TotalCPU,MaxRSS,AllocCPUs,ReqMem,NTasks"

with open(CONFIG_FILE, "r") as cf:
    config = yaml.safe_load(cf)
mysql_conf = config["mysql"]
conn = mysql.connector.connect(
    host=mysql_conf["host"],
    user=mysql_conf["user"],
    password=mysql_conf["password"],
    database=mysql_conf["database"],
)
cursor = conn.cursor()


def run_sacct(jid):
    """Get sacct output for a single job."""
    result = subprocess.run(
        ["sacct", "--allusers", "-j", str(jid), "-nPo", FIELDS],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_submit_line(job_id):
    """Get submit_line from MySQL for a given job ID."""
    cursor.execute(
        "SELECT submit_line FROM create_job_table WHERE id_job = %s LIMIT 1",
        (job_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else "(not found)"


with open(OUTPUT_FILE, 'w') as f:
    def out(text=""):
        print(text)
        print(text, file=f)

    # ================================================================
    # PART 1: Discover special step IDs
    # ================================================================
    out("=" * 80)
    out("PART 1: Discover special step IDs from the database")
    out("=" * 80)
    out()
    out("Special steps have negative id_step values in create_step_table.")
    out("(See https://slurm.schedmd.com/job_launch.html)")
    out()

    special_steps = discover_special_steps(cursor)
    for step_name, id_step in sorted(special_steps.items(), key=lambda x: x[1]):
        out(f"  id_step = {id_step:>5}  step_name = {step_name}")

    batch_id = special_steps.get('batch')
    interactive_id = special_steps.get('interactive')
    out()
    out(f"  Batch step id_step = {batch_id}")
    out(f"  Interactive step id_step = {interactive_id}")

    if batch_id is None:
        out("  WARNING: No batch step found — cannot categorise jobs properly.")

    # ================================================================
    # PART 2: Count jobs by step pattern
    # ================================================================
    out()
    out("=" * 80)
    out("PART 2: Job counts by step pattern (Jan 15, 2025, completed jobs)")
    out("=" * 80)
    out()
    out(f"Categorising based on presence of batch step (id_step = {batch_id}) "
        f"and regular srun steps (id_step >= 0).")
    out()

    # Pattern A: has batch step, no srun steps
    cursor.execute("""
        SELECT COUNT(DISTINCT j.id_job)
        FROM create_job_table j
        JOIN create_step_table s ON j.job_db_inx = s.job_db_inx
        WHERE j.time_submit >= UNIX_TIMESTAMP('2025-01-15')
          AND j.time_submit < UNIX_TIMESTAMP('2025-01-16')
          AND j.state = 3
          AND s.id_step = %s
          AND j.job_db_inx NOT IN (
              SELECT s2.job_db_inx FROM create_step_table s2
              WHERE s2.id_step >= 0
          )
    """, (batch_id,))
    count_a = cursor.fetchone()[0]
    out(f"  Pattern A (batch step only, no srun):  {count_a}")

    # Pattern B: has srun steps, no batch step
    cursor.execute("""
        SELECT COUNT(DISTINCT j.id_job)
        FROM create_job_table j
        JOIN create_step_table s ON j.job_db_inx = s.job_db_inx
        WHERE j.time_submit >= UNIX_TIMESTAMP('2025-01-15')
          AND j.time_submit < UNIX_TIMESTAMP('2025-01-16')
          AND j.state = 3
          AND s.id_step >= 0
          AND j.job_db_inx NOT IN (
              SELECT s2.job_db_inx FROM create_step_table s2
              WHERE s2.id_step = %s
          )
    """, (batch_id,))
    count_b = cursor.fetchone()[0]
    out(f"  Pattern B (srun steps only, no batch):  {count_b}")

    # Pattern C: has both batch step and srun steps
    cursor.execute("""
        SELECT COUNT(DISTINCT j.id_job)
        FROM create_job_table j
        WHERE j.time_submit >= UNIX_TIMESTAMP('2025-01-15')
          AND j.time_submit < UNIX_TIMESTAMP('2025-01-16')
          AND j.state = 3
          AND j.job_db_inx IN (
              SELECT s.job_db_inx FROM create_step_table s
              WHERE s.id_step = %s
          )
          AND j.job_db_inx IN (
              SELECT s.job_db_inx FROM create_step_table s
              WHERE s.id_step >= 0
          )
    """, (batch_id,))
    count_c = cursor.fetchone()[0]
    out(f"  Pattern C (batch + srun steps):         {count_c}")

    total = count_a + count_b + count_c
    out()
    out(f"  Total: {total}")
    if total > 0:
        out(f"  Pattern A: {count_a/total*100:.1f}%")
        out(f"  Pattern B: {count_b/total*100:.1f}%")
        out(f"  Pattern C: {count_c/total*100:.1f}%")

    # ================================================================
    # PART 3: Sample jobs for each pattern — sacct + submit_line
    # ================================================================
    out()
    out("=" * 80)
    out("PART 3: Sample jobs for each pattern (sacct output + submit_line)")
    out("=" * 80)
    out()
    out(f"sacct fields: {FIELDS}")

    # --- Pattern A: batch only ---
    out()
    out("-" * 70)
    out("Pattern A: batch step only (no srun steps)")
    out("-" * 70)
    cursor.execute("""
        SELECT j.id_job
        FROM create_job_table j
        JOIN create_step_table s ON j.job_db_inx = s.job_db_inx
        WHERE j.time_submit >= UNIX_TIMESTAMP('2025-01-15')
          AND j.time_submit < UNIX_TIMESTAMP('2025-01-16')
          AND j.state = 3
          AND s.id_step = %s
          AND j.job_db_inx NOT IN (
              SELECT s2.job_db_inx FROM create_step_table s2
              WHERE s2.id_step >= 0
          )
        LIMIT 5
    """, (batch_id,))
    pattern_a_ids = [row[0] for row in cursor]

    for jid in pattern_a_ids:
        out(f"\n  --- Job {jid} ---")
        out(f"  submit_line: {get_submit_line(jid)}")
        raw = run_sacct(jid)
        if raw:
            for line in raw.splitlines():
                out(f"    {line}")
        else:
            out("    (sacct returned no data)")

    # --- Pattern B: srun only ---
    out()
    out("-" * 70)
    out("Pattern B: srun steps only (no batch step)")
    out("-" * 70)
    cursor.execute("""
        SELECT j.id_job
        FROM create_job_table j
        JOIN create_step_table s ON j.job_db_inx = s.job_db_inx
        WHERE j.time_submit >= UNIX_TIMESTAMP('2025-01-15')
          AND j.time_submit < UNIX_TIMESTAMP('2025-01-16')
          AND j.state = 3
          AND s.id_step >= 0
          AND j.job_db_inx NOT IN (
              SELECT s2.job_db_inx FROM create_step_table s2
              WHERE s2.id_step = %s
          )
        LIMIT 5
    """, (batch_id,))
    pattern_b_ids = [row[0] for row in cursor]

    for jid in pattern_b_ids:
        out(f"\n  --- Job {jid} ---")
        out(f"  submit_line: {get_submit_line(jid)}")
        raw = run_sacct(jid)
        if raw:
            for line in raw.splitlines():
                out(f"    {line}")
        else:
            out("    (sacct returned no data)")

    # --- Pattern C: batch + srun ---
    out()
    out("-" * 70)
    out("Pattern C: batch step + srun steps")
    out("-" * 70)
    cursor.execute("""
        SELECT j.id_job
        FROM create_job_table j
        WHERE j.time_submit >= UNIX_TIMESTAMP('2025-01-15')
          AND j.time_submit < UNIX_TIMESTAMP('2025-01-16')
          AND j.state = 3
          AND j.job_db_inx IN (
              SELECT s.job_db_inx FROM create_step_table s
              WHERE s.id_step = %s
          )
          AND j.job_db_inx IN (
              SELECT s.job_db_inx FROM create_step_table s
              WHERE s.id_step >= 0
          )
        LIMIT 5
    """, (batch_id,))
    pattern_c_ids = [row[0] for row in cursor]

    for jid in pattern_c_ids:
        out(f"\n  --- Job {jid} ---")
        out(f"  submit_line: {get_submit_line(jid)}")
        raw = run_sacct(jid)
        if raw:
            for line in raw.splitlines():
                out(f"    {line}")
        else:
            out("    (sacct returned no data)")

    # ================================================================
    # PART 4: Focused comparison — TotalCPU and MaxRSS at each level
    # ================================================================
    out()
    out("=" * 80)
    out("PART 4: TotalCPU and MaxRSS — job-level vs step-level")
    out("=" * 80)
    out()
    out("From sacct docs (https://slurm.schedmd.com/sacct.html):")
    out("  'Without including steps, utilization statistics for job")
    out("   allocation(s) will be reported as zero.' (-X flag description)")
    out()
    out("Questions:")
    out("  1. Is TotalCPU populated at the job-level allocation line?")
    out("  2. Is MaxRSS populated at the job level, or only at step level?")
    out("  3. For multi-step jobs (pattern C), does job-level TotalCPU sum the steps?")

    def show_comparison(label, job_ids):
        out(f"\n--- {label} ---")
        out(f"  {'JobID':<30}  {'TotalCPU':<20}  {'MaxRSS':<15}  {'AllocCPUs':<10}")
        out(f"  {'-'*30}  {'-'*20}  {'-'*15}  {'-'*10}")
        for jid in job_ids:
            raw = run_sacct(jid)
            if not raw:
                out(f"  {jid:<30}  (no sacct data)")
                continue
            for line in raw.splitlines():
                parts = line.split("|")
                step_jid = parts[0] if len(parts) > 0 else ""
                totalcpu = parts[4] if len(parts) > 4 else ""
                maxrss = parts[5] if len(parts) > 5 else ""
                alloccpus = parts[6] if len(parts) > 6 else ""
                out(f"  {step_jid:<30}  {totalcpu:<20}  {maxrss:<15}  {alloccpus:<10}")
            out()

    show_comparison("Pattern A (batch only)", pattern_a_ids)
    show_comparison("Pattern B (srun only)", pattern_b_ids)
    show_comparison("Pattern C (batch + srun)", pattern_c_ids)

    # ================================================================
    # PART 5: Compare CPU time — sacct vs database aggregation
    # ================================================================
    out()
    out("=" * 80)
    out("PART 5: CPU time comparison — sacct job-level vs database aggregation")
    out("=" * 80)
    out()
    out("Comparing sacct's job-level TotalCPU against our database CPU time")
    out("aggregation (same logic as fetch_job_data in slurm_utils.py).")
    out()

    def parse_sacct_time(time_str):
        """Parse sacct time format [D-]HH:MM:SS or MM:SS.ms to seconds."""
        if not time_str:
            return 0.0
        days = 0
        if '-' in time_str:
            day_part, time_str = time_str.split('-', 1)
            days = int(day_part)
        parts = time_str.split(':')
        if len(parts) == 2:
            # MM:SS.ms
            return days * 86400 + int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            # HH:MM:SS
            return days * 86400 + int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return 0.0

    exclude_ids = ", ".join(str(sid) for sid in special_steps.values())
    all_sample_ids = [
        ("A", pattern_a_ids),
        ("B", pattern_b_ids),
        ("C", pattern_c_ids),
    ]

    out(f"  {'Pattern':<9}  {'Job ID':<12}  {'sacct (s)':>12}  {'DB (s)':>12}  {'Diff (s)':>10}  Result")
    out(f"  {'-'*9}  {'-'*12}  {'-'*12}  {'-'*12}  {'-'*10}  {'-'*6}")

    for pattern, job_ids in all_sample_ids:
        for jid in job_ids:
            # Get sacct job-level TotalCPU
            raw = run_sacct(jid)
            sacct_cpu_sec = None
            if raw:
                for line in raw.splitlines():
                    parts = line.split('|')
                    if parts[0] == str(jid):
                        sacct_cpu_sec = parse_sacct_time(parts[4])
                        break

            # Get DB aggregated CPU time (same logic as fetch_job_data)
            cursor.execute(f"""
                SELECT
                    COALESCE(
                        NULLIF(SUM(CASE WHEN s.id_step NOT IN ({exclude_ids})
                                        THEN s.user_sec ELSE 0 END), 0),
                        MAX(CASE WHEN s.id_step = {batch_id} THEN s.user_sec END),
                        0
                    ),
                    COALESCE(
                        NULLIF(SUM(CASE WHEN s.id_step NOT IN ({exclude_ids})
                                        THEN s.sys_sec ELSE 0 END), 0),
                        MAX(CASE WHEN s.id_step = {batch_id} THEN s.sys_sec END),
                        0
                    ),
                    COALESCE(
                        NULLIF(SUM(CASE WHEN s.id_step NOT IN ({exclude_ids})
                                        THEN s.user_usec ELSE 0 END), 0),
                        MAX(CASE WHEN s.id_step = {batch_id} THEN s.user_usec END),
                        0
                    ),
                    COALESCE(
                        NULLIF(SUM(CASE WHEN s.id_step NOT IN ({exclude_ids})
                                        THEN s.sys_usec ELSE 0 END), 0),
                        MAX(CASE WHEN s.id_step = {batch_id} THEN s.sys_usec END),
                        0
                    )
                FROM create_job_table j
                LEFT JOIN create_step_table s ON j.job_db_inx = s.job_db_inx
                WHERE j.id_job = %s
                GROUP BY j.job_db_inx
            """, (jid,))
            db_row = cursor.fetchone()
            db_cpu_sec = None
            if db_row:
                user_sec = float(db_row[0] or 0)
                sys_sec = float(db_row[1] or 0)
                user_usec = float(db_row[2] or 0)
                sys_usec = float(db_row[3] or 0)
                db_cpu_sec = (user_sec + user_usec / 1_000_000) + (sys_sec + sys_usec / 1_000_000)

            # Compare
            if sacct_cpu_sec is not None and db_cpu_sec is not None:
                diff = sacct_cpu_sec - db_cpu_sec
                result = "MATCH" if abs(diff) < 1.0 else "MISMATCH"
            else:
                diff = None
                result = "N/A"

            sacct_str = f"{sacct_cpu_sec:>12.2f}" if sacct_cpu_sec is not None else f"{'N/A':>12}"
            db_str = f"{db_cpu_sec:>12.2f}" if db_cpu_sec is not None else f"{'N/A':>12}"
            diff_str = f"{diff:>+10.2f}" if diff is not None else f"{'N/A':>10}"
            out(f"  {pattern:<9}  {jid:<12}  {sacct_str}  {db_str}  {diff_str}  {result}")

cursor.close()
conn.close()
print(f"\nOutput saved to {OUTPUT_FILE}", file=sys.stderr)
