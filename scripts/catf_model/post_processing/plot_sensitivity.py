# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/open-energy-transition/clean-firm-techs-eu>
#
# SPDX-License-Identifier: MIT
"""
Plots the change of low and high runs against a reference run.

Each entry of ``catf_model.post_processing.sensitivity.pairs`` is a pair of a
low and a high run, compared with the reference run of the same scenario set
(``catf_model.post_processing.sensitivity.reference_run``, the baseline). One
figure is made per metric:

- total system costs: Capex + Opex + CO2 cap penalty (the objective; without the
  penalty, a run that emits more above the cap can look cheaper);
- Capex and Opex;
- net CO2 emissions.

Costs are read from the ``system_costs.csv`` written by
``export_statistics_summary``, emissions from the ``co2_emissions/summary.csv``
of each run. Each figure has one panel per planning horizon with one row per
pair, showing the change relative to the reference in percent, annotated in
absolute terms. Rows are sorted by the mean spread of the total system costs
between the high and low run, the same in all figures.
"""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

# Colors for the plot layout, text and grid, as in plot_statistics
SURFACE = "#ffffff"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

LOW_COLOR = "#1f6f9f"
HIGH_COLOR = "#c0602b"
LINE_COLOR = "#6b7682"

# Metric -> (name in the plot, unit)
METRICS = {
    "total_costs": ("Total system costs (Capex + Opex + CO2 cap penalty)", "bn EUR/a"),
    "capex": ("Capex", "bn EUR/a"),
    "opex": ("Opex", "bn EUR/a"),
    "co2_emissions": ("Net CO2 emissions", "MtCO2"),
}


def load_metrics(costs_fn: str, co2_fns: list[str], runs: list[str]) -> pd.DataFrame:
    """Returns the metrics per run (scenario) and planning horizon."""
    costs = pd.read_csv(costs_fn, index_col=["scenario", "planning_horizon"])
    df = pd.DataFrame(
        {
            "total_costs": costs[["Capex", "Opex", "CO2 cap penalty"]].sum(axis=1),
            "capex": costs["Capex"],
            "opex": costs["Opex"],
        }
    )
    co2 = {
        run: pd.read_csv(fn, index_col="metric").loc["net emissions"].drop("unit")
        for run, fn in zip(runs, co2_fns)
    }
    co2 = pd.concat(co2).astype(float)
    co2.index = co2.index.set_levels(co2.index.levels[1].astype(int), level=1)
    df["co2_emissions"] = co2.reindex(df.index)
    return df


def signed(value: float) -> str:
    """Formats a change with sign, without "-0" for values close to zero."""
    return f"{round(value) + 0:+,.0f}" if round(value) else "0"


def sensitivity_changes(
    values: pd.Series, pairs: dict[str, list[str]], reference_run: str
) -> pd.DataFrame:
    """
    Returns the change of the low and high run of each pair from the reference
    run per horizon, absolute and in percent.
    """
    missing = sorted(
        {r for runs in pairs.values() for r in runs} - set(values.index.unique(0))
    )
    if missing:
        raise ValueError(f"Runs of the sensitivity pairs not found: {missing}")

    reference = values.xs(reference_run)
    rows = []
    for label, (low, high) in pairs.items():
        for case, run in [("low", low), ("high", high)]:
            change = values[run] - reference
            rows.append(
                pd.DataFrame(
                    {
                        "sensitivity": label,
                        "case": case,
                        "planning_horizon": change.index,
                        "change": change.values,
                        "relative": (change / reference * 100).values,
                    }
                )
            )
    return pd.concat(rows, ignore_index=True)


def spread_order(df: pd.DataFrame) -> list[str]:
    """Returns the sensitivities sorted by the mean spread between high and low run."""
    spread = df.pivot_table(
        index="sensitivity", columns="case", values="change", aggfunc="mean"
    )
    return list((spread.high - spread.low).abs().sort_values(ascending=False).index)


