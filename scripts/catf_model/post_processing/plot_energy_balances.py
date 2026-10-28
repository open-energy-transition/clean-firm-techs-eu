# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Plots the annual energy balances of all runs and planning horizons for reporting.

Reads the CSVs of ``export_energy_balances`` and writes one stacked bar chart
per reporting carrier set in ``catf_model.post_processing.energy_balances.report``.
A reporting carrier merges several bus carriers (e.g. Electricity = AC + low
voltage), so flows between them, such as the electricity distribution grid,
only show their losses. On the x-axis there is one bar per planning horizon,
grouped by scenario. Technologies are grouped as configured and stacked with
supply above and consumption below zero. Storage and transmission rows net
out to their losses over the year and are shown as one "Storage & grid
losses" group. Groups below ``other_threshold`` of the supply of every bar
and technologies without a group are merged into "Other".

Also writes the plotted values as a long-format CSV with the columns carrier,
scenario, planning_horizon, group, value and unit (TWh or Mt).
"""

import logging

import matplotlib.pyplot as plt
import matplotlib.transforms as mtransforms
import numpy as np
import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config
from scripts.catf_model.post_processing.plot_energy_balances_developer import (
    scale_unit,
)

logger = logging.getLogger(__name__)

# Colors for the plot layout, text and grid
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

LOSSES = "Storage & grid losses"
OTHER = "Other"
OTHER_COLOR = "#d3d2cc"

# Gap between scenario groups on the x-axis, in bar widths
GROUP_GAP = 0.8


def load_balances(paths: list[str], keys: list[tuple[str, int]]) -> pd.DataFrame:
    """Reads the energy balance CSVs and labels them with scenario and planning horizon."""
    return pd.concat(
        [
            pd.read_csv(path).assign(scenario=run, planning_horizon=horizon)
            for path, (run, horizon) in zip(paths, keys)
        ],
        ignore_index=True,
    )


def group_balance(
    balance: pd.DataFrame, carrier: str, spec: dict, groups: dict
) -> pd.DataFrame:
    """Returns the balance of one reporting carrier per scenario, horizon and group."""
    df = balance[balance.bus_carrier.isin(spec["bus_carriers"])]
    df = df[~df.carrier.isin(spec.get("exclude", []))]
    if df.empty:
        raise ValueError(f"No energy balance rows for {carrier}: {spec['bus_carriers']}")

    carrier_to_group = {c: g for g, v in groups.items() for c in v["carriers"]}
    group = df.carrier.map(carrier_to_group)
    group[df.category.isin(["storage", "transmission"])] = LOSSES

    unmapped = sorted(df.carrier[group.isna()].unique())
    if unmapped:
        logger.warning(f"{carrier}: technologies without a group, shown as {OTHER}: {unmapped}")

    factor, unit = scale_unit(df.unit.iloc[0])
    return (
        df.assign(group=group.fillna(OTHER), value=df.value * factor)
        .groupby(["scenario", "planning_horizon", "group"], sort=False)
        .value.sum()
        .unstack("group", fill_value=0.0)
        .rename_axis(columns=None)
        .pipe(lambda t: t.assign(unit=unit))
    )


def merge_small_groups(table: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Merges groups below the threshold share of the supply of every bar into Other."""
    values = table.drop(columns="unit")
    supply = values.clip(lower=0).sum(axis=1)
    share = values.abs().div(supply, axis=0)
    small = [g for g in values if g not in (OTHER, LOSSES) and (share[g] < threshold).all()]
    if small:
        values[OTHER] = values.get(OTHER, 0.0) + values[small].sum(axis=1)
        values = values.drop(columns=small)
    # Groups that are (numerically) zero in every bar would only clutter the legend
    values = values.loc[:, values.abs().max() > 1e-4 * supply.max()]
    return values.assign(unit=table.unit)


def x_positions(index: pd.MultiIndex) -> np.ndarray:
    """Returns bar positions with a gap between scenario groups."""
    x, pos = [], 0.0
    for i, (run, _) in enumerate(index):
        if i and run != index[i - 1][0]:
            pos += GROUP_GAP
        x.append(pos)
        pos += 1
    return np.array(x)


