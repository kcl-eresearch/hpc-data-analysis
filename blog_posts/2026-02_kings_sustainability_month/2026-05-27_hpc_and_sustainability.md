# HPC and Sustainability: How Efficiently Are We Using Our Cluster?

*King's Climate and Sustainability Month, February 2026*

## Introduction

An High Performance Computing (HPC) cluster is a shared resource — and like any shared resource, how we use it affects everyone. Every computing processing unit (CPU) reserved but unused, every gigabyte of memory allocated but never touched, is a resource that another researcher's job is queuing for. As part of [King's Climate and Sustainability Month](https://www.kcl.ac.uk/climate-sustainability/take-action/kings-sustainability-month) in February, we analysed six months of job data (July–December 2025) from the CREATE HPC cluster to find out: how efficiently are we actually using our resources?

The short answer: there's significant room for improvement. Across ~2.9 million analysed jobs, the **average CPU efficiency was 60%** and the **average memory efficiency was just 19%**. These findings were one of the motivations behind launching [`seff`](https://forum.er.kcl.ac.uk/t/new-tool-available-measuring-and-improving-the-efficiency-of-your-hpc-jobs/3269), a tool that lets you check the efficiency of any completed job with a single command. This post presents the full picture — how efficient jobs are across CPU, memory, and time, where the waste is concentrated, how faculties compare, and what you can do about it. The first half covers the key findings and practical recommendations; if you're short on time, that's all you need. The second half digs into resource request patterns, waste quantification, and faculty-level breakdowns for those who want the detail.

### Why efficiency matters

When you request resources (CPUs, memory) for a job, those resources are **reserved exclusively for you**, even if your job doesn't use them. This means:

- **Other jobs can't access those resources** while they sit idle — unused cores and memory are locked away from everyone else.
- **Queue wait times increase** for everyone, because the scheduler sees the cluster as full when it's actually underutilised.
- **The cluster's throughput drops** — fewer jobs run overall, slowing down research across the board.

In short, over-requesting resources doesn't just waste your own allocation — it directly impacts your colleagues' ability to get their work done. This post is about that kind of efficiency: making the most of the cluster we have, so that everyone gets fair access and faster results.

There's also a **sustainability** angle. The most relevant link in this context is to hardware: the cluster has a finite lifespan whether it's fully utilised or not, so if widespread over-requesting means the same body of research takes two hardware generations instead of one, that's twice the environmental cost in manufacturing and deployment for the same scientific output. And as demand grows, poor utilisation means capacity runs out sooner, potentially triggering expansion that carries its own CO₂ cost. The link between job efficiency and electricity use is more nuanced — most green HPC initiatives focus on carbon-aware scheduling, hardware improvements, or avoiding unnecessary computation (for an overview, see [Silva et al., 2024](https://www.sciencedirect.com/science/article/pii/S1364032123008778) and [Hölbling et al., 2025](https://www.sciencedirect.com/science/article/pii/S2666789425000789))

**The good news**: most inefficiency comes from requesting more than needed, and that's straightforward to fix once you know what to check.

Let's look at the data.

## Cluster-Wide Efficiency

### Which Jobs We Included

Between July and December 2025, ~3.7 million jobs were submitted to CREATE HPC. Using data recorded by Slurm — the workload manager that schedules and tracks all jobs on the cluster — we identified ~2.9 million jobs in states suitable for efficiency analysis, i.e., jobs that

- completed successfully (Slurm state `COMPLETED`),
- ran until their time limit (Slurm state `TIMEOUT`), or
- were killed for exceeding memory (Slurm state `OUT_OF_MEMORY`).

The remaining ~800k jobs were excluded because they either didn't run long enough (e.g., Slurm state `CANCELLED`) or terminated abnormally (e.g., Slurm state `FAILED`), making their resource usage unrepresentative.

For more details on which states were included and why, have a look at the [Appendix](#job-states-included).

In Figure 1, we can see that about three quarters of all submitted jobs completed successfully. Notably, `OUT_OF_MEMORY` — the state assigned when a job is killed for exceeding its memory allocation — is absent from the plot because memory limits were not yet enforced during this period.

![job_state_distribution](../../images/hpc-data-analysis/job_state_distribution.png)
*Figure 1: Job state distribution.*

### Efficiency Averages and Distributions

We measure three types of efficiency:

- **CPU efficiency** – how much of the allocated CPU time was actually used for computation (if you request 4 CPUs for 1 hour, you have 4 CPU-hours available).
- **Memory efficiency** – a job's peak memory usage compared to the amount requested.
- **Time efficiency** – how much of the requested wall time was used. (Unlike CPU and memory, unused time is not "blocked" — resources are released as soon as a job finishes. But over-requesting time still affects queue wait times, as we'll see below.)

Full definitions and formulas are in the [Appendix](#efficiency-metrics).

Before diving into the numbers, here's a rough guide for how to interpret efficiency percentages:

|   Range   |   Rating   | Meaning |
|:---------:|:----------:|:--------|
| 80–100%   | Excellent  | Resources well matched to actual usage |
| 60–80%    | Good | Some over-requesting — room for improvement |
| 40–60%      | Moderate | Significant over-requesting — review your resource requests |
| 20–40%      | Poor | Most of the requested resources are going unused |
| <20%      | Very poor | Almost all requested resources are wasted |

A small number of jobs with null or >100% efficiency values were excluded from the plots below; details are in the [Appendix](#excluded-jobs).

For each metric, we start with the headline averages and then look at the full distribution — which reveals patterns that averages hide, like whether most jobs are reasonably efficient with a few outliers, or whether low efficiency is widespread.

#### CPU Efficiency

The average CPU efficiency across all jobs is 60%, with a median of 71%. Figure 2 shows the full distribution. There's a reassuring peak near 100%, but also a long tail stretching all the way down — with a second concentration of jobs in the 0–15% range, suggesting a substantial number of jobs barely use their CPUs at all.

![cpu_efficiency_density](../../images/hpc-data-analysis/cpu_efficiency_density.png)
*Figure 2: CPU efficiency distribution.*

The picture changes dramatically when we separate **single-CPU** and **multi-CPU jobs** (Figure 3). Single-CPU jobs make up ~58% of all jobs and show a strong peak near 100% — most are using their one core well. Multi-CPU jobs (~42% of all jobs) tell a different story: the highest density sits in the 0–20% range, suggesting that many jobs request multiple cores but barely use them — likely because the code isn't parallelised, or can't effectively use all the cores requested.

When you request multiple CPUs, the expectation is that your code splits its work across all of them in parallel. If it doesn't — either because the software needs to be explicitly told to use multiple cores (e.g., via a library), or because only parts of the computation can actually run in parallel — you end up with reserved cores sitting idle.

![cpu_efficiency_density_split](../../images/hpc-data-analysis/cpu_efficiency_density_split.png)
*Figure 3: CPU efficiency by request size. Left: Jobs requesting one CPU. Right: Jobs requesting more than one CPU. Note that the y-axis scales differ between panels.*

The gap is stark: single-CPU jobs have a mean CPU efficiency of 82% and a median of 96% — solidly "excellent". Multi-CPU jobs average just 32%, with a median of 19%. This is the single biggest driver of CPU inefficiency on the cluster.

| Metric/request type | Single-CPU | Multi-CPU |
|:----------------------|:-------:|:-------:|
| Mean CPU efficiency |  81.8%  | 31.7% |
| Median CPU efficiency |  95.5%  | 18.6% |

*Table 1: Mean/median CPU efficiency by request type.*

#### Memory Efficiency

The average memory efficiency is 19%, with a median of just 9%. Figure 4 shows the distribution. Unlike CPU efficiency, there is no peak near 100%. Instead, the distribution is dominated by a spike near 0%, with most of the density sitting below 10%. Small bumps around 55% and 85% suggest pockets of jobs with better- or well-sized memory requests, but they are the exception.

![mem_efficiency_density](../../images/hpc-data-analysis/mem_efficiency_density.png)
*Figure 4: Memory efficiency distribution.*

Figure 5 separates jobs by how much memory they requested. Jobs requesting ≤1 GiB (~28% of all jobs) show density spread across the 0–30% range with a notable bump near 85–95%, indicating that a significant share of these smaller requests are well-sized. Jobs requesting more than 1 GiB (~72% of all jobs) are a different story: nearly all the density is concentrated near 0%, with very little beyond 20%.

![mem_efficiency_density_split](../../images/hpc-data-analysis/mem_efficiency_density_split.png)
*Figure 5: Memory efficiency by request size. Left: Jobs requesting ≤ 1 GiB of memory. Right: Jobs requesting more than 1 GiB. Note that the y-axis scales differ between panels.*

Neither group fares well (Table 2): jobs requesting ≤1 GiB have a mean of 24% and a median of 15% efficiency. Jobs requesting more than 1 GiB have an average of 18% with a median of just 4%. Unlike CPU, where single-resource jobs are generally fine, memory efficiency is low across both groups.

| Metric/request type | ≤1 GiB requests | >1 GiB requests |
|:----------------------|:-------:|:-------:|
| Mean memory efficiency    |  23.6%  | 17.6% |
| Median memory efficiency  |  15.3%  | 4.4% |

*Table 2: Mean/median memory efficiency by request type.*

#### Time Efficiency

The average time efficiency is 12%, with a median of just 2%. Figure 6 shows the distribution — the vast majority of jobs finish using only a small fraction of their requested wall time, with most of the density concentrated near 0%. Unlike CPU and memory, there is essentially no peak near 100%.

![time_efficiency_density](../../images/hpc-data-analysis/time_efficiency_density.png)
*Figure 6: Time efficiency distribution.*

Figure 7 separates jobs by how much time they requested. Jobs with short time limits (≤1 hour, ~31% of all jobs) show a more spread-out distribution, with visible density across the range. Jobs with longer time limits (>1 hour, ~69% of all jobs) are mostly concentrated near 0%.

![time_efficiency_density_split](../../images/hpc-data-analysis/time_efficiency_density_split.png)
*Figure 7: Time efficiency by request length. Left: Jobs with time limits ≤ 1 hour. Right: Jobs with time limits > 1 hour. Note that the y-axis scales differ between panels.*

The averages and medians bear this out (Table 3): short-limit jobs have a mean time efficiency of ~20% and a median of 12%. Long-limit jobs average just 8%, with a median of 0.5%.

| Metric/request type | ≤1 hour requests | >1 hour requests |
|:----------------------|:-------:|:-------:|
| Mean time efficiency    |  20.3%  | 8.1% |
| Median time efficiency  |  11.7%  | 0.5% |

*Table 3: Mean/median time efficiency by request length.*

#### Default Settings and Their Impact

Before reading too much into the very low time efficiency numbers: the cluster assigns a **24-hour default** wall time for batch jobs when no value is specified (and 1 hour for interactive jobs). Many jobs simply use this default, so a job that finishes in 30 minutes but was given the default 24 hours has a time efficiency of just 2%. The defaults for CPU (1 core) and memory (1 GiB) also contribute: a substantial portion of jobs (~68%) use less than 1 GiB of actual memory, and many use less than 1 hour of CPU time (~79%). For these jobs, the defaults are an over-allocation, which partly explains the low efficiency numbers above. Requesting less than the default takes deliberate effort, but if your jobs consistently use far less, it's worth adjusting your requests downward.

As noted above, time works differently from CPU and memory: once a job finishes, resources are released immediately, so unused time doesn't block them in the same way as unused CPU or memory do. It does, however, increase queue wait time, because the scheduler must find a slot where resources are free for the full requested duration — and it prevents your job from benefiting from backfill scheduling (see [Appendix](#backfill-scheduling)). Requesting a realistic time limit helps your jobs start sooner.

#### A Note on Efficiency and Scale

The efficiency numbers in this post treat every job equally, regardless of size. However, a large job with low efficiency wastes far more cluster resources than a small one. A single-CPU job at 20% efficiency wastes nothing — it's using its one core (and couldn't be allocated a smaller resource limit). A 64-core job at 20% efficiency leaves ~51 cores sitting idle. Similarly, a job using 500 MB of a 1 GiB memory allocation wastes very little, while one using 500 MB of a 100 GiB allocation locks away nearly 100 GiB.

Thus, while the headline efficiency numbers may look alarming across the board, the biggest concern is not the many small jobs, but the smaller number of large jobs that over-request by dozens of CPU cores or tens to hundreds of GiB of memory.

## Summary

We analysed ~2.9 million jobs on CREATE HPC from July to December 2025, looking at how well resource requests — CPUs, memory, and time limits — match actual usage. Here is what we found:

- **CPU efficiency is a tale of two halves.** Single-CPU jobs are generally well utilised (median 96%), but multi-CPU jobs average just 32% — many jobs request multiple cores without the code actually using them. This is the single biggest driver of CPU waste.
- **Memory is over-requested almost everywhere.** The median job uses just 8.5% of its requested memory. For jobs using the default 1 GiB request, this isn't necessarily a concern — the real waste comes from jobs requesting tens or hundreds of GiB while using only a fraction.
- **Time limits are rarely tight.** The median job finishes using 2% of its requested wall time, largely because many jobs use the 24-hour default without adjusting it.
- **Low efficiency isn't always a problem**. A single-CPU job at 20% efficiency wastes nothing; a 64-core job at 20% wastes ~51 cores. The biggest concern isn't the many small jobs, but the smaller number of large jobs that over-request at scale.

The good news: most of this is straightforward to fix. The next section covers concrete steps you can take to right-size your resource requests.

## How to Improve Your Efficiency

Having seen where the inefficiency lies, what can you do about it? Here are six practical steps, starting with the single most useful one:

1. **Make `seff` a habit.** Whenever you're unsure whether your resource requests are right, run `seff <jobid>` to see your CPU, memory, and GPU efficiency. It takes seconds and tells you immediately whether your resource requests are in the right ballpark. See our [detailed guide on seff and improving job efficiency](https://forum.er.kcl.ac.uk/t/new-tool-available-measuring-and-improving-the-efficiency-of-your-hpc-jobs/3269) for worked examples.
1. **Prioritise your largest jobs.** A small job with low efficiency wastes little, but a job requesting 64 cores or 100 GiB of memory that only uses a fraction locks away resources at scale and increases queue times for everyone. If you run a mix of small and large jobs, focus your efficiency efforts on the big ones first — that's where right-sizing has the most impact.
1. **Don't accept defaults blindly.** Every job uses at least one CPU core, but the default time and memory limits may be far more than you need. Think about what your job actually requires before submitting — don't leave defaults in place simply because it's easy.
1. **Question your CPU count in multi-CPU jobs.** 75% of multi-CPU jobs used less than half their requested CPU time. CPU efficiency drops sharply once jobs request more than the default of one core. Before requesting multiple cores, consider two things. First, can your computation be parallelised at all? Some algorithms are inherently sequential — no amount of cores will speed them up. Second, even if your computational problem can be parallelised in principle, does your code actually use multiple cores? Many programs need explicit flags, libraries, or code changes to run in parallel — without them, only one core does the work while the rest sits idle. If you're unsure on either point, seek out training or help before scaling up.
1. **Don't ignore memory.** 85% of jobs used less than half their requested memory. If you've never checked, there's a good chance you're over-requesting. Use `seff` to find your actual peak usage and request that plus a 10–20% buffer.
1. **Tighten your time limits.** 92% of jobs used less than half the requested time. While over-requesting time doesn't waste resources directly, it increases your queue wait time. If your job takes 2 hours, request 3 — not 24.
1. **Break up complex pipelines.** If only some stages of your workflow need many CPUs or lots of memory, split them into separate jobs with appropriate requests for each stage, rather than requesting the maximum for the entire pipeline.

### Getting help

- **Ask on the [e-Research forum](https://forum.er.kcl.ac.uk)** — other users may have tips for your specific software
- **Attend an [e-Research training workshop](https://docs.er.kcl.ac.uk/training/)** on Profiling and Optimisation for Python
- **Book a [Research Software Code Clinic](https://docs.er.kcl.ac.uk/research_software_engineering/code_clinic/)** — 30-minute sessions with a Research Software Engineer
- **Email [support@er.kcl.ac.uk](mailto:support@er.kcl.ac.uk)** for more complex queries or longer-term collaboration

## Acknowledgments

Thanks to Liz Ing-Simmons and James Graham for reviewing this post.
<br>

## Further Analysis - Request Patterns, Resource Waste, and Faculty Breakdowns

The following sections take a closer look at the relationship between CPU and memory efficiency, what resources people are actually requesting, how much waste that translates into, and how faculties compare.

## Are CPU-Efficient Jobs Also Memory-Efficient?

So far, we've looked at CPU, memory, and time efficiency separately. But are they related? For example, do jobs that use their CPUs well also tend to use their memory well?

There is a moderate positive correlation between CPU and memory efficiency — jobs that use their CPUs well tend to use their memory reasonably well too (see Figure 8). But this relationship breaks down for the most CPU-efficient jobs: a large fraction of jobs with high CPU efficiency remain memory-inefficient; while parallelisation is done right, memory requests are often not sized accurately. (For details on the statistical methods used, see the [Appendix](#cpu-memory-correlation-methodology).)

![cpu_vs_mem_efficiency](../../images/hpc-data-analysis/cpu_vs_mem_efficiency.png)
*Figure 8: CPU efficiency vs memory efficiency. Each cell groups jobs into a 10% × 10% efficiency bin; colour indicates how many jobs fall in that bin (log scale).*

## What Resources Are People Requesting?

The efficiency distributions and correlation above paint a picture of widespread over-requesting, particularly for memory and time. In this section, we look at what people are actually asking for — and whether the choices look deliberate, defaulted, or more or less random.

The following plots are based on all ~2.9 million efficiency jobs with valid states, regardless of efficiency value.

### CPUs

Figure 9 depicts the distribution of CPU requests on a log scale. As we've already seen above, the majority of jobs request a single CPU, with a median of one CPU and a higher mean at 7.1 CPUs, pulled up by jobs requesting many cores (the 95th percentile is 28 CPUs, with a maximum of 1,024). The next most common requests after 1 are 8 CPUs (16%), 4 CPUs (8%), and 2 CPUs (5%).

Requests cluster around powers of two (8, 16, 32, 64) and round numbers (100, 1000). The former is no coincidence — powers of two have established themselves as a sensible default because some parallelisation frameworks (e. g., [MPI's collective operations](https://mpitutorial.com/tutorials/mpi-broadcast-and-collective-communication/)) distribute work most efficiently with them: if you have a set of tasks to distribute, a power-of-two number of CPUs lets you split the work in half, then in half again, and so on — each split is perfectly even, with no remainder. For example, 12 tasks split evenly across 2 CPUs (6 each), then across 4 (3 each) — but not across 5.

![cpus_requested_distribution](../../images/hpc-data-analysis/cpus_requested_distribution.png)
*Figure 9: Distribution of requested CPUs (on a log scale).*

### Memory

Figure 10 shows the distribution of memory requests on a log scale. About 30% of jobs use the 1 GiB default — visible as the tallest bar. Beyond that, requests cluster around round values (2, 4, 8, 10, 100 GiB). The median request is 4 GiB, with a higher at 219 GiB pulled up by extreme requests (the 95th percentile is 100 GiB, and outliers go far beyond that).

Two anomalous peaks stand out in the tail: one around 5,000–10,000 GiB and another near 500,000 GiB. These are largely explained by a common pitfall: Slurm offers two ways to request memory — a total amount for the whole job, or an amount per allocated CPU. Confusing the two can lead to enormous reservations, for example, requesting 150 GiB per CPU with 100 CPUs reserves 15,000 GiB (nearly 15 TiB).

Over 37,000 jobs (1.3%) requested more than 1 TiB of memory — and 99.6% of them used the per-CPU memory option. Of these, over 36,000 jobs all request the same amount: 150 GiB per CPU. All >1 TiB requests come from just 25 users, each submitting large batches of jobs with massively inflated memory reservations — while their median actual memory usage is only 0.85 GiB.

![memory_requested_distribution](../../images/hpc-data-analysis/memory_requested_distribution.png)
*Figure 10: Distribution of requested memory (on a log scale).*

### Time

Figure 11 depicts the distribution of time requests. About a third of jobs (~31%) request up to an hour, and the vast majority (~87%) request a day or less. On standard partitions, the maximum allowed wall time is 48 hours for batch jobs. For interactive jobs, users must specify a time limit of up to 4 hours. The default for batch jobs is 24 hours — and it shows: 23% of all jobs use exactly this value, making it the most common choice by far.

For more stats related to time requests, have a look at the [Appendix](#time-request-details).

![time_requested_distribution_binned](../../images/hpc-data-analysis/time_requested_distribution_binned.png)
*Figure 11: Distribution of requested time limits.*

### Wait Times

A common concern among users is long queue wait times. Table 4 and Figure 12 show the picture: the distribution is heavily right-skewed, with a median wait of just 5 minutes — most jobs start almost immediately. A long tail of outliers pulls the mean to 5.5 hours, but excluding the top 5% brings it down to 1.7 hours. Extreme waits affect only a small minority of jobs.

This is overall good news! Yet tighter resource requests could make this even better for everyone.

|  Statistic  |  Wait time for all jobs   | ≤ 95th percentile |
|:------|:-----------:|:-----------------:|
| Median |   5.0 min   |      3.7 min      |
| Mean   |  5.5 hours  |     1.7 hours     |
| Max    | 1,722 hours |    26.4 hours     |

*Table 4: Wait times for a job to get started.*

![wait_time_distribution](../../images/hpc-data-analysis/wait_time_distribution.png)
*Figure 12: Wait time distribution.*

## How Much of Those Resources Goes to Waste?

So far, we've looked at efficiency distributions and what people are requesting. But how much waste does that translate into in practice?

The efficiency numbers above translate into concrete waste. Figure 13 breaks it down using the same five-tier scale introduced earlier. (Time efficiency is excluded here because, as noted above, unused time doesn't block resources — it's CPU and memory over-requesting that directly reduces cluster capacity.)

For CPU, the picture is mixed: about 43% of jobs fall into the "excellent" category (80–100% of resources requested are also used), but a similar share (31%) lands in "very poor" (below 20%), with relatively few jobs in between. For memory, 72% of jobs use less than 20% of the memory requested, and only 4% use 80% or more.

Among multi-CPU jobs specifically, ~620k (51%) fall into the "very poor" category — using less than 20% of their requested CPU time. Among jobs requesting more than 1 GiB of memory, ~1.3M (69%) are likewise "very poor".

![severity_barplot](../../images/hpc-data-analysis/severity_barplot.png)
*Figure 13: Waste severity breakdown. Each bar shows the percentage of jobs falling into each waste category. Labels on top of the bars indicate the approximate job count and percentage per category.*

The [Appendix](#requested-vs-used) includes scatter plots of requested vs. actually used resources for CPU, memory, and time, showing where individual jobs land relative to the ideal 1:1 mapping and offering a more granular view than the grouped distributions above.

## Efficiency By Faculty

So far, we've looked at efficiency, resource requests, and waste across all jobs — but different research groups use the cluster in different ways. Do some faculties fare better than others?

To understand where efficiency varies, we mapped users to faculties via King's Active Directory. The headline finding: CPU efficiency varies substantially between faculties, but memory and time inefficiency are shared across all groups — every faculty over-requests memory and time by a wide margin.

The abbreviations used in the plots below are:

| Abbreviation | Faculty |
|:------------:|:--------|
| **NMES**     | Faculty of Natural, Mathematical & Engineering Sciences |
| **IoPPN**    | Institute of Psychiatry, Psychology & Neuroscience |
| **DOCS**     | Faculty of Dentistry, Oral & Craniofacial Sciences |
| **LSM**      | Faculty of Life Sciences & Medicine |
| **SSPP**     | Faculty of Social Science & Public Policy |
| **KBS**      | King's Business School |
| **AH**       | Faculty of Arts & Humanities |
| **DPSL**     | The Dickson Poon School of Law |
| **Other**    | IT, Research Management & Innovation, Students & Education, and "Other" (a literal category in Active Directory) |
| **N/A**      | Unknown faculty (Active Directory lookup failed) |

### Job Outcomes by Faculty

Let's first look at who submits the most jobs. Figure 14 shows the outcome of all ~3.7 million submitted jobs, broken down by faculty. The four largest users by job volume are NMES, IoPPN, DOCS, and LSM.

![faculty_job_outcomes_merged](../../images/hpc-data-analysis/faculty_job_outcomes_merged.png)
*Figure 14: Job outcomes by faculty. Numbers at the tip of each bar show the approximate total number of jobs submitted per faculty.*

### Efficiency Results by Faculty

How do faculties compare on efficiency? Figure 15 shows boxplots of CPU, memory, and time efficiency by faculty, with mean values (diamonds) and 95% confidence intervals overlaid. Faculties with fewer than 50 jobs are excluded.

For CPU efficiency, SSPP leads with over 80%, followed closely by NMES (who submit far more jobs). Roughly half the faculties sit above 50% CPU efficiency, while the rest fall below. For memory efficiency, the picture is more uniformly bleak: no faculty exceeds 25% on average. Similarly, time efficiency is universally low, with no faculty exceeding 20% on average.

![faculty_efficiency_boxplots](../../images/hpc-data-analysis/faculty_efficiency_boxplots.png)
*Figure 15: CPU, memory, and time efficiency by faculty, ranked from highest to lowest average. Boxes show the interquartile range (25th–75th percentile) with the median as a line. Whiskers extend to 1.5× the interquartile range. Diamonds show the mean with 95% confidence intervals. Faculties with fewer than 50 jobs are excluded.*

Looking across all three metrics, NMES and SSPP consistently rank near the top — though even they have substantial room to improve on memory and time.

## Summary of Further Analysis

Beyond the headline efficiency numbers, the additional analysis reveals two further patterns:

- **CPU requests cluster around round numbers and powers of two**. There are good reasons to choose powers of two (see [previous section on CPU requests](#cpus)), but whether a particular job actually benefits depends on the code and the computational pipeline.
- **CPU efficiency varies by faculty; memory and time efficiency do not.** Some faculties achieve genuinely good CPU efficiency, while others are poor — but memory and time over-requesting are shared habits across all groups.

## Future Work

This analysis establishes a baseline for cluster efficiency during July–December 2025. We plan to revisit the data in six months to assess whether interventions — this blog post, `seff`, HPC training workshops, and memory enforcement (enabled January 2026) — are making a measurable difference to job efficiency over time.

We're also looking at extending this analysis to **GPU efficiency**, since GPU jobs are among the most resource-intensive on the cluster and `seff` already supports GPU metrics.

---

## Appendix

## Data Source and Code

All data in this post comes from the Slurm accounting database (MySQL) for job metrics, with faculty mapping via King's Active Directory (LDAP). All stats and plots have been generated using this [analysis code](https://github.com/nadinespy/hpc-data-analysis) — a Python pipeline that extracts job-level resource usage from Slurm's accounting database and calculates CPU, memory, and time efficiency metrics, both per job and aggregated by faculty.

## Efficiency Metrics

We use **average efficiency** — the mean of per-job efficiency values. Each job counts equally regardless of size, answering the question "what's the typical job's efficiency?".

### CPU Efficiency Formula

```text
CPU Efficiency = CPU time used / (Elapsed time × CPUs requested) × 100
```

- **CPU time used**: the total time CPUs spent doing work for the job
- **Elapsed time**: wall-clock duration of the job
- **CPUs requested**: the number of CPU cores requested at submission

A job requesting 4 CPUs for 1 hour has 4 CPU-hours available. If it uses 2 CPU-hours of actual computation, its CPU efficiency is 50%.

### Memory Efficiency Formula

```text
Memory Efficiency = Peak memory used / Requested memory × 100
```

- **Peak memory used**: the maximum memory the job actually used at any point during its run
- **Requested memory**: the amount of memory requested at submission

The data in this analysis is from a period when memory limits were **not enforced** — jobs could exceed their requested memory without being killed. Memory enforcement was enabled at the end of January 2026; jobs exceeding their memory request will now be terminated.

### Time Efficiency Formula

```text
Time Efficiency = Elapsed time / Time limit × 100
```

Measures what fraction of the requested wall-clock time was actually used.

## Units

Slurm and this analysis report memory in GiB (gibibytes, powers of 1024), not GB (gigabytes, powers of 1000). 1 GiB = 1.074 GB — a small difference, but worth noting for precision.

## Job States Included

Only jobs in specific terminal states are included in the efficiency analysis:

|        State         | Included | Why |
|:--------------------:|:--------:|:----|
| COMPLETED            |   Yes    | Job finished normally — clean efficiency data |
| TIMEOUT              |   Yes    | Job ran its full requested time — indicates time under-requesting |
| OUT_OF_MEMORY        |   Yes    | Job hit memory limits — indicates memory under-requesting |
| CANCELLED            |    No    | Intentional user action — resource usage not representative |
| FAILED               |    No    | Abnormal termination — resource usage not representative |
| NODE_FAIL, PREEMPTED |    No    | Infrastructure issues — not the user's fault |

These filters ensure we only compute efficiency for jobs that ran long enough to produce meaningful resource usage data.

## Excluded Jobs

We filtered out jobs with efficiency above 100%, which can arise from Slurm allocating slightly more resources than requested, or from historically unenforced memory limits. We also excluded a small number of jobs with null efficiency values (e.g., due to zero elapsed time). Specifically:

- CPU efficiencies are based on ~2.8M jobs, after excluding ~11.4k (0.4%) with null and ~97.3k (3.4%) with >100% CPU efficiency from the ~2.9M eligible jobs.
- Memory efficiencies are based on ~2.6M jobs, after excluding ~270 (<0.01%) with null and ~274.2k (9.5%) with >100% memory efficiency.
- Time efficiencies are based on ~2.8M jobs, after excluding ~274 (<0.01%) with null, and ~73.5k (2.5%) with >100% time efficiency. ~8.9k (0.3%) were additionally excluded because the time limit was not explicitly set by the user (e.g., jobs that inherited a partition-specific maximum rather than a user-specified limit).

CPU, memory, and time efficiencies are filtered independently — a job can appear in one metric's plots but not another's.

## Time Request Details

The median time request is 10 hours (even though 24h is the most common single value — enough short requests are pulling the median down below it); the 95th percentile is 2 days. A small number of jobs (~9.6k, 0.3%) had time limits exceeding 48 hours, with limits up to ~21 days. These ran in partitions with higher limits than the standard configuration.

### Backfill Scheduling

When a large job is next in the queue but waiting for enough resources to free up, the scheduler doesn't necessarily hold everything behind it. Instead, it looks further down the queue for smaller jobs that can finish before the large job's resources become available, and pulls them forward to fill the gap. This is backfill scheduling — it keeps resources productive during what would otherwise be idle time.

The scheduler has no way of knowing how long a job will actually run; all it has is the requested wall time. A 30-minute job with the 24-hour default therefore looks like a 24-hour job and will rarely fit any gap. Tightening your time limit makes your job eligible for backfill slots it would otherwise be skipped for.

## CPU-Memory Correlation Methodology

Figure 8 uses two statistical tools suited to skewed, non-normal distributions. The **Spearman rank correlation** (ρ) measures how consistently one variable increases as the other does, without assuming a straight-line relationship (unlike the more common Pearson correlation, which only captures linear trends). The **LOWESS trend line** (locally weighted scatterplot smoothing) fits a flexible curve through the data by averaging nearby points, revealing the local relationship between CPU and memory efficiency without imposing a particular shape.

The result: a moderate positive correlation (ρ ≈ 0.4). The LOWESS curve flattens above ~60% CPU efficiency, showing that among CPU-efficient jobs, memory efficiency does not consistently improve.

## Requested vs. Used

Figures A1–A3 show a random sample of 80,000 jobs each, with what was requested on the x-axis and what was actually used on the y-axis — for CPU, memory, and time, respectively. Points on the diagonal represent perfect efficiency; the further a point falls below it, the more was wasted. The colour indicates efficiency percentage.

For all three resources, the scatter falls predominantly below the diagonal — what's requested is often orders of magnitude more than what's used. A few patterns stand out:

- CPU time (Figure A1): a band of efficient jobs hugs the diagonal, mostly at smaller request sizes — these are largely the single-CPU jobs we saw performing well earlier. Below them, a broad cloud of jobs requests hours to thousands of hours of CPU time but uses only a small fraction.
- Memory (Figure A2): dense vertical columns at round request values (1, 4, 8, 64, 100 GiB) show that within each common request size, actual usage spans orders of magnitude. At the far right, jobs requesting TiBs of memory use only MiBs to a few GiBs — these are the extreme over-reservations from the main text.
- Wall time (Figure A3): vertical lines at common time limits (1 h, 6 h, 24 h, 2 days) dominate. The 24-hour default stands out most: a dense column of jobs that requested a full day but finished anywhere from seconds to a few hours.

![cpu_requested_vs_used](../../images/hpc-data-analysis/cpu_requested_vs_used.png)
*Figure A1: CPU time — requested vs used. Each dot is one job; colour indicates efficiency.*

![mem_requested_vs_used](../../images/hpc-data-analysis/mem_requested_vs_used.png)
*Figure A2: Memory — requested vs used. Each dot is one job; colour indicates efficiency.*

![time_requested_vs_used](../../images/hpc-data-analysis/time_requested_vs_used.png)
*Figure A3: Wall time — requested vs used. Each dot is one job; colour indicates efficiency.*