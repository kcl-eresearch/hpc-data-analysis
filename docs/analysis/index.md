# Analysis Documentation

This documentation is for analysts interpreting HPC cluster usage data. It explains how efficiency metrics are calculated and how to interpret results.

## Contents

1. [Efficiency Metrics](efficiency_metrics.md) - How CPU, memory, and time efficiency are calculated
2. [Interpreting Results](interpreting_results.md) - What good and bad efficiency looks like
3. [Data Caveats](data_caveats.md) - Known limitations and edge cases
4. [Open Questions](open_questions.md) - Unresolved puzzles, assumptions, and methodological decisions behind specific results

## Quick Reference

### Efficiency Formulas

| Metric | Formula | Ideal Value |
|--------|---------|-------------|
| CPU Efficiency | `CPU time used / (elapsed time × CPUs requested) × 100` | ~100% for parallel jobs |
| Memory Efficiency | `Peak memory used / Memory requested × 100` | 80-100% |
| Time Efficiency | `Elapsed time / Time limit × 100` | Varies by job type |

### What Jobs Are Included

Only jobs that ran and have meaningful resource data:
- **COMPLETED** (state 3) - Normal finish
- **TIMEOUT** (state 6) - Ran until time limit
- **OUT_OF_MEMORY** (state 11) - Exceeded memory

Excluded: PENDING, CANCELLED, FAILED (may not have run long enough for valid data).

### Units

- **Time**: Seconds (elapsed, CPU time)
- **Memory**: Bytes internally, displayed as GiB (1 GiB = 1024³ bytes)
- **Efficiency**: Percentages (0-100%, can exceed 100% in some cases)

## Output Files

The main analysis tools produce:

| Tool | Output | Description |
|------|--------|-------------|
| `hpc-job-stats` | `job_level_metrics.csv` | Per-job metrics for distribution analysis |
| `hpc-aggregate-stats` | `hpc_stats_output.csv` | Faculty/user aggregations |

Both tools auto-prefix the output filename with the analysis date range, e.g. `2025-07-01_2025-12-31_hpc_stats_output.csv`.

## Getting Started

1. Review [Efficiency Metrics](efficiency_metrics.md) to understand what's being measured
2. Check [Interpreting Results](interpreting_results.md) for guidance on what values mean
3. Read [Data Caveats](data_caveats.md) before drawing conclusions
4. Consult [Open Questions](open_questions.md) for the unresolved issues and assumptions behind specific figures (e.g. why some efficiencies exceed 100%)
