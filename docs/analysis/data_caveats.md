# Data Caveats

This document describes known limitations, edge cases, and potential issues when analyzing HPC cluster usage data.

## Job Selection

### Included States

Only jobs in these states are included in efficiency analysis:
- COMPLETED (3)
- TIMEOUT (6)
- OUT_OF_MEMORY (11)

### What's Excluded

| State | Why Excluded | Impact |
|-------|--------------|--------|
| PENDING | Never ran | No resource usage data |
| CANCELLED | May not have run | Incomplete or no data |
| FAILED | May have crashed early | Potentially misleading efficiency |
| NODE_FAIL | External failure | Not representative of job behavior |
| PREEMPTED | Interrupted | Incomplete execution |

**Implication**: Analysis represents jobs that ran to completion or natural termination, not all submitted jobs.

## CPU Time Accounting

### Multi-Node Jobs

For jobs spanning multiple nodes:
- CPU time is taken from the `user_sec`/`sys_sec` (rusage) columns, which capture only the head node's processes
- The distributed CPU time on remote nodes is therefore missed, so CPU efficiency is underestimated for genuinely multi-node jobs (a small fraction of all jobs)
- The cgroup-based TRES CPU value would capture remote-node time but is not currently used. See [open_questions.md](open_questions.md) #4

### Step Aggregation

CPU time is summed from job steps with logic to avoid double-counting:
- If srun steps exist (id_step >= 0): use those
- Otherwise: use batch/interactive step

Edge case: jobs with a substantial batch step alongside srun steps could be mis-summed, though this is rare. See [open_questions.md](open_questions.md) #5.

### CPU Efficiency Above 100%

CPU efficiency can exceed 100%, mainly because Slurm allocates whole cores: on hyperthreaded nodes (2 threads per core) a 1-CPU request is given a whole core = 2 logical CPUs, and multi-threaded code then uses them. Measured against *requested* CPUs this shows >100%; recomputing against *allocated* CPUs removes most of it, though a small residual stays unexplained. See [open_questions.md](open_questions.md) #2.

## Memory Accounting

### Peak Memory

Memory efficiency uses **peak** memory (maximum resident set size), because that is what has to be reserved: a job's memory request must cover its highest point, not its average. A short spike therefore sets the requirement even if usage is low the rest of the time.

### Memory Request Types

Users can request memory two ways — `--mem` (a total for the job) or `--mem-per-cpu` (an amount per allocated CPU). This needs no special handling in the efficiency calculation: Slurm already stores the **total** requested memory in `tres_req` (it pre-multiplies `--mem-per-cpu` by the CPU count), and peak usage is also a total, so `peak used / total requested` compares like-for-like regardless of how the request was written. (One consequence matters after memory enforcement: because `--mem-per-cpu` scales with the *allocated* CPU count, whole-core rounding can raise the enforced limit above the request — see [open_questions.md](open_questions.md) #7.)

## Data Gaps

### Missing Step Data

Some jobs may lack step table entries:
- Very short jobs that failed before step creation
- Jobs killed during startup
- Database issues

These jobs will have NULL efficiency values.

## User Attribution

Some jobs run under system or service accounts rather than an individual researcher — for example `hpcsys` (maintenance/recovery jobs) and CI/group accounts such as `er_slurm_group881` (GitLab CI jobs) appear in the data. These do not map to a research faculty via LDAP and fall into the "unknown"/"Other" buckets, so a small share of jobs is not attributable to a specific faculty.

## Related Documentation

- [Efficiency Metrics](efficiency_metrics.md) - How metrics are calculated
- [Interpreting Results](interpreting_results.md) - What values mean
- [Open Questions](open_questions.md) - Unresolved puzzles and methodological decisions
