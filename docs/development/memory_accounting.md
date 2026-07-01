# Memory Accounting

This document explains how memory requests and usage are recorded in the Slurm accounting database.

## Memory Request Types

Slurm supports two ways to request memory:

| Option | Meaning | Typical Use |
|--------|---------|-------------|
| `--mem=X` | X memory per **node** | Jobs using all memory on allocated nodes |
| `--mem-per-cpu=X` | X memory per **CPU** | Jobs where memory scales with CPU count |

## How Memory Type is Encoded

`mem_req` is a single 64-bit integer that has to record **two** things: the memory value the user asked for, *and* whether they used `--mem` (per node) or `--mem-per-cpu` (per CPU). Rather than use two columns, Slurm packs the yes/no into one spare bit of the number.

Memory values in MB never come near needing all 64 bits, so the **top bit (bit 63)** is free to use as a flag:

- **bit 63 = 0** → the value is `--mem` (a per-node total)
- **bit 63 = 1** → the value is `--mem-per-cpu` (a per-CPU amount)

The memory value itself always lives in the lower 63 bits. So reading `mem_req` is two steps: (a) test the top bit to learn the type, and (b) mask the top bit off to recover the value.

```python
# (a) Which mode? Test bit 63.
is_per_cpu = (mem_req & 0x8000000000000000) != 0

# (b) The value in MB — mask off bit 63, keeping the lower 63 bits.
mem_value_mb = mem_req & 0x7FFFFFFFFFFFFFFF
```

Concretely, `--mem-per-cpu=4096` is stored as `2^63 + 4096` = `9223372036854779904`; masking off bit 63 gives back `4096`.

| mem_req (decimal) | mem_req (hex) | Type | Value (lower 63 bits) |
|-------------------|---------------|------|-----------------------|
| 4096 | 0x1000 | `--mem` (per-node) | 4096 MB |
| 9223372036854779904 | 0x8000000000001000 | `--mem-per-cpu` | 4096 MB |

In practice the analysis avoids this decoding entirely by reading **`tres_req` (TRES ID 2)** instead, which already stores the *total* requested memory in MB regardless of mode (Slurm multiplies `--mem-per-cpu` by the CPU count for you). `mem_req` is only needed when you specifically want to know which mode the user chose.

## Memory Units in Different Fields

**Critical**: Different fields use different units!

| Field | Table | Units | Notes |
|-------|-------|-------|-------|
| `mem_req` | create_job_table | MB (with bit 63 flag) | See encoding above |
| `tres_req` TRES ID 2 | create_job_table | **MB** | Requested memory |
| `tres_usage_in_max` TRES ID 2 | create_step_table | **Bytes** | Peak memory used |

### Conversion for Efficiency Calculation

```python
# Requested memory (from tres_req, in MB)
reqmem_mb = parse_tres_value(tres_req, 2)
reqmem_bytes = reqmem_mb * 1024 * 1024

# Used memory (from tres_usage_in_max, already in bytes)
maxrss_bytes = parse_tres_value(tres_usage_in_max, 2)

# Memory efficiency
mem_eff = (maxrss_bytes / reqmem_bytes) * 100
```

## Memory Usage Tracking

Memory usage is tracked per step in `tres_usage_in_max`:

- TRES ID 2 = memory in bytes
- Value represents peak RSS (Resident Set Size)
- Take MAX across all steps for job-level peak memory

```sql
MAX(
    CAST(
        SUBSTRING_INDEX(
            SUBSTRING_INDEX(CONCAT(',', s.tres_usage_in_max), ',2=', -1),
            ',', 1
        ) AS UNSIGNED
    )
) AS max_mem_bytes
```

The memory efficiency formula and how to read the resulting percentages are analysis concerns — see [Efficiency Metrics](../analysis/efficiency_metrics.md) and [Interpreting Results](../analysis/interpreting_results.md).

## Display Units

When displaying memory values to users, use binary units (matching Slurm conventions):

| Unit | Value |
|------|-------|
| 1 KiB | 1024 bytes |
| 1 MiB | 1024 KiB = 1,048,576 bytes |
| 1 GiB | 1024 MiB = 1,073,741,824 bytes |
| 1 TiB | 1024 GiB |

```python
# Convert bytes to GiB
mem_gib = mem_bytes / (1024 ** 3)
```

Note: Use "GiB" not "GB" to indicate binary units (1024-based) rather than decimal units (1000-based).

## Investigation Scripts

- `query_memory.py` - Determines unit encoding through sampling
- `query_cpu_mem_diagnostics.py` - Part 2 analyses the `--mem` vs `--mem-per-cpu` distribution (bit 63)

## Related Documentation

- [TRES Encoding](tres_encoding.md) - How TRES strings are parsed
- [Slurm Database Schema](slurm_database_schema.md) - Column definitions
