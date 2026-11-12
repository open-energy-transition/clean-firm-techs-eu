# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/open-energy-transition/clean-firm-techs-eu>
#
# SPDX-License-Identifier: MIT
"""
Plots the transmission expansion of runs (e.g. lcopt, lvopt) compared to a
reference run (e.g. baseline).

Reads the CSVs written by ``export_transmission`` for each run and planning
horizon. The transmission volume is the capacity times the length of each AC
line and DC link, in TWkm. The figure has two panels sharing the x-axis, with
one bar per planning horizon grouped by run, stacked by AC and DC:

- Transmission volume of each run. The dashed line is today's grid (the
  existing capacity of the reference run in the first planning horizon).
- Change of the volume compared to the reference run in the same horizon.

The volumes are also written to a CSV.
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

# Gap between run groups on the x-axis, in bar widths
GROUP_GAP = 0.8


def read_volumes(path: str) -> pd.Series:
    """Returns the existing and optimal transmission volume per carrier in TWkm."""
    df = pd.read_csv(path)
    volume = df[["existing", "optimal"]].mul(df.length, axis=0) / 1e6
    return volume.groupby(df.carrier).sum().stack()


def x_positions(index: pd.MultiIndex) -> np.ndarray:
    """Returns bar positions with a gap between run groups."""
    x, pos = [], 0.0
    for i, (run, _) in enumerate(index):
        if i and run != index[i - 1][0]:
            pos += GROUP_GAP
        x.append(pos)
        pos += 1
    return np.array(x)


def plot_stacked(
    ax: plt.Axes, table: pd.DataFrame, x: np.ndarray, colors: dict, labels: list
) -> None:
    """Plots stacked bars, positive values upwards and negative ones downwards, and annotates each bar."""
    top, bottom = np.zeros(len(table)), np.zeros(len(table))
    for carrier in table.columns:
        values = table[carrier].to_numpy()
        base = np.where(values >= 0, top, bottom)
        ax.bar(
            x,
            values,
            bottom=base,
            width=0.75,
            color=colors.get(carrier),
            edgecolor=SURFACE,
            linewidth=0.5,
            label=carrier,
            zorder=2,
        )
        top += np.clip(values, 0, None)
        bottom += np.clip(values, None, 0)

    for xi, hi, lo, label in zip(x, top, bottom, labels):
        if not label:
            continue
        down = abs(lo) > hi
        ax.annotate(
            label,
            (xi, lo if down else hi),
            xytext=(0, -2 if down else 2),
            textcoords="offset points",
            ha="center",
            va="top" if down else "bottom",
            fontsize=7,
            color=TEXT_SECONDARY,
        )


def style_axis(ax: plt.Axes, ylabel: str) -> None:
    """Applies the layout of the CATF comparison plots."""
    ax.set_ylabel(ylabel, color=TEXT_SECONDARY, fontsize=9)
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=8, length=0)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)


def plot_transmission(
    volumes: pd.DataFrame, reference: str, colors: dict
) -> plt.Figure:
    """Plots the transmission volume per run and its change compared to the reference run."""
    optimal = volumes.xs("optimal", level="value", axis=1)
    carriers = [c for c in colors if c in optimal] + [
        c for c in optimal if c not in colors
    ]
    optimal = optimal[carriers]
    change = optimal - optimal.loc[reference].reindex(
        optimal.index, level="planning_horizon"
    )
    first_horizon = volumes.index.get_level_values("planning_horizon").min()
    today = volumes.xs("existing", level="value", axis=1).loc[
        (reference, first_horizon)
    ]

    bars = optimal.index
    runs = bars.get_level_values("run")
    x = x_positions(bars)

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(3 + 0.55 * len(bars), 6),
        sharex=True,
        facecolor=SURFACE,
        layout="constrained",
    )

    # Transmission volume, with today's grid as a reference line
    ax = axes[0]
    totals = optimal.sum(axis=1)
    plot_stacked(ax, optimal, x, colors, [f"{v:,.0f}" for v in totals])
    ax.axhline(
        today.sum(), color=TEXT_SECONDARY, linestyle="--", linewidth=1, zorder=3
    )
    ax.annotate(
        f"today's grid: {today.sum():,.0f} TWkm",
        (x[-1] + 0.5, today.sum()),
        xytext=(0, 2),
        textcoords="offset points",
        ha="right",
        va="bottom",
        fontsize=7,
        color=TEXT_SECONDARY,
    )
    ax.set_ylim(top=max(totals.max(), today.sum()) * 1.15)
    ax.set_title(
        "Transmission volume", loc="left", fontsize=10, fontweight="bold", color=TEXT_PRIMARY
    )
    style_axis(ax, "TWkm")
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

    # Change compared to the reference run, in TWkm and percent of its volume
    ax = axes[1]
    reference_totals = totals.loc[reference].reindex(
        bars, level="planning_horizon"
    )
    change_totals = change.sum(axis=1)
    labels = [
        ""
        if run == reference
        else f"{c:+,.0f} ({c / r:+.0%})"
        if r
        else f"{c:+,.0f}"
        for run, c, r in zip(runs, change_totals, reference_totals)
    ]
    plot_stacked(ax, change, x, colors, labels)
    ax.axhline(0, color=BASELINE, linewidth=0.8, zorder=1)
    span = max(change_totals.abs().max(), 1e-6)
    ax.set_ylim(
        min(change.clip(upper=0).sum(axis=1).min() * 1.3, -0.1 * span),
        max(change.clip(lower=0).sum(axis=1).max() * 1.3, 0.1 * span),
    )
    ax.set_title(
        f"Change compared to {reference}",
        loc="left",
        fontsize=10,
        fontweight="bold",
        color=TEXT_PRIMARY,
    )
    style_axis(ax, "TWkm")

    # Vertical break between run groups, in the middle of each gap
    for ax in axes:
        for i in range(1, len(x)):
            if runs[i] != runs[i - 1]:
                ax.axvline(
                    (x[i - 1] + x[i]) / 2,
                    color=BASELINE,
                    linewidth=0.8,
                    linestyle="--",
                    zorder=1,
                )

    # Planning horizons as tick labels, run names centred below each group
    ax = axes[-1]
    ax.set_xticks(x, bars.get_level_values("planning_horizon").astype(str))
    for run in runs.unique():
        ax.text(
            x[runs == run].mean(),
            -0.15,
            run,
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=9,
            color=TEXT_PRIMARY,
        )

    fig.suptitle(
        "Electricity transmission expansion",
        x=0.01,
        ha="left",
        fontsize=12,
        color=TEXT_PRIMARY,
    )
    return fig


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "plot_transmission_expansion",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.sensitivity.yaml",
            ],
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    runs = snakemake.params.runs
    horizons = snakemake.params.planning_horizons
    reference = runs[0]

    # Inputs are ordered by run, then horizon
    keys = [(run, int(h)) for run in runs for h in horizons]
    volumes = pd.DataFrame(
        {key: read_volumes(path) for key, path in zip(keys, snakemake.input.capacities)}
    ).T.fillna(0.0)
    volumes.index.names = ["run", "planning_horizon"]
    volumes.columns.names = ["carrier", "value"]

    fig = plot_transmission(volumes, reference, snakemake.params.colors)
    fig.savefig(snakemake.output.plot, dpi=200)
    plt.close(fig)

    # Volumes in TWkm, with the change compared to the reference run
    summary = volumes.stack("carrier", future_stack=True)
    summary["change to " + reference] = summary.optimal - summary.optimal.loc[
        reference
    ].reindex(summary.index.droplevel("run"), fill_value=0.0).to_numpy()
    summary.round(2).to_csv(snakemake.output.csv)

    logger.info(
        f"Plotted the transmission expansion of {runs[1:]} compared to {reference} "
        f"to {snakemake.output.plot}."
    )
