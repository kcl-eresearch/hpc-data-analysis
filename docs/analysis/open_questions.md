# Open Questions & Uncertainties

This document records the open questions, partially-resolved puzzles, and analysis decisions that came up while analysing the CREATE HPC cluster's Slurm accounting data. It is a durable companion to the code: where an aspect of the analysis is still unsolved, a result rests on an assumption, an unverified inference, or a deliberate methodological choice, it is written down here.

Items still marked **Open**, **Partially open** or **External action** are candidates for GitHub issues; this document is the narrative record behind them.

## Status taxonomy

| Status | Meaning |
|--------|---------|
| **Resolved** | Understood and confirmed; the code/analysis handles it correctly. |
| **Design decision** | Not a bug or unknown — a deliberate methodological choice, recorded so the rationale isn't lost. |
| **Understood** | A settled explanation or background fact, not an open problem. |
| **Partially open** | Largely explained, with a specific residual that is not understood. |
| **Open** | Genuinely unresolved; needs more investigation. |
| **External action** | Resolved on our side, but the fix/output is a change someone else owns (e.g. KCL CREATE docs). |

## Two cross-cutting root causes

Several issues below share one of two underlying mechanisms.
They are stated once here and referenced throughout.

**A note on the variables used here and throughout**: `cpus_req`, `tres_req`, and
`tres_alloc` are columns of the Slurm accounting database's `create_job_table`.
`cpus_req` is a plain integer — the CPUs the user requested. `tres_req` and
`tres_alloc` are TRES-encoded strings — comma-separated `ID=value` pairs (e.g.
`1=8,2=8000`, where TRES ID 1 = CPU and ID 2 = memory) — holding, respectively,
what was *requested* and what Slurm *allocated*. `alloc_cpus` is **not** a
column in the database: it is the CPU value (ID 1) parsed out of the `tres_alloc` string in code.
(TRES = Slurm's "Trackable RESources"; see the developer docs on TRES encoding.)

### Root cause A — core-level allocation on hyperthreaded nodes

CREATE nodes are hyperthreaded (2 hardware threads per core), and a 1-CPU
request ends up consuming a whole core = 2 logical CPUs, so the number of allocated CPUs can
exceed the number of requested CPUs.

The governing setting is `SelectTypeParameters=CR_CORE_MEMORY` (whole-core
allocation with memory enforcement, live config since February 2026) which can be checked using `scontrol show config | grep -i selecttype`. 
Pre-memory-enforcement config was `CR_Core` (without the `_Memory` option which makes memory consumable — see root cause B), so whole-core rounding applies across all periods, including the Jul–Dec 2025 blog data.

This single mechanism is the root of the ~1.7M jobs where allocated > requested CPU (issue #1, from an all-time diagnostic over ~30.7M jobs); part of the CPU-efficiency >100% artefact (#2); and a narrow subset of memory efficiencies exceeding >100% when `--mem-per-cpu` was used in the job submission, as shown in a post-memory-enforcement analysis (Feb 2026) — 1,415 of the 1,550 jobs that exceeded 100% on *requested* memory there (out of ~481k computable jobs in that window), because `--mem-per-cpu` scales the memory limit with the rounded-up CPU count (#7).

Empirical backing (`query_cpu_mem_diagnostics.py`): `cpus_req` vs the CPU value in `tres_req` match for 99.999% of jobs (only 323 of ~30.7M differ), but `cpus_req` vs `alloc_cpus` (derived from `tres_alloc`) differ for ~1.68M jobs, dominated by the `cpus_req=1, alloc_cpus=2` pattern.

### Root cause B — memory was not a consumable resource before Feb 2026

Before February 2026, the cluster scheduled with `CR_Core`
without the `_Memory` option, so memory was not tracked as a consumable
resource (the change at enforcement was `CR_Core` → `CR_Core_Memory`). Per the
[Slurm docs](https://slurm.schedmd.com/slurm.conf.html): when memory is not consumable, it can be
oversubscribed and is not constrained by task/cgroup, and `--mem` is used only
to filter nodes (see #6). This is the root of the absent `tres_alloc` memory
before Feb 2026 (#6), and how absurd >1 TiB requests ran with zero OOM kills
(#8). Memory enforcement was enabled at the end of January 2026.

## Summary

| # | Issue | Status | Impact on results |
|---|-------|--------|-------------------|
| 1 | Allocated > requested CPUs | Resolved | None — explained by root cause A |
| 2 | CPU efficiency > 100% | Partially open | ~3% of efficiencies; residual unexplained |
| 3 | Requested vs allocated CPUs for efficiency | Design decision | Two sets of results reported by purpose |
| 4 | Multi-node jobs: CPU-time undercount | Open | Small; ~0.9% of jobs, multi-node CPU time understated |
| 5 | Multi-step jobs: CPU-time summation | Open | Small; batch-vs-regular double-counting risk |
| 6 | Memory handling before enforcement (pre-Feb 2026) | Understood | Frames all pre-Feb-2026 memory analysis |
| 7 | Memory efficiency > 100% after enforcement | Partially open | 171 jobs (0.04%); 101 unexplained |
| 8 | Extreme memory requests (>1 TiB) | Partially open | Distorts request plots; ~13 users |
| 9 | Interactive job detection | Resolved | 0.4% interactive vs 99.6% batch |
| 10 | Multi-threaded request docs (`--ntasks` vs `--cpus-per-task`) | External action | CREATE docs amendment |
| 11 | Job efficiency ↔ carbon framing | Partially open | Shapes the blog-post narrative |
| 12 | Analysis runtime is flat across date ranges | Open (cause identified) | Both tools take ~50 min regardless of range |

---

## CPU

### 1. Allocated CPUs exceed requested CPUs

- **Status:** Resolved (with a very minor open question).
- **Affects:** ~1.7M jobs (5.5%) of ~30.7M jobs in the database.
- **What we found:** For a large minority of jobs, `alloc_cpus` is greater than `cpus_req` / the CPU value in `tres_req` — most often 1 requested, 2 allocated. 
This is not caused by multi-threading (which is invisible to Slurm).
It is hardware allocation granularity: whole physical cores are allocated, and on hyperthreaded nodes one core = 2 logical CPUs (root cause A).
- **How the code handles it:** Both `cpus_req` (parsed from `tres_req`) and `alloc_cpus` (parsed from `tres_alloc`) are computed and carried through, so efficiency can be expressed against either denominator (see #3).
- **What's still open:** Nothing significant. 
The 323 jobs where `cpus_req` itself disagrees with the `tres_req` CPU value are unexplained edge cases, but at 0.001% of all jobs, they do not change the main results, so worth digging into only if nothing else has higher priority.
- **References:** `query_cpu_mem_diagnostics.py` (Part 1); root cause A.

### 2. CPU efficiency exceeds 100%

- **Status:** Partially open.
- **Affects:** ~97k (~3.4%) of ~2.9M efficiency-eligible jobs (status (COMPLETED/TIMEOUT/OOM, in a given time window).
- **What we found:** Some jobs show CPU efficiency above 100% — i.e. more CPU time used than `time elapsed × CPUs`.
  - **Using `cpus_req` inflates efficiencies** (root cause A): Whole-core rounding can give the job more CPUs than it asked for (e.g. requested 1, allocated 2) and its (multi-threaded) code uses them. Results will then be inflated if using `cpus_req` in the efficiency calculation.
  Recomputing against `alloc_cpus` brings these jobs to ~100%.
    - Threads are "invisible" to Slurm, but it doesn't allocate CPUs based on thread count; the `cgroup` still pins the whole job to its allocated cores (see next bullet point).
    - CPU limits *are* enforced on CREATE: inspecting the cluster's `cgroup` config confirmed `ConstrainCores=yes`.
    That is what makes the residual below genuinely puzzling.
- **What's still open:** 34,420 efficiencies (1.2% of valid jobs) still exceed 100% even when computed against `alloc_cpus` — down from 97,342 (3.4%) when computed against `cpus_req`, but still present (user notebook, "Global Summary", cell 41). These are genuinely puzzling: almost all of them (34,399) are jobs where `req_cpus == alloc_cpus`, so the whole-core-rounding explanation cannot apply, yet they still exceed 100%. Because `ConstrainCores` is enforced, this is unexpected.
The cause is unknown — candidates include:
  - Grace period on timeout: A job hitting its time limit is
    given a short grace period before being killed, which could push CPU time slightly over 100% on jobs in a killed/failed state.
    Not yet checked against the data.
  - Multi-node CPU-time accounting (see #4).
  - Measurement artefacts.
  - A Slurm config/mechanism not yet identified.
- **Impact on results:** The portion of jobs with >100% efficiency was small enough to be excluded from the analysis/plots in the blog post notebook (documented in the blog-post appendix).
- **Next steps:** Characterise the 34,420 residual jobs against their state distribution (tests the grace-period hypothesis), their node count (tests multi-node CPU accounting, #4), and any partition or user concentration to discriminate between candidate causes.
- **References:** user notebook (efficiency violin plots); root cause A;
  cgroup.conf inspection.

### 3. Requested vs allocated CPUs

- **Status:** Design decision (not open).
- **What we found:** CPU efficiency can be computed against requested CPUs
  (`cpu_eff_req`) or allocated CPUs (`cpu_eff_alloc`). 
  Neither is "wrong" — they answer different questions, so both are produced and reported.
- **The rationale:**
  - **Requested CPUs → user behaviour.** "Did the user request more than they needed?" The fairer denominator for *user education*, because a user can't control that Slurm rounded their 1-CPU request up to a whole core (root cause A).
  This is the lens of the user-perspective and blog post notebook.
  - **Allocated CPUs → cluster utilisation.** "How much of the reserved hardware was actually used?" 
  The relevant denominator for *infrastructure planning*, and it corrects the cases where efficiency against `cpus_req` is misleadingly high because more was allocated than requested (root cause A).
  This is the lens of the infrastructure notebook.
- **Caveat to record:** When `cpus_req == alloc_cpus`, the two cannot be
  distinguished, so you cannot tell granularity rounding apart from genuine under-requesting from this comparison alone.
  Also note that the expectation "allocated-CPU efficiency ≤ ~100%" does **not** fully hold — that residual is tracked in #2, not here.
- **References:** README "Weighted vs average efficiency"; root cause A; #2.

### 4. Multi-node jobs: CPU-time undercount

- **Status:** Open.
- **Affects:** ~27k (0.9%) of ~2.9M jobs (blog post data) are multi-node, and within those, a small fraction is genuinely distributed (e.g., uses MPI).
- **What we found**: A job can run on several *nodes* and have several *steps* (for the step structure see #5).
  - There are **two ways CPU time is recorded per step**:
    - **`rusage` columns** (`user_sec`, `sys_sec`, and the microsecond parts
    `user_usec`, `sys_usec`): When a program runs, the OS records how much
    CPU time its processes used, split into *user* CPU time (running the
    program's own code) and *system* CPU time (the kernel working on the
    program's behalf — file I/O, memory allocation, networking).
    `getrusage()` and `wait4()` are standard Unix system calls that report a finished process's resource usage;
    Slurm calls them and stores the result as seconds + microseconds. Total step CPU time =
    `user_sec + sys_sec + (user_usec + sys_usec) / 1e6`.
      - **Limitation** (inferred, not exhaustively verified): These calls appear to capture only processes reaped on the node where the step's launcher ran (the head node), so for genuinely distributed steps (e.g., using MPI) the remote-node CPU time is missed.
      This is our own reading rather than something stated in official Slurm docs.
      It rests on two things: how `getrusage` works (it counts only the processes the calling process waited on locally, i.e. on the head node), and a pattern we see in the diagnostics — in multi-node MPI jobs, the `orted` steps show `user_sec = 0` while their TRES CPU time value is non-zero, i.e. the work clearly ran (TRES counted it) but the head-node's `rusage` column recorded none of it (`query_tres_usage_vs_rusage.py` PART 2).
        - `orted` is Open MPI's per-node helper daemon that launches and manages the job's processes on each node, so its presence marks a multi-node MPI job.
    - **TRES data** (`tres_usage_in_max`, TRES ID 1 = CPU): Comes from `cgroup` accounting and can include processes on remote nodes.
      - The `cgroup` groups a set of processes and tracks their resource use. Slurm places a job/job step into a `cgroup` on every node it runs on and reads each node's CPU counter, so `tres_usage_in_max` can reflect CPU used on the remote nodes too.
      (For a single-node job there are no remote nodes, so the two sources do agree in value; see also next bullet point.)
      - **Units of TRES CPU time**: `query_tres_usage_vs_rusage.py` PART 1 compares `user_sec+sys_sec` against `tres_usage_in_max` CPU time for single-node batch steps, and the ratio is consistently ~1000 (average 1000.14 across 20 jobs), confirming that TRES CPU time is in *milliseconds*, not seconds (as is the case for `rusage`).
  - **Single node vs multiple nodes:** Most jobs run entirely on one node, including multi-CPU jobs: requesting several CPUs (e.g. `--cpus-per-task=4`) normally places all those cores on a single node, where the `rusage` columns capture all the CPU time correctly.
  The undercounting only matters for the minority of jobs that genuinely span *multiple* nodes — e.g. an MPI job or `srun --nodes=4`, where one step launches processes across several nodes at once and `rusage` appears to record only the local (head-node) share (see the limitation above).
  (This is about cores spread across separate *machines*; the placement of cores *within* a single node — NUMA locality — is a separate, performance-only concern covered in #10.)
- **What's still open:** The TRES value would capture the remote-node CPU and is the potential fix — but it's not clear whether it's worth doing for the ~0.9% of jobs affected. It would involve: converting milliseconds to seconds, confirming `tres_usage_in_max` CPU time is the cumulative *total* (not a peak — cf. `tres_usage_in_tot`) and aggregates correctly across multiple nodes/steps, and checking that mixing sources (`rusage` for single-node, TRES for multi-node) stays consistent.
- **How the code currently handles it:** The code uses `rusage` (head-node only) and not the TRES value, hence multi-node jobs are *undercounted*: the distributed CPU time on remote nodes is missed and nothing compensates, so their CPU efficiency is understated.
- **Impact on results:** small — the multi-node undercount affects only the ~0.9% of jobs that span multiple nodes, so the affected population is tiny; but the mechanism is not fully understood.
- **References:** `query_tres_usage_vs_rusage.py`; #2.

### 5. Multi-step jobs: CPU-time summation

- **Status:** Open.
- **Affects:** ~290k (~1%) of the ~30.7M all-time jobs have more than one step.
- **What we found**: A job can have several *steps* in `create_step_table`.
  - **Single step vs multiple steps:** A *step* is a unit of execution within a job: every batch job has a *batch step* (`id_step=-5`, the script itself), and each `srun` call inside the script adds a *regular step* (`id_step≥0`).
  A single-step job has only the batch step, which then holds all its CPU time; a multi-step job has the batch step plus one or more regular steps, where the regular steps do the real work and the batch step is usually just overhead.
  The vast majority are single-step.
- **What's still open:**
  - **What the batch step's CPU represents.** An `sbatch` job has a batch step (`id_step=-5`); if its script calls `srun` it also has regular steps (`id_step≥0`).
  Most multi-step jobs have a tiny batch-step CPU (0–2 s, just script overhead), but the diagnostics show some with batch-step CPU roughly *equal* to the regular-step CPU (ratio ~1.00×) and others where it is ~0 --> Is the batch CPU *additional* to the regular steps (genuinely separate work: the script plus launching `srun`), or does it *overlap/duplicate* them (so summing both would double-count)?
  And why ~0 for some jobs but ~equal for others?
- **How the code currently handles it:** `fetch_job_data()` sums the **regular** steps' CPU and falls back to the batch step only when there are no regular steps — so it never adds batch + regular, avoiding potential double-counting in the multi-step case.
- **Impact on results:** small — only multi-step jobs with substantial batch-step CPU are at risk of mis-summation, a tiny subset; in the common case the batch step is negligible overhead, so the effect on totals is minimal.
- **References:** `query_step_diagnostics.py`.

---

## Memory

### 6. How memory was handled before enforcement (pre-Feb 2026)

- **Status:** Understood (see root cause B).
- **Summary:** 
- **What we found:** `tres_alloc` had no memory value (TRES ID = 2) for jobs before Feb 2026; from Feb 2026 it is present and can differ from requested memory. 
Before that, memory was not reserved per job: Slurm used `--mem` only to choose where to place a job — it would run on any node whose *total* RAM was ≥ `--mem` — but it set no memory aside for the job and did not stop other jobs using the same RAM.
So memory could be oversubscribed: two jobs could land on the same node and each "use" all of its RAM, and over-large requests ran without ever being killed (which is why the absurd >1 TiB requests had zero OOM kills — see #8).
- **Impact on results:** frames all pre-Feb-2026 memory analysis — requested memory is meaningful, but "allocated memory" doesn't exist and memory was never enforced, so memory efficiency >100% was both possible and harmless then.
- **References:** root cause B; #7; #8.

### 7. Memory efficiency exceeds 100% after enforcement (Feb 2026 data)

- **Status:** Partially open.
- **Affects:**: 1,550 (0.3%) Of ~481k efficiency-eligible jobs in the Feb 2026 post-memory-enforcement data.
- **What we found:** Of the 1,550 jobs >100% against *requested* memory,
  1,415 are an accounting artefact: they are `--mem-per-cpu` jobs where Slurm allocated more CPUs than requested (root cause A), so the memory limit — which scales with CPUs — was raised above the request, and `cgroup` enforced the larger *allocated* limit.
  Recomputing against *allocated* memory removes these, dropping the count from 1,550 to 171.
- **What's still open:** Of the remaining 171, the largest group (101) are
  `--mem` (per-node) jobs where requested and allocated memory are identical, yet the job used more than the `cgroup` should have allowed.
  Cause unclear.
  - **Suggestions to act on:**
    - Have the notebook report a handful of job IDs for the anomalous group so ops/infra can investigate specific jobs;
    - Check whether those jobs were OOM-killed, which would be consistent with exceeding memory;
    - Check the concentration of faculty "unknown" / whether they come from a single user or a special job type.
    - More generally, add a standard anomaly-overview plot set whenever an
    anomalous group is flagged: distributions of requested CPUs, requested
    memory, and run time, plus bar plots of job states and faculties.
- **References:** user notebook §4.4 (comparison plots and breakdown tables for the >100% cases, against both requested and allocated memory); root cause A; root cause B.

### 8. Extreme memory requests (>1 TiB)

- **Status:** Partially open (one sub-question open).
- **Affects:** ~37k jobs (~1.3%) of the ~2.9M efficiency-eligible jobs requested >1 TiB; concentrated in ~13 users.
- **What we found:** 99.5% of >1 TiB requests use `--mem-per-cpu` (37,272 of 37,429; only 157 use `--mem`). The dominant pattern is a single user submitting ~36,000 array jobs at 150 GiB **per CPU** × 100 CPUs = 15,000 GiB total — almost certainly meaning `--mem=150 GiB` rather than `--mem-per-cpu`. 
Just 13 users account for all >1 TiB requests, and their median *actual* usage is < 1 GiB.
Example job IDs:
  - `28184209` — 2,200 GiB/CPU × 250 CPUs = 550 TiB requested, 40.8 GiB used
  - `28525244` — 150 GiB/CPU × 100 CPUs = 15 TiB requested, 0.9 GiB used
  - `27321885` — 200 GiB/CPU × 24 CPUs = 4.8 TiB requested, 31.0 GiB used
  - For scale: There are nodes with 2,200 GiB RAM and 250 CPUs, but not 2,200 GiB *per CPU*.
- **What's still open:** How does Slurm handle an *impossible* request? Given root cause B (memory not consumable before enforcement), it appears `--mem-per-cpu` totals were effectively ignored for placement and only `--mem` filtered nodes — which is why these jobs ran on nodes far smaller than their nominal totals.
Whether `--mem-per-cpu` is *entirely* ignored when memory is not consumable is not confirmed in the Slurm docs.
- **Impact on results:** Small — only ~1.3% of 2.9M jobs, affecting no efficiency conclusion.
Their one visible effect is on the requested-memory distribution plots, where a few extreme values skew the scale and inflate the mean.
- **References:** user notebook §4.6; root cause B; #6.

---

## Job classification

### 9. Interactive job detection

- **Status:** Resolved.
- **Affects:** classification of all jobs as interactive vs batch.
- **What we found:** 
  - Looking for an "interactive" job step (`id_step=-6`) — found almost no interactive jobs (2 in ~30M), which is implausible.
  - That `-6` step is only created for sessions started with `salloc` when the cluster has `LaunchParameters=use_interactive_step` set — a path essentially unused on CREATE (the 2 jobs found are presumably those rare exceptions).
  CREATE users start interactive sessions with `srun --pty /bin/bash`, which does not create a `-6` step, so the step-based method misses essentially all of them.
  - **Resolution:** detect interactive jobs by parsing the `submit_line` column in `create_job_table` for the `--pty` flag. Result: ~11k interactive jobs (0.4%) vs ~2.9M (99.6%) — plausible, since interactive use is mostly training and most work uses `sbatch`.
- **How the code handles it:** `detect_interactive_from_submit_line()` in
  `slurm_utils.py`; breakdown in the user notebook §4.4 ("Submit Line Analysis").
- **References:** user notebook §4.4; `query_submit_line.py`.

---

## External actions (KCL CREATE documentation)

### 10. Multi-threaded resource requests: `--ntasks` vs `--cpus-per-task`

- **Status:** External action (understanding resolved; doc change needed).
- **What we found:** The CREATE docs recommend `--ntasks` for requesting cores for multi-threaded jobs and don't mention `--cpus-per-task`.
This is the wrong abstraction for the common case (single process, multiple threads).
  - **The correct model:**
    - `--ntasks` (or `--ntasks-per-node`) sets the number of *processes* (task slots); `--cpus-per-task` gives *one process multiple CPUs*.
    - Both reserve the same number of CPUs, but for a plain `sbatch` script with no `srun`, the script always runs as a single process regardless of `--ntasks` — so `--ntasks=4` effectively just means "give me 4 CPUs," and the "4 separate task slots" never materialise as processes.
    The distinction only matters under `srun`/MPI, where you genuinely want multiple processes.
    - For multi-threaded single-process code the real difference is CPU
    placement: `--cpus-per-task=4` keeps the cores contiguous within one NUMA domain (e.g. affinity `0–3`), good for threads that share memory, while `--ntasks=4` scatters them across NUMA domains (e.g. `0,1,64,65`) and needs a `--nodes=1` workaround to stop tasks spreading across nodes.
    - **NUMA** (Non-Uniform Memory Access) is a property *within* a single node: a server is divided into NUMA domains, each a group of cores with its own attached memory bank, and a core reaches its own domain's memory faster than another domain's. So even on one node, *where* the cores sit affects performance — this is distinct from the cross-node accounting concern in #4.
  - **Correct guidance for that common case — one multi-threaded process on a single node:** `#SBATCH --nodes=1` + `#SBATCH --cpus-per-task=N` (N = number of threads).
- **Next steps** (Stuart's suggestions): Amend the basic running-jobs page; extend the MPI page (`running_jobs_mpi/#mpi-examples`) with an MP-threads-vs-MPI-ranks example in C; add a note on `torchrun` and how it differs in thread/GPU spawning.
- **References:** Feb 2026 (multi-threaded job requests).

---

## Sustainability framing

### 11. Does job efficiency actually reduce carbon?

- **Status:** Partially open (framing decided; data gaps open).
- **Summary:** 
- **What we found/concluded:** We had a discussion on whether improving job efficiency yields a real CO₂ reduction (as "green computing" might suggest), and how to frame this honestly in the blog post. 
Clarified that job efficiency does *not* directly save energy.
A core reserved-but-idle draws the same power as an unreserved idle core, and distributing the same work over more cores uses roughly the same total energy.
The genuine sustainability links are:
  - **Embodied carbon.** Archer2 data splits an HPC job's emissions ~50:50 between electricity generation (scope 2) and hardware manufacture (scope 3), so running more jobs on the same hardware lowers per-job embodied carbon and reduces the pressure to buy new hardware.
  - **Scheduling efficiency / fairness.** Right-sizing lets more jobs pack onto the same nodes, cutting queue times and getting more research done per unit of cluster capacity.
  Carbon-aware scheduling (running when the grid is greener), hardware/cooling efficiency (PUE), and "green coding" (avoiding unnecessary computation) are separate concerns, not what this analysis is about.
- **Open data gaps** (record for future work):
  - **No node power-draw data** (idle vs full load): Simulating full load has proven hard; Slurm energy monitoring was attempted. PDUs may track power but not at node level, and wall-power never matches reported draw (temperature, PSU rating, speedstep/boost on low-core workloads).
  - **Node power-down is configured but mostly disabled:**
    `SuspendProgram`/`ResumeProgram` (`/opt/create/slurm_*_nodes.py`),
    `SuspendTime`/`SuspendTimeout` exist in `slurm.conf`, but almost all
    partitions are excluded via `SuspendExcParts`/`SuspendExcNodes` (Max).
    Suspended nodes still run system services, so they don't truly power down on load.
  - **VM scaling.** The CPU partition scales OpenStack VMs up/down with demand; reliable Slurm node-resume-on-demand for bare-metal nodes is not yet working (Xand).
- **References:** blog post "Why efficiency matters" / sustainability framing.

---

## Tooling & performance

### 12. Analysis runtime is the same across date ranges

- **Status:** Open (cause identified).
- **Affects:** runtime of both CLI tools (`hpc-aggregate-stats`, `hpc-job-stats`).
- **What we found:** A re-run on CREATE (June 2026) took roughly 40–55 min *regardless of the date span queried*, up from ~10–30 min in Feb/Mar 2026.
- **Cause — a full table scan**: The query filters on `time_submit`, but the schema dump (`output_table_defs.txt`) shows no index on `create_job_table` *led* by `time_submit` — it appears only inside composite indices sorted by `id_job` first, and the only leading time-indices are on `time_end`/`time_eligible`.
With no usable index, a `time_submit` range forces a full scan of the whole table on every run, so a one-day and a six-month query scan the same rows — which is why runtime relates to total table size, not the date window.
(The query also joins the large `create_step_table` and string-parses `tres_usage_in_max` per row; that cost is range-independent too.)
An *index* is a sorted lookup that lets the database jump to matching rows; without one it reads every row.
- **What this does *not* explain:** The near-doubling since Feb/Mar (~10–30 min then). 
Row growth is too small: the DB goes back to ~Feb 2022 (~30M jobs over ~4 years), so a few extra months adds only single-digit-percent more rows — predicting a few minutes of additional runtime, not ~50.
- **How to confirm / fix:** 
  - `EXPLAIN` the query for a one-day vs a six-month range (a full scan with the same row estimate for both confirms it).
  - Time the SQL against the per-user LDAP lookups to see how long they each take.
  - The likely fix is to filter on `time_end` (leading-indexed) or add a `time_submit` index (needs infra input).
- **References:** `slurm_utils.py` (`fetch_job_data`); `aggregate_stats.py`, `job_stats.py`.
