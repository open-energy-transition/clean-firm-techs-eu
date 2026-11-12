# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Plots the electricity dispatch of one run and planning horizon in representative weeks.

Reads the CSVs of ``export_dispatch`` and draws one panel per week of
``catf_model.post_processing.dispatch.weeks``: supply stacked above zero and
consumption below, per technology group in GW. Weeks outside the modelled period are skipped; if no week is
inside it (e.g. in short test runs), the whole period is plotted.

Technology groups and colours are those of
``catf_model.post_processing.energy_balances.report.groups``, extended by
``catf_model.post_processing.dispatch.groups`` (e.g. batteries, which net out
over the year but not over the hours). Technologies without a group are shown
as "Other".

Snapshots are time segments of different length under temporal aggregation;
each segment is drawn as a step over its duration, so the plot shows the
resolution the model optimises, not hourly values.
"""

import logging

import matplotlib.pyplot as plt
import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

# Colors for the plot layout, text and grid, as in plot_energy_balances
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"

OTHER = "Other"
OTHER_COLOR = "#d3d2cc"


def merge_groups(groups: dict, extra: dict) -> dict:
    """Returns the groups with the extra groups added, or their carriers added to existing groups."""
    merged = {g: {**v, "carriers": list(v["carriers"])} for g, v in groups.items()}
    for group, spec in extra.items():
        if group in merged:
            merged[group]["carriers"] += spec["carriers"]
        else:
            merged[group] = dict(spec)
    return merged


def group_dispatch(dispatch: pd.DataFrame, groups: dict) -> pd.DataFrame:
    """Returns the dispatch per snapshot and technology group in GW."""
    carrier_to_group = {c: g for g, v in groups.items() for c in v["carriers"]}
    group = dispatch.columns.map(lambda c: carrier_to_group.get(c, OTHER))
    unmapped = sorted(dispatch.columns[group == OTHER])
    if unmapped:
        logger.warning(f"Technologies without a group, shown as {OTHER}: {unmapped}")
    grouped = dispatch.T.groupby(group, sort=False).sum().T / 1e3
    order = [g for g in [*groups, OTHER] if g in grouped]
    return grouped[order]


def hourly(df: pd.DataFrame, hours: pd.Series) -> pd.DataFrame:
    """Repeats each snapshot (time segment) for every hour it lasts."""
    repeated = df.loc[df.index.repeat(hours.reindex(df.index).astype(int))]
    repeated.index = pd.date_range(df.index[0], periods=len(repeated), freq="h")
    return repeated


def select_weeks(index: pd.DatetimeIndex, weeks: dict[str, str]) -> dict[str, slice]:
    """
    Returns the time range of each week within the modelled period; weeks outside
    it are skipped, and if none is inside, the whole period is returned.
    """
    selected = {}
    for name, start in weeks.items():
        begin = pd.Timestamp(start)
        end = begin + pd.Timedelta(days=7) - pd.Timedelta(hours=1)
        if begin >= index[0] and begin <= index[-1]:
            selected[f"{name} (from {begin:%d %b})"] = slice(begin, end)
        else:
            logger.warning(f"{name} ({start}) is outside the modelled period, skipped.")
    return selected or {"Modelled period": slice(index[0], index[-1])}


def plot_dispatch(
    dispatch: pd.DataFrame,
    weeks: dict[str, str],
    colors: dict[str, str],
    title: str,
) -> plt.Figure:
    """Plots supply above and consumption below zero per week."""
    weeks = select_weeks(dispatch.index, weeks)
    fig, axes = plt.subplots(
        len(weeks),
        1,
        figsize=(12, 3.6 * len(weeks) + 0.8),
        facecolor=SURFACE,
        layout="constrained",
        squeeze=False,
    )
    # Groups that are not zero in any week, for the legend
    shown = dispatch.columns[dispatch.abs().max() > 1e-3 * dispatch.abs().max().max()]

    for ax, (name, period) in zip(axes[:, 0], weeks.items()):
        data = dispatch.loc[period, shown]

        x = data.index
        for values in [data.clip(lower=0), data.clip(upper=0)]:
            ax.stackplot(
                x,
                values.T.values,
                colors=[colors.get(g, OTHER_COLOR) for g in values.columns],
                labels=list(values.columns),
                step="post",
                linewidth=0,
            )
        ax.axhline(0, color=TEXT_PRIMARY, linewidth=0.8)
        ax.set_title(name, loc="left", fontsize=10, color=TEXT_PRIMARY)
        ax.set_ylabel("GW (consumption − / supply +)", fontsize=8, color=TEXT_SECONDARY)
        ax.set_xlim(x[0], x[-1])
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=8)
        for side in ["top", "right"]:
            ax.spines[side].set_visible(False)

    # Legend once, in the order of the plot from top to bottom: supply from the
    # top of the stack down to zero, then consumption from zero down. Groups
    # with both (e.g. storage) are listed where most of their volume is.
    handles, labels = axes[0, 0].get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    data = dispatch[shown]
    is_supply = data.clip(lower=0).sum() >= -data.clip(upper=0).sum()
    order = [*shown[is_supply][::-1], *shown[~is_supply]]
    fig.legend(
        [unique[g] for g in order],
        order,
        loc="outside right upper",
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
            "plot_dispatch",
            configfiles=["config/catf_model/config.base.yaml"],
            run="baseline",
            horizon="2030",
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    spec = snakemake.params.dispatch
    groups = merge_groups(snakemake.params.groups, spec.get("groups") or {})
    colors = {g: v["color"] for g, v in groups.items() if "color" in v}

    hours = pd.read_csv(
        snakemake.input.snapshot_weightings, index_col=0, parse_dates=True
    )["objective"]
    dispatch = pd.read_csv(snakemake.input.dispatch, index_col=0, parse_dates=True)

    dispatch = hourly(group_dispatch(dispatch, groups), hours)

    title = f"Electricity dispatch, {snakemake.wildcards.run}, {snakemake.wildcards.horizon}"
    fig = plot_dispatch(dispatch, spec["weeks"], colors, title)
    fig.savefig(snakemake.output[0], dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Plotted the electricity dispatch to {snakemake.output[0]}.")
