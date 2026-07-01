# Efficiency Metrics

This document explains how resource efficiency metrics are calculated for HPC jobs.

## CPU Efficiency

**What it measures**: How much of the requested CPU time was actually used for computation.

### Formula

```
CPU Efficiency (%) = (Total CPU Time Used / Total CPU Time Available) × 100
                   = (total_cpu_seconds / (elapsed_seconds × cpus_requested)) × 100
```

### Components

| Component | Description | Source |
|-----------|-------------|--------|
| Total CPU Time Used | User + system CPU seconds across all job steps | Sum of `user_sec + sys_sec` from step table |
| Elapsed Time | Wall-clock time the job ran | `time_end - time_start` |
| CPUs Requested | Number of CPU cores requested | From TRES request string |

### Example

A job that:
- Requested 4 CPUs
- Ran for 1 hour (3600 seconds)
- Used 10,800 CPU-seconds total

```
CPU Available = 4 × 3600 = 14,400 CPU-seconds
CPU Efficiency = 10,800 / 14,400 × 100 = 75%
```

### User vs System CPU

CPU time is split into:
- **User CPU**: Time spent executing user code
- **System CPU**: Time spent in kernel/system calls (I/O, memory management)

```
User CPU % = (User CPU Time / Total CPU Time) × 100
```

High system CPU (>20%) may indicate I/O-heavy workloads.

## Memory Efficiency

**What it measures**: How much of the requested memory was actually used.

### Formula

```
Memory Efficiency (%) = (Peak Memory Used / Memory Requested) × 100
                      = (maxrss_bytes / reqmem_bytes) × 100
```

### Components

| Component | Description | Source |
|-----------|-------------|--------|
| Peak Memory Used | Maximum resident set size (RSS) | `tres_usage_in_max` TRES ID 2 (in bytes) |
| Memory Requested | Memory requested by user | `tres_req` TRES ID 2 (in MB, converted to bytes) |

### Example

A job that:
- Requested 16 GB (16,384 MB = 17,179,869,184 bytes)
- Used peak 12 GB (12,884,901,888 bytes)

```
Memory Efficiency = 12,884,901,888 / 17,179,869,184 × 100 = 75%
```

## Time Efficiency

**What it measures**: How much of the requested time limit was actually used.

### Formula

```
Time Efficiency (%) = (Elapsed Time / Time Limit) × 100
                    = (elapsed_seconds / timelimit_seconds) × 100
```

### Components

| Component | Description | Source |
|-----------|-------------|--------|
| Elapsed Time | Wall-clock time the job ran | `time_end - time_start` |
| Time Limit | Requested time limit | `timelimit` column (in minutes, converted to seconds) |

### Example

A job that:
- Requested 24 hours (86,400 seconds)
- Ran for 18 hours (64,800 seconds)

```
Time Efficiency = 64,800 / 86,400 × 100 = 75%
```

## Wait Time

**What it measures**: How long a job waited in the queue before starting.

### Formula

```
Wait Time (seconds) = time_start - time_submit
```

## Submission Type

Jobs are classified by how they were submitted:

| Type | Description | Detection |
|------|-------------|-----------|
| batch | Submitted via `sbatch` | `submit_line` begins with `sbatch` (with a fallback to the presence of a batch step, id_step = -5) |
| interactive | Submitted via `srun --pty` | `--pty` present in `submit_line` |

Detection is based on the raw `submit_line`, not on the interactive step (id_step = -6): on CREATE almost no jobs create that step (users start interactive sessions with `srun --pty`, not `salloc`), so the step-based method misses essentially all of them. See [open_questions.md](open_questions.md) #9.

## Aggregation Methods

To summarise a group of jobs (a faculty, or the whole cluster), `hpc-aggregate-stats` reports **two** figures for each efficiency metric, because they answer different questions:

| Method | How it combines jobs | Answers | Perspective |
|--------|----------------------|---------|-------------|
| Simple average (`avg_*`) | mean of the per-job efficiencies; each job counts **once** | "What is the typical job's efficiency?" | User |
| Weighted average (`weighted_*`) | a ratio of totals, so each job counts in proportion to the resources it reserved | "How efficiently were the reserved resources used overall?" | Infrastructure |

The simple average treats a 1-CPU job and a 512-CPU job equally; the weighted average lets the large job count for more, so it better reflects cluster-wide impact. Both are produced for every metric.

The weighted figure is a ratio of totals, and the weighting quantity differs by metric:

```
Weighted CPU efficiency    = Σ(CPU time used) / Σ(elapsed × CPUs requested)
Weighted memory efficiency = Σ(peak memory used) / Σ(requested memory)
Weighted time efficiency   = Σ(elapsed) / Σ(time limit)
```

Other aggregates:

| Metric | Aggregation |
|--------|-------------|
| Wait time | Total and mean (`total_wait_sec`, `avg_wait_sec`); a median can be computed from the per-job output if needed |
| Job count | Sum of jobs in the period |

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Elapsed = 0 | CPU/time efficiency = NULL |
| Memory requested = 0 | Memory efficiency = NULL |
| CPU time > available | Efficiency > 100% — mainly whole-core rounding on hyperthreaded nodes (allocated CPUs can exceed requested); a small residual is unexplained. See [open_questions.md](open_questions.md) #2 |
| Memory used > requested | Efficiency > 100% — memory was not enforced before Feb 2026, so jobs could exceed their request without being killed (not an OOM kill). See [open_questions.md](open_questions.md) #6, #7 |

## Related Documentation

- [Interpreting Results](interpreting_results.md) - What these values mean in practice
- [Data Caveats](data_caveats.md) - Limitations to be aware of
- [Open Questions](open_questions.md) - Unresolved puzzles and methodological decisions