def plot_carrier(
    table: pd.DataFrame,
    order: list[str],
    colors: dict[str, str],
    title: str,
    net_marker: bool = False,
) -> plt.Figure:
    """Plots stacked group values with scenarios and planning horizons on the x-axis."""
    unit = table.unit.iloc[0]
    values = table.drop(columns="unit")
    values = values[[g for g in order if g in values]]

    x = x_positions(values.index)
    fig, ax = plt.subplots(
        figsize=(2.5 + 0.55 * len(values), 4.5), facecolor=SURFACE, layout="constrained"
    )

    pos_bottom = np.zeros(len(values))
    neg_bottom = np.zeros(len(values))
    for group in values:
        v = values[group].to_numpy()
        ax.bar(
            x,
            v,
            bottom=np.where(v >= 0, pos_bottom, neg_bottom),
            width=0.75,
            color=colors.get(group, OTHER_COLOR),
            edgecolor=SURFACE,
            linewidth=0.6,
            label=group,
            zorder=2,
        )
        pos_bottom += v.clip(min=0)
        neg_bottom += v.clip(max=0)

    # Net balance (e.g. net CO2 emissions) as marker, otherwise total supply on top
    net = values.sum(axis=1).to_numpy()
    if net_marker:
        ax.scatter(
            x, net, marker="D", s=22, color=TEXT_PRIMARY, zorder=4, label="Net"
        )
    labels = net if net_marker else pos_bottom
    for xi, top, label in zip(x, pos_bottom, labels):
        ax.annotate(
            f"{label:,.0f}",
            (xi, top),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7,
            color=TEXT_SECONDARY,
        )

    # Planning horizons as tick labels, scenario names centred below each group
    runs = values.index.get_level_values("scenario")
    ax.set_xticks(x, values.index.get_level_values("planning_horizon").astype(str))
    trans = mtransforms.blended_transform_factory(ax.transData, ax.transAxes)
    for run in runs.unique():
        ax.text(
            x[runs == run].mean(),
            -0.1,
            run,
            transform=trans,
            ha="center",
            va="top",
            fontsize=9,
            color=TEXT_PRIMARY,
        )
    for i in range(1, len(x)):
        if runs[i] != runs[i - 1]:
            ax.axvline(
                (x[i - 1] + x[i]) / 2,
                color=BASELINE,
                linewidth=0.8,
                linestyle="--",
                zorder=1,
            )

    ax.axhline(0, color=BASELINE, linewidth=0.8, zorder=3)
    ax.set_facecolor(SURFACE)
    ax.set_title(title, color=TEXT_PRIMARY, fontsize=10, loc="left")
    ax.set_ylabel(f"{title} balance [{unit}]", color=TEXT_SECONDARY, fontsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=8, length=0)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)

    # Legend in the order of the bars from top to bottom: supply groups from the
    # top of the stack down to zero, then consumption groups from zero downwards
    supply = values.sum() >= 0
    order = [g for g in values if supply[g]][::-1] + [g for g in values if not supply[g]]
    handles = dict(zip(*ax.get_legend_handles_labels()[::-1]))
    labels = order + [label for label in handles if label not in order]
    fig.legend(
        [handles[label] for label in labels],
        labels,
        loc="outside right center",
        frameon=False,
        fontsize=8,
        labelcolor=TEXT_PRIMARY,
    )
    return fig


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "plot_energy_balances",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.initial.yaml",
            ],
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    report = snakemake.params.report
    runs = snakemake.params.runs
    runs = [runs] if isinstance(runs, str) else runs
    horizons = snakemake.params.planning_horizons

    # CSVs are ordered by run, then horizon
    keys = [(run, int(h)) for run in runs for h in horizons]
    balance = load_balances(snakemake.input.balances, keys)

    groups = report["groups"]
    colors = {g: v["color"] for g, v in groups.items()}
    order = [g for g in groups if g != LOSSES] + [LOSSES, OTHER]

    summary = []
    for (carrier, spec), output in zip(report["carriers"].items(), snakemake.output.plots):
        table = group_balance(balance, carrier, spec, groups)
        table = merge_small_groups(table, report["other_threshold"])

        fig = plot_carrier(table, order, colors, carrier, spec.get("net_marker", False))
        fig.savefig(output, dpi=200, bbox_inches="tight")
        plt.close(fig)
        logger.info(f"Plotted the {carrier} balance to {output}.")

        summary.append(
            table.drop(columns="unit")
            .stack()
            .rename("value")
            .reset_index()
            .rename(columns={"level_2": "group"})
            .assign(carrier=carrier, unit=table.unit.iloc[0])
        )

    columns = ["carrier", "scenario", "planning_horizon", "group", "value", "unit"]
    summary = pd.concat(summary, ignore_index=True)[columns]
    summary.round({"value": 3}).to_csv(snakemake.output.csv, index=False)
    logger.info(f"Exported the plotted energy balances to {snakemake.output.csv}.")
