# HPC Data Analysis

Analyses HPC cluster usage by faculty, with a focus on resource efficiency (CPU, memory, time). Queries the Slurm accounting database (MySQL) directly and maps users to faculties via LDAP.

## Documentation

- **For analysts** interpreting results: see [`docs/analysis/`](docs/analysis/index.md)
  - How efficiency metrics are calculated
  - What good/bad efficiency looks like
  - Known limitations and caveats

- **For developers** working on the codebase: see [`docs/development/`](docs/development/index.md)
  - Slurm database schema
  - CPU and memory accounting details
  - Dev scripts guide

## Structure

```
hpc-data-analysis/
├── src/
│   └── hpc_data_analysis/
│       ├── __init__.py
│       ├── slurm_utils.py                  # Shared utilities: MySQL, LDAP, TRES parsing
│       ├── aggregate_stats.py              # Aggregate statistics per faculty (→ CSV)
│       └── job_stats.py                    # Per-job efficiency metrics (→ CSV)
├── docs/
│   ├── analysis/                           # Documentation for analysts
│   └── development/                        # Documentation for developers
├── notebooks/
│   ├── blog_2026-02_sustainability.ipynb   # Blog-post plots (user perspective)
│   ├── visualisation_users.ipynb           # User-focused: average efficiency metrics
│   └── visualisation_infrastructure.ipynb  # Infrastructure-focused: weighted efficiency metrics
├── dev_scripts/                            # Diagnostic query scripts
│   └── output/                             # ...and their saved output
├── results/
│   ├── data/                               # Generated CSV output (gitignored)
│   └── plots/                              # Generated figures (committed)
├── pyproject.toml                          # Package metadata and dependency ranges
├── requirements.txt                        # Pinned dependency versions (reproducible env)
├── config.yaml.example                     # Template for config.yaml
├── config.yaml                             # MySQL credentials (not committed)
├── LICENSE
└── README.md
```

## Installation

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Create the data output directory (where the CLI tools write generated CSVs):

```bash
mkdir -p results/data
```

Install the package. Choose based on what you need:

```bash
# Core CLI tools only (query the database, write CSVs):
pip install .

# ...plus the notebook dependencies (pandas, matplotlib, seaborn, scipy, etc.):
pip install ".[notebook]"

# For development: an "editable" install that links the package to this
# source tree, so code edits take effect immediately without reinstalling:
pip install -e ".[notebook]"
```

`[notebook]` is an optional dependency group — the core tools don't need
pandas/seaborn/etc., so omitting it keeps the environment light for anyone who
only runs the CLI tools (and not the visualisation notebooks).

To reproduce the exact dependency versions this project was developed and
tested with, install the pinned set first, then the package itself:

```bash
pip install -r requirements.txt
pip install .            # or  pip install -e .  for development
```

`requirements.txt` pins every dependency (a reproducible snapshot);
`pyproject.toml` declares the looser compatible ranges used when you install
the package directly.

### Verify your installation

Confirm the package and its dependencies import in your *active* environment:

```bash
hpc-aggregate-stats --help     # package + entry point + core deps (mysql.connector, ldap, yaml)
python3 -c "import pandas, numpy, matplotlib, seaborn, scipy, statsmodels; print('notebook deps OK')"
```

