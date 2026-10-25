# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Plots the installed capacity by sector across runs and planning horizons.

Capacities are taken from ``n.statistics.optimal_capacity`` and grouped into
the sectors set in ``catf_model.post_processing.installed_capacity.sectors``.
Carriers not assigned to a sector are plotted as "Other" and listed in the
log. Carriers with unlimited capacity (e.g. the CO2 load sink) cannot be
plotted and are left out, also listed in the log.

Generator and storage unit capacities are their nominal power. Link
capacities are measured at the output port ``bus1`` (input capacity times
efficiency), e.g. electrical output for CCGT and CHP. Links with time-varying
efficiency, such as heat pumps, have a static efficiency of 1 and so show
their input capacity. Store energy capacities (MWh) are not included.

Writes one bar chart with a panel per run, the planning horizons on the
x-axis and the sectors stacked, and a CSV with the plotted values in GW.
"""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

# Categorical palette in fixed order, assigned to sectors in config order
SECTOR_COLORS = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#6250d6",
    "#e34948",
    "#8a5a2b",
]

# Carriers without a sector, plotted in a neutral color after all sectors
OTHER = "Other"
OTHER_COLOR = "#898781"

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"


def sum_by_carrier(*stats: pd.Series) -> pd.Series:
    """Sums statistics per carrier, whether or not they are also indexed by component."""
    # The carrier is always the last index level; it is unnamed for empty results
    summed = pd.concat([s.groupby(level=-1).sum() for s in stats])
    return summed.groupby(level=0).sum().rename_axis("carrier")


def capacity_by_carrier(n: pypsa.Network) -> pd.Series:
    """Returns the optimal capacity in MW per carrier, with links at their output port."""
    one_port = n.statistics.optimal_capacity(
        components=["Generator", "StorageUnit"], groupby="carrier", nice_names=False
    )
    links = n.statistics.optimal_capacity(
        components=["Link"], at_port="bus1", groupby="carrier", nice_names=False
    )
    return sum_by_carrier(one_port, links)


def capacity_by_sector(
    capacity: pd.Series, sectors: dict[str, list[str]]
) -> tuple[pd.Series, list[str], list[str]]:
    """
    Returns the capacity in GW per sector, the carriers plotted as "Other" and
    the carriers left out for unlimited capacity.
    """
    unlimited = capacity.index[~np.isfinite(capacity)].tolist()
    capacity = capacity[np.isfinite(capacity)]

    carrier_to_sector = {c: s for s, carriers in sectors.items() for c in carriers}
    mapped = pd.Series(capacity.index.map(carrier_to_sector), index=capacity.index)
    other = capacity.index[mapped.isna() & (capacity.abs() > 1)].tolist()
    by_sector = (
        capacity.groupby(mapped.fillna(OTHER))
        .sum()
        .reindex([*sectors, OTHER], fill_value=0.0)
    )
    return by_sector / 1e3, other, unlimited


def plot_capacity(data: pd.DataFrame, sectors: list[str]) -> plt.Figure:
    """Plots stacked sector capacities with one panel per run and horizons on the x-axis."""
    runs = data.index.unique("run")
    if len(sectors) > len(SECTOR_COLORS):
        raise ValueError(
            f"At most {len(SECTOR_COLORS)} sectors can be plotted, got {len(sectors)}."
        )
    colors = dict(zip(sectors, SECTOR_COLORS)) | {OTHER: OTHER_COLOR}
    if OTHER in data and data[OTHER].abs().sum() > 0:
        sectors = [*sectors, OTHER]

    finite = np.isfinite(data[sectors])
    if not finite.all().all():
        bad = data[sectors].columns[~finite.all()].tolist()
        logger.warning(f"Ignoring non-finite capacities in sectors: {bad}")
        data = data[sectors].where(finite, 0.0)
    if data.empty:
        raise ValueError("Nothing to plot: no capacities for any run and horizon.")
    ymax = data[sectors].sum(axis=1).max() * 1.1

    fig, axes = plt.subplots(
        1,
        len(runs),
        figsize=(1.0 + 2.4 * len(runs), 4.5),
        sharey=True,
        squeeze=False,
        facecolor=SURFACE,
    )
    for ax, run in zip(axes[0], runs):
        df = data.xs(run, level="run")
        x = range(len(df))
        bottom = pd.Series(0.0, index=df.index)
        for sector in sectors:
            ax.bar(
                x,
                df[sector],
                bottom=bottom,
                width=0.6,
                color=colors[sector],
                edgecolor=SURFACE,
                linewidth=1.5,
                label=sector,
                zorder=2,
            )
            bottom += df[sector]
        for xi, total in zip(x, bottom):
            ax.annotate(
                f"{total:,.0f}",
                (xi, total),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color=TEXT_SECONDARY,
            )

        ax.set_facecolor(SURFACE)
        ax.set_title(run, fontsize=10, color=TEXT_PRIMARY)
        ax.set_xticks(list(x), df.index.astype(str))
        ax.set_ylim(0, ymax)
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=9, length=0)
        for side in ["top", "right", "left"]:
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(BASELINE)

    axes[0, 0].set_ylabel("Installed capacity [GW]", color=TEXT_SECONDARY, fontsize=9)
    handles, labels = axes[0, 0].get_legend_handles_labels()
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

        snakemake = mock_snakemake("plot_installed_capacity")

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    sectors = snakemake.params.sectors
    runs = snakemake.params.runs
    horizons = snakemake.params.planning_horizons

    # Networks are ordered by run, then horizon (see the rule's expand)
    keys = [(run, int(h)) for run in runs for h in horizons]
    results = {}
    for key, path in zip(keys, snakemake.input.networks):
        n = pypsa.Network(path)
        results[key], other, unlimited = capacity_by_sector(
            capacity_by_carrier(n), sectors
        )
        if other:
            logger.info(f"{key}: carriers without a sector, plotted as Other: {other}")
        if unlimited:
            logger.info(f"{key}: carriers with unlimited capacity, left out: {unlimited}")

    data = pd.DataFrame(results).T
    data.index.names = ["run", "horizon"]
    data.round(1).to_csv(snakemake.output.csv)

    fig = plot_capacity(data, list(sectors))
    fig.savefig(snakemake.output.plot, dpi=200, bbox_inches="tight")
    logger.info(f"Plotted installed capacity by sector to {snakemake.output.plot}.")
