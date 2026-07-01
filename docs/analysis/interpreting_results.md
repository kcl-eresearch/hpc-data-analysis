# Interpreting Results

This guide helps interpret efficiency metrics and identify patterns in HPC cluster usage.

## CPU Efficiency

### What Values Mean

| Efficiency | Rating | Meaning |
|:----------:|:------:|:--------|
| 80–100% | Excellent | Resources well matched to actual usage |
| 60–80% | Good | Some over-requesting — room for improvement |
| 40–60% | Moderate | Significant over-requesting — review your resource requests |
| 20–40% | Poor | Most of the requested resources are going unused |
| <20% | Very poor | Almost all requested resources are wasted |

This is the same five-tier scale used in the sustainability blog post, and it applies to CPU, memory, and time efficiency alike. For CPU specifically, a serial job on N requested CPUs sits near 100/N% (e.g. 1 of 8 ≈ 12.5%). CPU efficiency can also exceed 100% — see [Efficiency Metrics](efficiency_metrics.md) and [open_questions.md](open_questions.md) #2.

### Common Patterns

**Serial code on multiple cores** — the biggest single driver of CPU waste on the cluster
- Symptom: CPU efficiency near 100/N% for a job requesting N CPUs
- Cause: the code runs on one core but several were requested — either it isn't parallelised, or it needs to be told (via a flag or library) to use multiple cores
- Fix: request one CPU, or parallelise the code

**Cores idle for other reasons**
- Low CPU efficiency can also come from jobs that spend much of their time waiting (e.g. for disk or network I/O) rather than computing
- The accounting data alone can't distinguish the cause; diagnosing it needs profiling the running job

## Memory Efficiency

### What Values Mean

| Efficiency | Rating | Meaning |
|:----------:|:------:|:--------|
| 80–100% | Excellent | Resources well matched to actual usage |
| 60–80% | Good | Some over-requesting — room for improvement |
| 40–60% | Moderate | Significant over-requesting — review your resource requests |
| 20–40% | Poor | Most of the requested resources are going unused |
| <20% | Very poor | Almost all requested resources are wasted |

Memory efficiency can exceed 100% where memory was not enforced (before Feb 2026) or via `--mem-per-cpu` rounding — see [open_questions.md](open_questions.md) #6, #7.

### Common Patterns

**"Just in case" over-requesting** — widespread on the cluster
- Symptom: consistently low memory efficiency across many of a user's jobs
- Cause: memory requested as a safety margin, far above actual peak usage
- Impact: reserved-but-unused memory blocks other jobs and lengthens queues
- Fix: check actual peak usage (e.g. with `seff`) and request that plus a modest buffer

## Time Efficiency

### What Values Mean

| Efficiency | Rating | Meaning |
|:----------:|:------:|:--------|
| 80–100% | Excellent | Resources well matched to actual usage |
| 60–80% | Good | Some over-requesting — room for improvement |
| 40–60% | Moderate | Significant over-requesting — review your resource requests |
| 20–40% | Poor | Most of the requested resources are going unused |
| <20% | Very poor | Almost all requested resources are wasted |

A job at exactly 100% was typically killed at its time limit (TIMEOUT state). Note that "excellent" is more double-edged for time than for CPU/memory: using nearly all the requested time risks hitting the limit and being killed, so a modest safety margin is prudent (see Considerations below).

### Considerations

Time efficiency is **less critical** than CPU/memory efficiency because:
- Unused time is returned to the cluster immediately when job finishes
- It doesn't block other jobs (unlike reserved CPUs/memory)
- Some over-estimation is prudent to avoid job termination

However, very long time limits can:
- Reduce scheduler flexibility (harder to backfill)
- Delay job start (fewer slots available for long jobs)

## Identifying Waste

### Resource Waste Calculation

```
CPU Waste = (1 - CPU Efficiency/100) × CPU-hours requested
Memory Waste = (1 - Memory Efficiency/100) × Memory-hours requested
```

### High-Impact Targets

Focus optimization efforts on jobs with:
1. **Large resource requests** AND **low efficiency** - maximum waste
2. **High frequency** - fixing once helps many jobs
3. **Long duration** - more opportunity for waste

### Example Analysis

If you find:
- 1000 jobs with 8 CPUs, 50% CPU efficiency, 4 hours each
- Total waste: 1000 × 8 × 4 × 0.5 = 16,000 CPU-hours

Compared to:
- 10 jobs with 128 CPUs, 90% CPU efficiency, 24 hours each
- Total waste: 10 × 128 × 24 × 0.1 = 3,072 CPU-hours

The first group (many small inefficient jobs) wastes 5× more resources.

## Red Flags

Watch for these patterns in the data:

| Pattern | Possible Issue |
|---------|----------------|
| Many jobs at exactly 100% time efficiency | Jobs being killed at time limit (TIMEOUT) |
| Memory efficiency >100% | Memory not enforced (pre-Feb 2026) or `--mem-per-cpu` rounding — see [open_questions.md](open_questions.md) #6, #7 |
| CPU efficiency >100% | Whole-core rounding on hyperthreaded nodes; small residual unexplained — see [open_questions.md](open_questions.md) #2 |
| Very low efficiency for large jobs | High-impact waste |
| Single user dominating waste | Training opportunity |

## Related Documentation

- [Efficiency Metrics](efficiency_metrics.md) - How metrics are calculated
- [Data Caveats](data_caveats.md) - Limitations when interpreting
- [Open Questions](open_questions.md) - Unresolved puzzles and methodological decisions