def plot_changes(
    df: pd.DataFrame,
    reference: pd.Series,
    labels: list[str],
    name: str,
    unit: str,
) -> plt.Figure:
    """Plots the low and high change per sensitivity, one panel per horizon."""
    horizons = sorted(df.planning_horizon.unique())
    y = np.arange(len(labels))[::-1]

    # At least +-1% so that panels without any change still have an axis
    limit = max(df.relative.abs().max() * 1.25, 1)
    fig, axes = plt.subplots(
        1,
        len(horizons),
        figsize=(4.2 * len(horizons) + 1.5, 0.6 * len(labels) + 1.8),
        sharey=True,
        facecolor=SURFACE,
        layout="constrained",
    )
    axes = np.atleast_1d(axes)

    for ax, horizon in zip(axes, horizons):
        data = df[df.planning_horizon == horizon].set_index(["sensitivity", "case"])
        low = data.xs("low", level="case").reindex(labels)
        high = data.xs("high", level="case").reindex(labels)

        ax.hlines(
            y, low.relative, high.relative, color=LINE_COLOR, linewidth=2, zorder=2
        )
        ax.scatter(
            low.relative,
            y,
            s=55,
            facecolor=SURFACE,
            edgecolor=LOW_COLOR,
            linewidth=2,
            zorder=3,
            label="Low case",
        )
        ax.scatter(
            high.relative,
            y,
            s=50,
            marker="s",
            color=HIGH_COLOR,
            zorder=3,
            label="High case",
        )
        for points, offset, va in [(low, -9, "top"), (high, 8, "bottom")]:
            for yi, (_, row) in zip(y, points.iterrows()):
                ax.annotate(
                    signed(row.change),
                    (row.relative, yi),
                    xytext=(0, offset),
                    textcoords="offset points",
                    ha="center",
                    va=va,
                    fontsize=7,
                    color=TEXT_SECONDARY,
                )

        # Reference line above the grid lines (zorder 1.5), below the pairs
        ax.axvline(0, color=TEXT_PRIMARY, linewidth=0.9, linestyle="--", zorder=1.8)
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-0.7, len(labels) - 0.3)
        ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0f}%" if v else "0")
        ax.set_title(
            f"{horizon}\nReference: {reference[horizon]:,.0f} {unit}",
            loc="left",
            fontsize=10,
            color=TEXT_PRIMARY,
        )
        ax.set_facecolor(SURFACE)
        ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=8, length=0)
        for side in ["top", "right", "left"]:
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(BASELINE)

    axes[0].set_yticks(y, labels, fontsize=9, color=TEXT_PRIMARY)
    fig.supxlabel(
        f"Change in {name} from reference (%), annotated in {unit}",
        fontsize=9,
        color=TEXT_SECONDARY,
    )
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        names,
        loc="outside upper right",
        ncols=2,
        frameon=False,
        fontsize=8,
        labelcolor=TEXT_PRIMARY,
    )
    return fig


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "plot_sensitivity",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.sensitivity.yaml",
            ],
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    spec = snakemake.params.sensitivity
    values = load_metrics(
        snakemake.input.costs, snakemake.input.co2, snakemake.params.runs
    )

    changes = {
        metric: sensitivity_changes(
            values[metric], spec["pairs"], spec["reference_run"]
        )
        for metric in METRICS
    }
    # Same row order in all figures, by the spread of the total system costs
    labels = spread_order(changes["total_costs"])

    for metric, (name, unit) in METRICS.items():
        reference = values[metric].xs(spec["reference_run"])
        fig = plot_changes(changes[metric], reference, labels, name, unit)
        fig.savefig(snakemake.output[metric], dpi=200, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Plotted the sensitivity of {name} to {snakemake.output[metric]}.")

    df = pd.concat(changes, names=["metric"]).droplevel(1).reset_index()
    df["unit"] = df.metric.map(lambda m: METRICS[m][1])
    df.round({"change": 2, "relative": 3}).to_csv(snakemake.output.csv, index=False)
    logger.info(f"Exported the sensitivity results to {snakemake.output.csv}.")
