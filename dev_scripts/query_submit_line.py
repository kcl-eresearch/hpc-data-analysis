#!/usr/bin/env python3
"""Explore the submit_line column to detect interactive jobs and extract
--ntasks / --cpus-per-task from raw submission commands.

The submit_line column in create_job_table contains the raw submission command
(e.g. "sbatch script.sh", "srun --pty /bin/bash"). This lets us:
- Distinguish submission types (sbatch vs srun vs salloc)
- Detect interactive jobs via --pty (srun --pty pattern from KCL docs)
- Extract --ntasks and --cpus-per-task values

Data source: create_job_table (submit_line, cpus_req, tres_req columns)

Saves output to output_submit_line.txt
"""

import re
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
OUTPUT_FILE = SCRIPT_DIR / "output_submit_line.txt"

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

# Discover special step IDs dynamically (batch, interactive, etc.)
special_steps = discover_special_steps(cursor)
batch_id = special_steps.get('batch')
interactive_id = special_steps.get('interactive')

# Time range: Jan 2025
TIME_FILTER = """
    time_submit >= UNIX_TIMESTAMP('2025-01-01')
    AND time_submit < UNIX_TIMESTAMP('2025-02-01')
"""

with open(OUTPUT_FILE, 'w') as f:
    def out(text=""):
        print(text)
        print(text, file=f)

    # ================================================================
    # PART 1: Sample submit_line values
    # ================================================================
    out("=" * 80)
    out("PART 1: Sample submit_line values (Jan 2025)")
    out("=" * 80)
    out()

    # 10 jobs that have a batch step, 10 without
    out(f"--- 10 jobs WITH a batch step (id_step = {batch_id}) ---")
    cursor.execute(f"""
        SELECT j.id_job, j.submit_line
        FROM create_job_table j
        WHERE {TIME_FILTER}
          AND j.job_db_inx IN (
              SELECT DISTINCT s.job_db_inx FROM create_step_table s WHERE s.id_step = %s
          )
        ORDER BY RAND()
        LIMIT 10
    """, (batch_id,))
    for job_id, submit_line in cursor:
        out(f"  job {job_id}: {submit_line}")

    out()
    out("--- 10 jobs WITHOUT a batch step ---")
    cursor.execute(f"""
        SELECT j.id_job, j.submit_line
        FROM create_job_table j
        WHERE {TIME_FILTER}
          AND j.job_db_inx NOT IN (
              SELECT DISTINCT s.job_db_inx FROM create_step_table s WHERE s.id_step = %s
          )
        ORDER BY RAND()
        LIMIT 10
    """, (batch_id,))
    for job_id, submit_line in cursor:
        out(f"  job {job_id}: {submit_line}")

    # ================================================================
    # PART 2: Submission command distribution
    # ================================================================
    out()
    out("=" * 80)
    out("PART 2: Submission command distribution (Jan 2025)")
    out("=" * 80)
    out()

    cursor.execute(f"""
        SELECT submit_line
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND submit_line IS NOT NULL
          AND submit_line != ''
    """)
    command_counts = {}
    total_with_submit_line = 0
    for (submit_line,) in cursor:
        total_with_submit_line += 1
        # Extract first word (the command)
        first_word = submit_line.strip().split()[0] if submit_line and submit_line.strip() else "(empty)"
        # Normalize to basename in case of full path like /usr/bin/sbatch
        first_word = first_word.rsplit("/", 1)[-1]
        command_counts[first_word] = command_counts.get(first_word, 0) + 1

    # Also count NULLs / empty
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND (submit_line IS NULL OR submit_line = '')
    """)
    null_count = cursor.fetchone()[0]

    out(f"  Total jobs in Jan 2025: {total_with_submit_line + null_count}")
    out(f"  Jobs with submit_line: {total_with_submit_line}")
    out(f"  Jobs with NULL/empty submit_line: {null_count}")
    out()
    out(f"  {'command':<30}  {'count':>10}  {'%':>8}")
    out(f"  {'-' * 30}  {'-' * 10}  {'-' * 8}")
    for cmd, cnt in sorted(command_counts.items(), key=lambda x: -x[1]):
        pct = cnt / total_with_submit_line * 100 if total_with_submit_line else 0
        out(f"  {cmd:<30}  {cnt:>10}  {pct:>7.2f}%")

    # ================================================================
    # PART 3: Interactive job detection via submit_line
    # ================================================================
    out()
    out("=" * 80)
    out("PART 3: Interactive job detection via submit_line")
    out("=" * 80)
    out()

    # Count jobs with --pty
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND submit_line LIKE '%--pty%'
    """)
    pty_count = cursor.fetchone()[0]
    out(f"  Jobs with '--pty' in submit_line: {pty_count}")

    # Count jobs starting with srun (broader interactive indicator)
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND (submit_line LIKE 'srun %' OR submit_line LIKE '%/srun %')
    """)
    srun_count = cursor.fetchone()[0]
    out(f"  Jobs starting with 'srun': {srun_count}")

    # Sample --pty jobs
    out()
    out("  Sample submit_line values with '--pty':")
    cursor.execute(f"""
        SELECT id_job, submit_line
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND submit_line LIKE '%--pty%'
        ORDER BY RAND()
        LIMIT 20
    """)
    rows = list(cursor)
    if rows:
        for job_id, submit_line in rows:
            out(f"    job {job_id}: {submit_line}")
    else:
        out("    (none found)")

    # Cross-reference with step-based detection
    out()
    out(f"  Cross-reference: --pty jobs that also have interactive step (id_step = {interactive_id}):")
    cursor.execute(f"""
        SELECT j.id_job, j.submit_line
        FROM create_job_table j
        WHERE {TIME_FILTER}
          AND j.submit_line LIKE '%--pty%'
          AND j.job_db_inx IN (
              SELECT s.job_db_inx FROM create_step_table s WHERE s.id_step = %s
          )
    """, (interactive_id,))
    rows = list(cursor)
    out(f"    Count: {len(rows)}")
    for job_id, submit_line in rows:
        out(f"    job {job_id}: {submit_line}")

    out()
    out(f"  Cross-reference: --pty jobs that do NOT have interactive step (id_step = {interactive_id}):")
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM create_job_table j
        WHERE {TIME_FILTER}
          AND j.submit_line LIKE '%--pty%'
          AND j.job_db_inx NOT IN (
              SELECT s.job_db_inx FROM create_step_table s WHERE s.id_step = %s
          )
    """, (interactive_id,))
    out(f"    Count: {cursor.fetchone()[0]}")

    # ================================================================
    # PART 4: --ntasks extraction
    # ================================================================
    out()
    out("=" * 80)
    out("PART 4: --ntasks extraction from submit_line")
    out("=" * 80)
    out()

    # Count jobs with --ntasks or -n
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND (submit_line LIKE '%--ntasks%' OR submit_line REGEXP ' -n [0-9]')
    """)
    ntasks_count = cursor.fetchone()[0]
    out(f"  Jobs with '--ntasks' or '-n <num>' in submit_line: {ntasks_count}")

    # Sample values to understand formatting
    out()
    out("  Sample submit_line values with '--ntasks':")
    cursor.execute(f"""
        SELECT id_job, submit_line
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND submit_line LIKE '%--ntasks%'
        ORDER BY RAND()
        LIMIT 15
    """)
    for job_id, submit_line in cursor:
        out(f"    job {job_id}: {submit_line}")

    out()
    out("  Sample submit_line values with '-n <num>' (short form):")
    cursor.execute(f"""
        SELECT id_job, submit_line
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND submit_line REGEXP ' -n [0-9]'
          AND submit_line NOT LIKE '%--ntasks%'
        ORDER BY RAND()
        LIMIT 15
    """)
    for job_id, submit_line in cursor:
        out(f"    job {job_id}: {submit_line}")

    # Distribution of ntasks values (parse from submit_line)
    out()
    out("  Distribution of --ntasks values (parsed from submit_line):")
    cursor.execute(f"""
        SELECT submit_line
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND (submit_line LIKE '%--ntasks%' OR submit_line REGEXP ' -n [0-9]')
    """)
    ntasks_values = {}
    for (submit_line,) in cursor:
        # Try --ntasks=N or --ntasks N
        m = re.search(r'--ntasks[= ]+(\d+)', submit_line)
        if not m:
            # Try -n N (but not inside another flag like -name)
            m = re.search(r' -n (\d+)', submit_line)
        if m:
            val = int(m.group(1))
            ntasks_values[val] = ntasks_values.get(val, 0) + 1

    out(f"  {'ntasks value':>15}  {'count':>10}")
    out(f"  {'-' * 15}  {'-' * 10}")
    for val, cnt in sorted(ntasks_values.items(), key=lambda x: -x[1])[:20]:
        out(f"  {val:>15}  {cnt:>10}")

    # ================================================================
    # PART 5: --cpus-per-task extraction
    # ================================================================
    out()
    out("=" * 80)
    out("PART 5: --cpus-per-task extraction from submit_line")
    out("=" * 80)
    out()

    # Count jobs with --cpus-per-task or -c
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND (submit_line LIKE '%--cpus-per-task%' OR submit_line REGEXP ' -c [0-9]')
    """)
    cpt_count = cursor.fetchone()[0]
    out(f"  Jobs with '--cpus-per-task' or '-c <num>' in submit_line: {cpt_count}")

    # Sample values
    out()
    out("  Sample submit_line values with '--cpus-per-task':")
    cursor.execute(f"""
        SELECT id_job, submit_line
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND submit_line LIKE '%--cpus-per-task%'
        ORDER BY RAND()
        LIMIT 15
    """)
    for job_id, submit_line in cursor:
        out(f"    job {job_id}: {submit_line}")

    out()
    out("  Sample submit_line values with '-c <num>' (short form):")
    cursor.execute(f"""
        SELECT id_job, submit_line
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND submit_line REGEXP ' -c [0-9]'
          AND submit_line NOT LIKE '%--cpus-per-task%'
        ORDER BY RAND()
        LIMIT 15
    """)
    for job_id, submit_line in cursor:
        out(f"    job {job_id}: {submit_line}")

    # Distribution of cpus-per-task values
    out()
    out("  Distribution of --cpus-per-task values (parsed from submit_line):")
    cursor.execute(f"""
        SELECT submit_line
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND (submit_line LIKE '%--cpus-per-task%' OR submit_line REGEXP ' -c [0-9]')
    """)
    cpt_values = {}
    for (submit_line,) in cursor:
        m = re.search(r'--cpus-per-task[= ]+(\d+)', submit_line)
        if not m:
            m = re.search(r' -c (\d+)', submit_line)
        if m:
            val = int(m.group(1))
            cpt_values[val] = cpt_values.get(val, 0) + 1

    out(f"  {'cpus-per-task':>15}  {'count':>10}")
    out(f"  {'-' * 15}  {'-' * 10}")
    for val, cnt in sorted(cpt_values.items(), key=lambda x: -x[1])[:20]:
        out(f"  {val:>15}  {cnt:>10}")

    # ================================================================
    # PART 6: Cross-tabulation
    # ================================================================
    out()
    out("=" * 80)
    out("PART 6: Cross-tabulation (command x --ntasks x --cpus-per-task)")
    out("=" * 80)
    out()

    cursor.execute(f"""
        SELECT submit_line
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND submit_line IS NOT NULL
          AND submit_line != ''
    """)
    cross_tab = {}  # (command, has_ntasks, has_cpt) -> count
    for (submit_line,) in cursor:
        first_word = submit_line.strip().split()[0] if submit_line and submit_line.strip() else "(empty)"
        first_word = first_word.rsplit("/", 1)[-1]

        has_ntasks = bool(
            re.search(r'--ntasks', submit_line)
            or re.search(r' -n \d', submit_line)
        )
        has_cpt = bool(
            re.search(r'--cpus-per-task', submit_line)
            or re.search(r' -c \d', submit_line)
        )

        key = (first_word, has_ntasks, has_cpt)
        cross_tab[key] = cross_tab.get(key, 0) + 1

    out(f"  {'command':<15}  {'--ntasks':<10}  {'--cpus-per-task':<17}  {'count':>10}")
    out(f"  {'-' * 15}  {'-' * 10}  {'-' * 17}  {'-' * 10}")
    for (cmd, has_nt, has_cpt), cnt in sorted(cross_tab.items(), key=lambda x: (-x[1])):
        nt_str = "yes" if has_nt else "no"
        cpt_str = "yes" if has_cpt else "no"
        out(f"  {cmd:<15}  {nt_str:<10}  {cpt_str:<17}  {cnt:>10}")

    # Summary
    out()
    total_jobs = sum(cross_tab.values())
    has_neither = sum(v for (_, nt, cpt), v in cross_tab.items() if not nt and not cpt)
    has_ntasks_only = sum(v for (_, nt, cpt), v in cross_tab.items() if nt and not cpt)
    has_cpt_only = sum(v for (_, nt, cpt), v in cross_tab.items() if not nt and cpt)
    has_both = sum(v for (_, nt, cpt), v in cross_tab.items() if nt and cpt)
    out(f"  Summary:")
    out(f"    Neither --ntasks nor --cpus-per-task: {has_neither:>8} ({has_neither/total_jobs*100:.1f}%)")
    out(f"    --ntasks only:                        {has_ntasks_only:>8} ({has_ntasks_only/total_jobs*100:.1f}%)")
    out(f"    --cpus-per-task only:                  {has_cpt_only:>8} ({has_cpt_only/total_jobs*100:.1f}%)")
    out(f"    Both:                                  {has_both:>8} ({has_both/total_jobs*100:.1f}%)")

    # ================================================================
    # PART 7: Comparison with existing structured fields
    # ================================================================
    out()
    out("=" * 80)
    out("PART 7: Comparison with existing fields (cpus_req, tres_req)")
    out("=" * 80)
    out()

    # For jobs with --ntasks in submit_line: compare parsed value to cpus_req
    out("--- Jobs with --ntasks in submit_line vs cpus_req ---")
    cursor.execute(f"""
        SELECT id_job, submit_line, cpus_req, tres_req
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND (submit_line LIKE '%--ntasks%' OR submit_line REGEXP ' -n [0-9]')
        LIMIT 500
    """)
    rows = list(cursor)

    match_count = 0
    mismatch_count = 0
    parse_fail = 0
    sample_mismatches = []

    for job_id, submit_line, cpus_req, tres_req in rows:
        m = re.search(r'--ntasks[= ]+(\d+)', submit_line)
        if not m:
            m = re.search(r' -n (\d+)', submit_line)
        if m:
            parsed_ntasks = int(m.group(1))
            if parsed_ntasks == cpus_req:
                match_count += 1
            else:
                mismatch_count += 1
                if len(sample_mismatches) < 15:
                    sample_mismatches.append((job_id, submit_line, parsed_ntasks, cpus_req, tres_req))
        else:
            parse_fail += 1

    out(f"  Total sampled: {len(rows)}")
    out(f"  parsed_ntasks == cpus_req: {match_count}")
    out(f"  parsed_ntasks != cpus_req: {mismatch_count}")
    out(f"  Parse failures: {parse_fail}")
    out()
    if sample_mismatches:
        out("  Sample mismatches (ntasks vs cpus_req):")
        out(f"    {'job':>10}  {'ntasks':>7}  {'cpus_req':>9}  tres_req / submit_line")
        for job_id, submit_line, parsed_ntasks, cpus_req, tres_req in sample_mismatches:
            out(f"    {job_id:>10}  {parsed_ntasks:>7}  {cpus_req:>9}  tres_req={tres_req}")
            out(f"    {'':>10}  {'':>7}  {'':>9}  submit_line={submit_line}")

    # For jobs with --cpus-per-task: compare to cpus_req
    out()
    out("--- Jobs with --cpus-per-task in submit_line vs cpus_req ---")
    cursor.execute(f"""
        SELECT id_job, submit_line, cpus_req, tres_req
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND (submit_line LIKE '%--cpus-per-task%' OR submit_line REGEXP ' -c [0-9]')
        LIMIT 500
    """)
    rows = list(cursor)

    match_count = 0
    mismatch_count = 0
    parse_fail = 0
    sample_mismatches = []

    for job_id, submit_line, cpus_req, tres_req in rows:
        m = re.search(r'--cpus-per-task[= ]+(\d+)', submit_line)
        if not m:
            m = re.search(r' -c (\d+)', submit_line)
        if m:
            parsed_cpt = int(m.group(1))
            if parsed_cpt == cpus_req:
                match_count += 1
            else:
                mismatch_count += 1
                if len(sample_mismatches) < 15:
                    sample_mismatches.append((job_id, submit_line, parsed_cpt, cpus_req, tres_req))
        else:
            parse_fail += 1

    out(f"  Total sampled: {len(rows)}")
    out(f"  parsed_cpus_per_task == cpus_req: {match_count}")
    out(f"  parsed_cpus_per_task != cpus_req: {mismatch_count}")
    out(f"  Parse failures: {parse_fail}")
    out()
    if sample_mismatches:
        out("  Sample mismatches (cpus-per-task vs cpus_req):")
        out(f"    {'job':>10}  {'cpt':>7}  {'cpus_req':>9}  tres_req / submit_line")
        for job_id, submit_line, parsed_cpt, cpus_req, tres_req in sample_mismatches:
            out(f"    {job_id:>10}  {parsed_cpt:>7}  {cpus_req:>9}  tres_req={tres_req}")
            out(f"    {'':>10}  {'':>7}  {'':>9}  submit_line={submit_line}")

    # Extra: for --ntasks jobs, also check ntasks * cpus-per-task relationship
    out()
    out("--- Jobs with BOTH --ntasks and --cpus-per-task: ntasks*cpt vs cpus_req ---")
    cursor.execute(f"""
        SELECT id_job, submit_line, cpus_req, tres_req
        FROM create_job_table
        WHERE {TIME_FILTER}
          AND (submit_line LIKE '%--ntasks%' OR submit_line REGEXP ' -n [0-9]')
          AND (submit_line LIKE '%--cpus-per-task%' OR submit_line REGEXP ' -c [0-9]')
        LIMIT 500
    """)
    rows = list(cursor)
    out(f"  Jobs with both flags: {len(rows)}")

    match_product = 0
    mismatch_product = 0
    sample_products = []
    for job_id, submit_line, cpus_req, tres_req in rows:
        m_nt = re.search(r'--ntasks[= ]+(\d+)', submit_line) or re.search(r' -n (\d+)', submit_line)
        m_cpt = re.search(r'--cpus-per-task[= ]+(\d+)', submit_line) or re.search(r' -c (\d+)', submit_line)
        if m_nt and m_cpt:
            nt = int(m_nt.group(1))
            cpt = int(m_cpt.group(1))
            product = nt * cpt
            if product == cpus_req:
                match_product += 1
            else:
                mismatch_product += 1
                if len(sample_products) < 10:
                    sample_products.append((job_id, nt, cpt, product, cpus_req, tres_req))

    out(f"  ntasks * cpus-per-task == cpus_req: {match_product}")
    out(f"  ntasks * cpus-per-task != cpus_req: {mismatch_product}")
    if sample_products:
        out()
        out(f"    {'job':>10}  {'nt':>5}  {'cpt':>5}  {'nt*cpt':>7}  {'cpus_req':>9}  tres_req")
        for job_id, nt, cpt, product, cpus_req, tres_req in sample_products:
            out(f"    {job_id:>10}  {nt:>5}  {cpt:>5}  {product:>7}  {cpus_req:>9}  {tres_req}")

cursor.close()
conn.close()
print(f"\nOutput saved to {OUTPUT_FILE}", file=sys.stderr)
