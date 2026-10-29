# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/open-energy-transition/clean-firm-techs-eu>
#
# SPDX-License-Identifier: MIT
"""
Plots the installed capacity, generation and demand across runs and planning horizons.

Reads the long-format summary written by ``export_statistics_summary`` and
writes one figure per statistic. Each figure has one panel per carrier stacked
vertically (capacity: Electricity, Heat, Hydrogen, Fuels & conversion, Storage;
generation: the same without Storage; demand: a single panel). All panels share
the x-axis, with one bar per planning horizon grouped by scenario. Each panel
has its own unit, so only values of the same unit are stacked; the total is
annotated above each bar. All values are positive, as exported by
``export_statistics``.
"""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

# Colors for the plot layout, text and grid
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

# Group of carriers not assigned in the config, as in export_statistics_summary
OTHER = "Other"
OTHER_COLOR = "#898781"

# Gap between scenario groups on the x-axis, in bar widths
GROUP_GAP = 0.8

# Groups below this share of the largest bar of a panel in every bar are merged into "Other"
OTHER_THRESHOLD = 0.01

# Height of one panel in inches
PANEL_HEIGHT = 2.6

TITLES = {
    "capacities": "Installed capacity",
    "generation": "Generation",
    "demand": "Final demand",
}


def x_positions(index: pd.MultiIndex) -> np.ndarray:
    """Returns bar positions with a gap between scenario groups."""
    x, pos = [], 0.0
    for i, (run, _) in enumerate(index):
        if i and run != index[i - 1][0]:
            pos += GROUP_GAP
        x.append(pos)
        pos += 1
    return np.array(x)


def plot_panel(ax: plt.Axes, table: pd.DataFrame, x: np.ndarray, colors: dict) -> None:
    """Plots the groups of one panel as stacked bars and annotates the totals. All values are positive."""
    bottom = np.zeros(len(table))
    for group in table.columns:
        values = table[group].to_numpy()
        ax.bar(
            x,
            values,
            bottom=bottom,
            width=0.75,
            color=colors.get(group, OTHER_COLOR),
            edgecolor=SURFACE,
            linewidth=0.5,
            label=group,
            zorder=2,
        )
        bottom += values

    for xi, total in zip(x, bottom):
        ax.annotate(
            f"{total:,.0f}" if total >= 10 else f"{total:.1f}",
            (xi, total),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7,
            color=TEXT_SECONDARY,
        )
    ax.set_ylim(top=bottom.max() * 1.15)

    # Legend from top to bottom of the stack
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles[::-1],
        labels[::-1],
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        frameon=False,
        fontsize=7,
        labelcolor=TEXT_PRIMARY,
    )


def plot_statistic(data: pd.DataFrame, order: list[str], colors: dict, title: str) -> plt.Figure:
    """Plots one panel per carrier, with scenarios and planning horizons on the shared x-axis."""
    panels = data.panel.unique()
    bars = data.set_index(["scenario", "planning_horizon"]).index.unique()
    x = x_positions(bars)

    fig, axes = plt.subplots(
        len(panels),
        1,
        figsize=(3 + 0.55 * len(bars), PANEL_HEIGHT * len(panels)),
        sharex=True,
        squeeze=False,
        facecolor=SURFACE,
        layout="constrained",
    )
    axes = axes[:, 0]

    for ax, panel in zip(axes, panels):
        rows = data[data.panel == panel]
        # One row per (scenario, horizon), one column per group in the configured order
        table = rows.pivot_table(
            index=["scenario", "planning_horizon"],
            columns="group",
            values="value",
            aggfunc="sum",
            fill_value=0.0,
        ).reindex(bars, fill_value=0.0)
        threshold = OTHER_THRESHOLD * table.sum(axis=1).max()
        small = [g for g in table if g != OTHER and table[g].max() < threshold]
        if small:
            table[OTHER] = table.get(OTHER, 0) + table[small].sum(axis=1)
            table = table.drop(columns=small)
        table = table[[g for g in [*order, OTHER] if g in table and table[g].max() > 0]]

        plot_panel(ax, table, x, colors)
        if len(panels) > 1:
            ax.set_title(panel, loc="left", fontsize=10, fontweight="bold", color=TEXT_PRIMARY)
        ax.set_ylabel(rows.unit.iloc[0], color=TEXT_SECONDARY, fontsize=9)
        ax.set_facecolor(SURFACE)
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=8, length=0)
        for side in ["top", "right", "left"]:
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(BASELINE)

        # Vertical break between scenario groups, in the middle of each gap
        runs = bars.get_level_values("scenario")
        for i in range(1, len(x)):
            if runs[i] != runs[i - 1]:
                ax.axvline((x[i - 1] + x[i]) / 2, color=BASELINE, linewidth=0.8, linestyle="--", zorder=1)

    # Planning horizons as tick labels, scenario names centred below each group
    ax = axes[-1]
    ax.set_xticks(x, bars.get_level_values("planning_horizon").astype(str))
    for run in runs.unique():
        ax.text(
            x[runs == run].mean(),
            -0.25,
            run,
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=9,
            color=TEXT_PRIMARY,
        )

    fig.suptitle(title, x=0.01, ha="left", fontsize=12, color=TEXT_PRIMARY)
    return fig


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "plot_statistics",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.initial.yaml",
            ],
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    groups = snakemake.params.statistics["groups"]
    sectors = snakemake.params.sectors["demand"]
    colors = {g: spec["color"] for g, spec in groups.items()} | snakemake.params.colors
    orders = {"capacities": list(groups), "generation": list(groups), "demand": list(sectors)}

    summary = pd.read_csv(snakemake.input.statistics_summary)

    for statistic, order in orders.items():
        data = summary[summary.statistic == statistic]
        if data.empty:
            raise ValueError(f"No '{statistic}' rows in {snakemake.input.statistics_summary}.")

        output = getattr(snakemake.output, statistic)
        fig = plot_statistic(data, order, colors, TITLES[statistic])
        fig.savefig(output, dpi=200, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Plotted {statistic} to {output}.")