This only checks that everything is installed and importable — not that the
database is reachable or your credentials work (that requires the cluster; see
[Usage](#usage)). If the first command says "command not found", the package
didn't install into your active environment — use the `PYTHONPATH` fallback
shown under Usage.

## Configuration

The tools rely on two configuration files. Both hold credentials and are kept out of version control.

### `config.yaml` — MySQL (you create this)

Connection details for the Slurm accounting database. Copy the template and fill in the values provided by the infrastructure team:

```bash
cp config.yaml.example config.yaml
```

It lives in the project root and is gitignored, so it is never committed. The accounting database is reachable only from the cluster, so run the tools there. The two analysis commands default to `config.yaml` in the directory you run them from; if it lives elsewhere, point them at it with `--config <path>`.

### `/etc/hpc_export_stats.yaml` — LDAP (infra-managed)

Only needed when mapping users to faculties (`--collate_by st=faculty` or `--include-faculty`). This file is provisioned and maintained by the infrastructure team on the cluster — you do not create or edit it, but it must exist for faculty lookups to work. The two analysis commands default to `/etc/hpc_export_stats.yaml`; if your file lives elsewhere, override the path with `--ad_config <path>`. It contains the following keys:

| Key | Meaning |
|-----|---------|
| `ldap_host` | AD/LDAP server hostname (connected to via `ldaps://`) |
| `ldap_ca_file` | path to the CA certificate file used to verify the TLS connection |
| `ldap_users_ou` | base OU searched for user accounts |
| `ldap_binddn` | bind DN used to authenticate |
| `ldap_password` | bind account password |

## Usage

Run from the repository root. The examples use the installed console commands
(`hpc-aggregate-stats`, `hpc-job-stats`), available after `pip install`. The
accounting database is reachable only from the cluster, so run these there.

> **If a command is "not found"** (common on shared/cloud systems where the
> package didn't install into the active Python environment), run the module
> directly with the source on the path instead — the arguments are identical:
> ```bash
> PYTHONPATH=src python3 -m hpc_data_analysis.aggregate_stats ...
> ```

### 1. Generate aggregate faculty statistics

```bash
hpc-aggregate-stats \
    --since 2025-01-01 --until 2025-02-01 \
    --collate_by st=faculty --collate_by none \
    --output results/data/hpc_stats_output.csv
```

- `--collate_by st=faculty`: Groups stats by faculty (LDAP attribute)
- `--collate_by none`: Adds a global summary row (`faculty="all"`)

### 2. Generate per-job metrics

```bash
hpc-job-stats \
    --since 2025-01-01 --until 2025-02-01 \
    --output results/data/job_level_metrics.csv --include-faculty
```

> **Output filenames are auto-prefixed with the date range.** The command above
> actually writes `results/data/2025-01-01_2025-02-01_job_level_metrics.csv`,
> not the bare name you passed. Generated CSVs contain usernames, so they are
> gitignored and never committed.

These two commands are also how you **regenerate the data** the notebooks read —
both require cluster database access (and LDAP access for the `--collate_by` /
`--include-faculty` faculty lookups).

### 3. Run the notebooks

Three notebooks are provided:

- **`notebooks/blog_2026-02_sustainability.ipynb`** — generates the publication-ready plots for the sustainability blog post (user perspective, **average efficiency**). Holds the most polished plotting code.

- **`notebooks/visualisation_users.ipynb`** — User-focused analysis using **average efficiency** (each job counts equally). Use this for user training, feedback sessions, and helping users understand typical job efficiency.

- **`notebooks/visualisation_infrastructure.ipynb`** — Infrastructure-focused analysis using **weighted efficiency** (larger jobs contribute more). Use this for capacity planning, resource allocation decisions, and understanding overall cluster utilisation.

The notebooks read the CSV files generated in steps 1–2 (from `results/data/`) and include a Technical Appendix documenting the methodology.

## What it computes

### Efficiency metrics

- **CPU efficiency**: total CPU time / (elapsed × requested CPUs). Can exceed 100% if jobs use more threads than requested CPUs.
- **Memory efficiency**: peak memory used / requested memory. Can exceed 100% if memory limits are not enforced.
- **Time efficiency**: elapsed wall-clock time / requested time limit.

### Weighted vs average efficiency

| Metric | Formula | Best for |
|--------|---------|----------|
| **Weighted** | sum(used) / sum(allocated) × 100 | Infrastructure planning — larger jobs contribute more to the overall picture |
| **Average** | mean(per-job efficiency) | User education — shows typical job efficiency, each job counts equally |

### Job states

- **Efficiency stats** include: COMPLETED, TIMEOUT, OUT_OF_MEMORY (jobs that ran and have meaningful resource usage)
- **Success** = COMPLETED only
- **Failed** = FAILED, TIMEOUT, NODE_FAIL, PREEMPTED, OUT_OF_MEMORY (not CANCELLED, which is intentional)

See the Technical Appendix in the notebooks for full details.
