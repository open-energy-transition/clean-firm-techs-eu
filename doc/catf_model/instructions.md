<!-- SPDX-FileCopyrightText: Contributors to clean-techs-firm-eu <https://github.com/open-energy-transition/clean-firm-techs-eu/> -->
<!-- SPDX-FileCopyrightText: Open Energy Transition gGmbH -->
<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Instructions to run the model

## Configuration files

The CATF model is built from stacked config files in `config/catf_model/`. Files listed later override earlier ones.

| File | Purpose |
|---|---|
| `config.base.yaml` | Base CATF assumptions (clustering, costs, solver settings). Always first. |
| `config.initial.yaml` | Turns on the initial scenario set (`run.prefix: initial`, `run.name: all`) defined in `scenarios.initial.yaml`. |
| `scenarios.initial.yaml` | Scenario definitions: `baseline`, `high-need`, `low-need`. |
| `config.test.yaml` | Optional overlay for quick tests: one week of snapshots, 28 time segments, `run.prefix: test`. |

Scenarios in `scenarios.initial.yaml`:

- **baseline**: default PyPSA-Eur demand response; cost file `custom_costs_x1.0.csv`.
- **high-need**: investment costs of established technologies and the gas price +33% (`x1.33`); household, services and rail electricity load +10%; EV demand response reduced to 25% of BEVs.
- **low-need**: costs and gas price -25% (`x0.75`); electricity load -10%; residential heat demand response on.

The scaled cost files are built automatically by rule `build_cost_sensitivity` (`rules/catf_model/cost_sensitivity.smk`), which reads the factor from the file name.

## Running with pixi tasks

The tasks are defined in `pixi.toml` under `[feature.catf-model.tasks]` and run in the `catf-model` environment.

| Task | What it does |
|---|---|
| `catf-initial` | Solves all initial scenarios (`solve_networks`). |
| `catf-initial-test` | Same, with the `config.test.yaml` overlay (fast test run). |
| `catf-postprocess` | Runs CATF post-processing (`catf_post_processing`) on the initial scenarios. |
| `catf-postprocess-test` | Post-processing for the test run. |

Run the test version first to check the workflow end to end:

```bash
pixi run -e catf-model catf-initial-test
```

Full run, then post-processing:

```bash
pixi run -e catf-model catf-initial
```

```bash
pixi run -e catf-model catf-postprocess
```

Any extra arguments are passed straight to Snakemake. For example, a dry run that lists the jobs without running them:

```bash
pixi run -e catf-model catf-initial -n
```

Outputs are written under `resources/<prefix>/` and `results/<prefix>/`, with `<prefix>` being `initial` for full runs and `test` for test runs. Each scenario gets its own subfolder.

### Running a subset of scenarios

`config.initial.yaml` sets `run.name: all`, which runs every scenario in `scenarios.initial.yaml`. To run only some of them, change it to a list in a local copy of the overlay (or in the file itself):

```yaml
run:
  name:
  - baseline
  - high-need
```

### Adding a scenario

Add a new top-level entry to `scenarios.initial.yaml`. Only the settings that differ from `config.base.yaml` are needed. For a different cost sensitivity, point `costs.custom_cost_fn` at a file with the new factor, e.g. `resources/{prefix}/{run}/custom_costs_x1.5.csv`. Use `{prefix}` and `{run}` rather than fixed names so the test overlay keeps working.

## Running on a SLURM cluster

Locally, the pixi tasks run every job on the current machine (`-call` uses all cores). On a SLURM cluster, the `profiles/catf_slurm` profile submits each Snakemake job as its own `sbatch` job instead. The solves for each scenario and planning horizon do not depend on each other, so they run in parallel. Scenario-independent steps (clustering, renewable availability, etc.) are shared between scenarios and run only once (`run.shared_resources.policy: base`).

### Starting a run

Run Snakemake from a login node inside `tmux` or `screen`. It has to stay alive for the whole run to submit and track jobs.

```bash
tmux new -s catf
```

Add `--profile profiles/catf_slurm` to any pixi task:

```bash
pixi run -e catf-model catf-initial-test --profile profiles/catf_slurm
```

```bash
pixi run -e catf-model catf-initial --profile profiles/catf_slurm
```

