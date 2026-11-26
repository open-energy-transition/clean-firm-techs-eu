# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Plots the use of nuclear CHP for electricity and heat per node of one run.

Reads the CSVs of ``export_nuclear_chp`` and draws one panel per planning
horizon with nuclear CHP: a horizontal bar per node, stacked into electricity
and district heat output in TWh per year, labelled with the heat share of the
output. Nodes are labelled by country name, numbered if a country has several
nodes. Nodes are sorted by total output over all horizons. Horizons without
nuclear CHP are left out; if no horizon has any, the figure says so.
"""

import logging

import country_converter as coco
import matplotlib.pyplot as plt
import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

# Colors for the plot layout, text and grid, as in plot_energy_balances
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"

# Electricity and heat of nuclear CHP (validated pair: lightness, chroma, CVD)
SERIES = {
    "electricity_TWh": ("Electricity", "#e3a857"),
    "heat_TWh": ("District heat", "#8a4b00"),
}
# Nodes with a total output below this share of the largest are left out
MIN_SHARE = 1e-3


def country_labels(countries: pd.Series) -> pd.Series:
    """
    Returns a label per node: its country name, numbered by node if a country
    has several nodes (e.g. "Germany 1", "Germany 2").
    """
    codes = sorted(countries.unique())
    # not_found=None keeps the code; a single code is returned as a string
    converted = coco.convert(codes, to="name_short", not_found=None)
    if isinstance(converted, str):
        converted = [converted]
    names = dict(zip(codes, converted))
    labels = countries.map(names).sort_index()
    count = labels.groupby(labels).transform("size")
    number = labels.groupby(labels).cumcount() + 1
    return labels.where(count == 1, labels + " " + number.astype(str))


def read_outputs(files: list[str], horizons: list) -> dict[str, pd.DataFrame]:
    """
    Returns the electricity and heat output per node for each horizon with
    nuclear CHP, indexed by country name.
    """
    outputs = {}
    countries = []
    for horizon, fn in zip(horizons, files):
        df = pd.read_csv(fn, index_col=0)
        total = df[list(SERIES)].sum(axis=1)
        df = df[total > MIN_SHARE * total.max()] if total.max() > 0 else df.iloc[:0]
        if not df.empty:
            outputs[str(horizon)] = df
            countries.append(df.country)
    if not outputs:
        return outputs

    # Same label for a node in all horizons
    countries = pd.concat(countries)
    labels = country_labels(countries[~countries.index.duplicated()])
    return {h: df[list(SERIES)].rename(index=labels) for h, df in outputs.items()}


def plot_nuclear_chp(outputs: dict[str, pd.DataFrame], title: str) -> plt.Figure:
    """Plots stacked electricity and heat output per node, one panel per horizon."""
    if not outputs:
        fig, ax = plt.subplots(figsize=(6, 1.5), facecolor=SURFACE)
        ax.axis("off")
        ax.text(0, 0.5, "No nuclear CHP in this run.", color=TEXT_SECONDARY)
        fig.suptitle(title, x=0.01, ha="left", fontsize=11, color=TEXT_PRIMARY)
        return fig

    # Same node order in all panels, largest total output at the top
    totals = pd.concat([df.sum(axis=1) for df in outputs.values()], axis=1)
    nodes = totals.sum(axis=1).sort_values().index
    xmax = max(df.sum(axis=1).max() for df in outputs.values())

    fig, axes = plt.subplots(
        1,
        len(outputs),
        figsize=(4.5 * len(outputs) + 1, 0.28 * len(nodes) + 1.6),
        facecolor=SURFACE,
        layout="constrained",
        sharey=True,
        squeeze=False,
    )
    for ax, (horizon, df) in zip(axes[0], outputs.items()):
        df = df.reindex(nodes, fill_value=0)
        left = pd.Series(0.0, index=nodes)
        for column, (label, color) in SERIES.items():
            ax.barh(
                nodes,
                df[column],
                left=left,
                height=0.7,
                color=color,
                edgecolor=SURFACE,
                linewidth=1,
                label=label,
            )
            left += df[column]

        # Heat share of the output at the end of each bar
        total = df.sum(axis=1)
        for node in nodes[total > 0]:
            share = df.at[node, "heat_TWh"] / total[node]
            ax.text(
                total[node] + 0.01 * xmax,
                node,
                f"{share:.0%} heat",
                va="center",
                fontsize=7,
                color=TEXT_SECONDARY,
            )

        ax.set_title(
            f"{horizon}: {df.electricity_TWh.sum():.0f} TWh electricity, "
            f"{df.heat_TWh.sum():.0f} TWh heat",
            loc="left",
            fontsize=9,
            color=TEXT_PRIMARY,
        )
        ax.set_xlim(0, xmax * 1.2)
        ax.set_xlabel("TWh/a", fontsize=8, color=TEXT_SECONDARY)
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=8, length=0)
        ax.grid(axis="x", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for side in ["top", "right", "left"]:
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        # Below the panels: at the top it clashes with the suptitle
        loc="outside lower left",
        ncols=len(SERIES),
        frameon=False,
        fontsize=8,
        labelcolor=TEXT_PRIMARY,
    )
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, color=TEXT_PRIMARY)
    return fig


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "plot_nuclear_chp",
            configfiles=["config/catf_model/config.base.yaml"],
            run="high-nuclear",
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    outputs = read_outputs(snakemake.input, snakemake.params.planning_horizons)
    title = f"Nuclear CHP output per node, {snakemake.wildcards.run}"
    fig = plot_nuclear_chp(outputs, title)
    fig.savefig(snakemake.output[0], dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Plotted nuclear CHP per node to {snakemake.output[0]}.")
