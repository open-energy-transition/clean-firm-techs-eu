# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/oet/clean-firm-techs-eu>
#
# SPDX-License-Identifier: MIT
"""
Plots each of the statistics (installed capacity, generation, demand and costs) by sector across runs and planning horizons.

Reads the long-format summary written by ``export_statistics_summary`` and
writes one stacked bar chart per statistic: the sectors stacked on the y-axis,
and on the x-axis one bar per planning horizon, grouped by scenario. Negative
values (e.g. the electricity consumption of heat pumps in generation) are
stacked below zero. The net total is annotated above each bar.
"""

import logging

import matplotlib.pyplot as plt
import matplotlib.transforms as mtransforms
import numpy as np
import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)


# Define colors for the plot layout, text and grid

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

# Carriers without a sector, plotted after all sectors. Its color comes from
# the config (key "Others"), with a neutral fallback for sectors without a color
OTHER = "Others"
OTHER_COLOR = "#898781"

# Sector mapping in the config used for each statistic, as in export_statistics_summary
SECTOR_MAPPING = {
    "capacities": "cap_and_generation",
    "generation": "cap_and_generation",
    "demand": "demand",
}

# Gap between scenario groups on the x-axis, in bar widths
GROUP_GAP = 0.8

LABELS = {
    "capacities": "Installed capacity",
    "generation": "Generation",
    "demand": "Demand",
    "costs": "Costs",
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


def plot_statistic(
    data: pd.DataFrame, sectors: list[str], colors: dict[str, str], ylabel: str
) -> plt.Figure:
    """Plots stacked sector values with scenarios and planning horizons on the x-axis."""
    finite = np.isfinite(data["value"])
    if not finite.all():
        bad = data[~finite]
        logger.warning(f"Ignoring non-finite values in sectors: {bad.Sector.unique()}")
        data = data[finite]
    if data.empty:
        raise ValueError("Nothing to plot: no values for any run and horizon.")

    # One row per (scenario, horizon) in the order of the summary, one column per sector
    table = data.pivot_table(
        index=["scenario", "planning_horizon"],
        columns="Sector",
        values="value",
        aggfunc="sum",
        fill_value=0.0,
        sort=False,
    )
    order = [*sectors, OTHER]
    table = table.reindex(
        columns=[s for s in order if s in table.columns]
        + [s for s in table.columns if s not in order]
    )

    x = x_positions(table.index)
    fig, ax = plt.subplots(figsize=(1.5 + 0.55 * len(table), 4.5), facecolor=SURFACE)

    pos_bottom = np.zeros(len(table))
    neg_bottom = np.zeros(len(table))
    for sector in table.columns:
        values = table[sector].to_numpy()
        ax.bar(
            x,
            values,
            bottom=np.where(values >= 0, pos_bottom, neg_bottom),
            width=0.75,
            color=colors.get(sector, OTHER_COLOR),
            edgecolor=SURFACE,
            linewidth=1.0,
            label=sector,
            zorder=2,
        )
        pos_bottom += values.clip(min=0)
        neg_bottom += values.clip(max=0)

    for xi, top, total in zip(x, pos_bottom, table.sum(axis=1)):
        ax.annotate(
            f"{total:,.0f}",
            (xi, top),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7,
            color=TEXT_SECONDARY,
        )

    # Planning horizons as tick labels, scenario names centred below each group
    ax.set_xticks(x, table.index.get_level_values("planning_horizon").astype(str))
    trans = mtransforms.blended_transform_factory(ax.transData, ax.transAxes)
    runs = table.index.get_level_values("scenario")
    for run in runs.unique():
        centre = x[runs == run].mean()
        ax.text(
            centre,
            -0.1,
            run,
            transform=trans,
            ha="center",
            va="top",
            fontsize=9,
            color=TEXT_PRIMARY,
        )

    # Vertical break between scenario groups, in the middle of each gap
    for i in range(1, len(x)):
        if runs[i] != runs[i - 1]:
            ax.axvline(
                (x[i - 1] + x[i]) / 2,
                color=BASELINE,
                linewidth=0.8,
                linestyle="--",
                zorder=1,
            )

    if (neg_bottom < 0).any():
        ax.axhline(0, color=BASELINE, linewidth=0.8, zorder=3)
    ax.set_facecolor(SURFACE)
    ax.set_ylabel(ylabel, color=TEXT_SECONDARY, fontsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=8, length=0)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)

    handles, labels = ax.get_legend_handles_labels()
    fig.legend(
        handles[::-1],
        labels[::-1],
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=9,
        labelcolor=TEXT_PRIMARY,
    )
    fig.tight_layout()
    return fig


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("plot_statistics")

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    sectors = snakemake.params.sectors
    colors = snakemake.params.colors
    statistics = snakemake.params.statistics

    df_summary = pd.read_csv(snakemake.input.statistics_summary)

    for stat in statistics:
        df_stat = df_summary.query("statistic == @stat and Sector != @OTHER")
        if df_stat.empty:
            raise ValueError(
                f"No '{stat}' rows in {snakemake.input.statistics_summary}; "
                f"available: {df_summary.statistic.unique().tolist()}."
            )
        ylabel = f"{LABELS.get(stat, stat.capitalize())} [{df_stat.unit.iloc[0]}]"

        output = getattr(snakemake.output, stat)
        sector_order = list(sectors[SECTOR_MAPPING.get(stat, "cap_and_generation")])
        fig = plot_statistic(df_stat, sector_order, colors, ylabel)
        fig.savefig(output, dpi=200, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Plotted {stat} by sector to {output}.")
