# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/open-energy-transition/clean-firm-techs-eu>
#
# SPDX-License-Identifier: MIT
"""
Plots the change in system costs of low and high runs against a reference run.

Reads the ``system_costs.csv`` written by ``export_statistics_summary`` for the
scenario set, which includes the reference run
(``catf_model.post_processing.sensitivity.reference_run``, the baseline). Each
entry of
``catf_model.post_processing.sensitivity.pairs`` is a pair of a low and a high
run. The figure has one panel per planning horizon with one row per pair,
showing the low and high run as change in system costs relative to the
reference in percent and annotated in bn EUR/a. Rows are sorted by the mean
spread between the high and low run over all horizons.

System costs are the sum of the cost components in
``catf_model.post_processing.sensitivity.costs`` (columns of
``system_costs.csv``). By default this includes the CO2 cap penalty: it is part
of the objective, so leaving it out can make a run look cheaper only because it
pays more penalty for emissions above the cap.
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


def system_costs(path: str, components: list[str]) -> pd.Series:
    """Returns the sum of the cost components in bn EUR/a per run and planning horizon."""
    costs = pd.read_csv(path, index_col=["scenario", "planning_horizon"])
    return costs[components].sum(axis=1)


def signed(value: float) -> str:
    """Formats a change in bn EUR/a with sign, without "-0" for values close to zero."""
    return f"{round(value) + 0:+,.0f}" if round(value) else "0"


def sensitivity_changes(
    costs: pd.Series, reference: pd.Series, pairs: dict[str, list[str]]
) -> pd.DataFrame:
    """
    Returns the change of the low and high run of each pair from the reference
    per horizon, in bn EUR/a and in percent, with the pairs sorted by spread.
    """
    missing = sorted(
        {r for runs in pairs.values() for r in runs} - set(costs.index.unique(0))
    )
    if missing:
        raise ValueError(f"Runs of the sensitivity pairs not found: {missing}")

    rows = []
    for label, (low, high) in pairs.items():
        for case, run in [("low", low), ("high", high)]:
            change = costs[run] - reference
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
    df = pd.concat(rows, ignore_index=True)

    spread = df.pivot_table(
        index="sensitivity", columns="case", values="change", aggfunc="mean"
    )
    order = (spread.high - spread.low).abs().sort_values(ascending=False).index
    df["sensitivity"] = pd.Categorical(df.sensitivity, categories=order, ordered=True)
    return df.sort_values(["sensitivity", "planning_horizon"])


def plot_changes(
    df: pd.DataFrame, reference: pd.Series, components: list[str]
) -> plt.Figure:
    """Plots the low and high change per sensitivity, one panel per horizon."""
    horizons = sorted(df.planning_horizon.unique())
    labels = list(df.sensitivity.cat.categories)
    y = np.arange(len(labels))[::-1]

    limit = df.relative.abs().max() * 1.25
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
        for yi, (_, row) in zip(y, low.iterrows()):
            ax.annotate(
                signed(row.change),
                (row.relative, yi),
                xytext=(0, -9),
                textcoords="offset points",
                ha="center",
                va="top",
                fontsize=7,
                color=TEXT_SECONDARY,
            )
        for yi, (_, row) in zip(y, high.iterrows()):
            ax.annotate(
                signed(row.change),
                (row.relative, yi),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
                color=TEXT_SECONDARY,
            )

        # Reference line above the grid lines (zorder 1.5), below the pairs
        ax.axvline(0, color=TEXT_PRIMARY, linewidth=0.9, linestyle="--", zorder=1.8)
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-0.7, len(labels) - 0.3)
        ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0f}%" if v else "0")
        ax.set_title(
            f"{horizon}\nReference: {reference[horizon]:,.0f} bn EUR/a",
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
        f"Change in annual system costs ({' + '.join(components)}) from reference (%), "
        "annotated in bn EUR/a",
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
            "plot_sensitivity_system_costs",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.sensitivity.yaml",
            ],
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    spec = snakemake.params.sensitivity
    components = spec["costs"]
    costs = system_costs(snakemake.input.costs, components)
    reference = costs.xs(spec["reference_run"])

    df = sensitivity_changes(costs, reference, spec["pairs"])
    fig = plot_changes(df, reference, components)
    fig.savefig(snakemake.output.plot, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Plotted the sensitivity of system costs to {snakemake.output.plot}.")

    df.round({"change": 2, "relative": 3}).to_csv(snakemake.output.csv, index=False)
    logger.info(f"Exported the sensitivity of system costs to {snakemake.output.csv}.")
