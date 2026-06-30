# Notebooks

The notebooks are the **exploration / visualisation stage** of the pipeline: they read the per-job and per-faculty CSVs produced by the `hpc-job-stats` and `hpc-aggregate-stats` commands and turn them into plots and summaries. They need no database access and are normally run locally.

This file is the catalog of what each notebook does. For how to install the notebook dependencies, generate the input CSVs, and reproduce the committed analysis, see [Run the notebooks](../README.md#3-run-the-notebooks) in the README.

## Inputs

All notebooks read their data from `results/data/`:

- `<dates>_job_level_metrics.csv` — one row per job, with per-job CPU, memory, and time efficiencies (from `hpc-job-stats`).
- `<dates>_hpc_stats_output.csv` — one row per faculty, with both simple-average and weighted-average efficiencies (from `hpc-aggregate-stats`).

`<dates>` is the `YYYY-MM-DD_YYYY-MM-DD` range prefix the commands add automatically. For what "average" vs "weighted" efficiency mean, see [Weighted vs average efficiency](../README.md#weighted-vs-average-efficiency) in the README for a quick summary, or [Aggregation Methods](analysis/efficiency_metrics.md#aggregation-methods) in the analyst docs for the fuller treatment.

## Configuring a run

Each notebook has a config cell at the top with the values you set by hand:

- `DATE_FILTER` — the `YYYY-MM-DD_YYYY-MM-DD` range to load (or `None` to use the most recent CSVs in `RESULTS_DIR`). To analyse a different period, generate the CSVs for it (see [Run the notebooks](../README.md#3-run-the-notebooks)), set `DATE_FILTER` to match, and re-run all cells.
- `RESULTS_DIR` — where the input CSVs live (default `../results/data`).

A notebook that saves figures also sets a `PLOT_DIR` (the folder its PNGs are written to); one that only displays plots inline does not. To make an inline notebook save its figures, set a `PLOT_DIR` and add `savefig(...)` calls.

## The notebooks

### [`2026-02_sustainability_month_blog_post.ipynb`](../notebooks/2026-02_sustainability_month_blog_post.ipynb)

- **Perspective:** user / **average** efficiency.
- **Purpose:** generates figures for the [King's Climate & Sustainability Month blog post](https://docs.er.kcl.ac.uk/blog/2026/05/27/hpc-and-sustainability-how-efficiently-are-we-using-our-cluster/) (data: July–December 2025) — KDE density plots, the 2-D CPU-vs-memory efficiency heatmap, requested-vs-used scatter plots, a waste-severity breakdown, and faculty comparisons.
- **Outputs:** PNGs saved to `results/plots/2026-02_sustainability_month_blog_post/`.
- **Use it for:** reproducing or updating the blog-post figures.

### [`visualisation_users.ipynb`](../notebooks/visualisation_users.ipynb)

- Uses **average** efficiency (relevant for **user perspective**).
- **Purpose:** exploratory analysis — efficiency distributions (violin plots), investigation of jobs with >100% efficiency, CPU–memory correlation, and an educational "why efficiency matters" section.

### [`visualisation_infrastructure.ipynb`](../notebooks/visualisation_infrastructure.ipynb)

- Uses **weighted** average efficiency (larger jobs count more) (relevant for **infrastructure perspective**).
- **Purpose:** exploratory infrastructure-facing analysis — weighted efficiency, resource-waste pie/bar charts, and faculty comparisons.

Each notebook also includes a Technical Appendix documenting its own methodology.

## Adding a new notebook

When you add a notebook, keep this catalog and the conventions consistent:

1. Read input CSVs from `results/data/`.
2. If it saves figures, write them to a dedicated `results/plots/<notebook-name>/` folder (so outputs from different notebooks don't collide).
3. Add an entry above describing its perspective, purpose, inputs, and outputs.
