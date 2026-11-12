# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/open-energy-transition/clean-firm-techs-eu>
#
# SPDX-License-Identifier: MIT
"""
Plots maps of the transmission expansion of runs (e.g. lcopt, lvopt) compared
to a reference run (e.g. baseline).

Reads the CSVs written by ``export_transmission`` for each run and planning
horizon. There is one map per compared run (rows) and planning horizon
(columns). Each AC line and DC link is drawn with a width proportional to the
difference of its optimal capacity to the reference run in the same horizon:
more capacity in the AC or DC color, less capacity in the reduction color. The
reference grid is drawn underneath in grey. Line widths use the same scale in
all maps, so that they can be compared.

The map projection and boundaries are taken from ``plotting`` (as in
``plot_power_network``), the background from the onshore regions.
"""

import logging

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

# Colors for the plot layout, text and map, as in plot_statistics
SURFACE = "#ffffff"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
LAND = "#f4f3ee"
BORDER = "#c3c2b7"
REFERENCE_GRID = "#b5b4ad"
REDUCTION = "#db170d"

# Width of the line with the largest capacity difference, in points
MAX_LINE_WIDTH = 7.0
# Differences below this share of the largest one are not drawn
MIN_SHARE = 0.01
# Size of one map, in inches
MAP_SIZE = 4.2


def read_capacities(path: str) -> pd.DataFrame:
    """Returns the transmission capacities of a run and horizon, indexed by component and name."""
    return pd.read_csv(path).set_index(["component", "name"])


def legend_values(max_gw: float) -> list[float]:
    """Returns up to three round capacity differences in GW for the line width legend."""
    if max_gw <= 0:
        return []
    magnitude = 10 ** np.floor(np.log10(max_gw))
    top = next(m * magnitude for m in [5, 2, 1] if m * magnitude <= max_gw)
    return sorted({top, top / 2, top / 5} - {0})


def draw_lines(
    ax: plt.Axes, df: pd.DataFrame, widths: np.ndarray, colors: np.ndarray, zorder: int
) -> None:
    """Draws straight lines between the bus coordinates of each row."""
    for (_, row), width, color in zip(df.iterrows(), widths, colors):
        ax.plot(
            [row.x0, row.x1],
            [row.y0, row.y1],
            color=color,
            linewidth=width,
            solid_capstyle="round",
            transform=ccrs.PlateCarree(),
            zorder=zorder,
        )


def plot_maps(
    capacities: dict,
    runs: list[str],
    horizons: list,
    reference: str,
    regions: gpd.GeoDataFrame,
    projection: ccrs.Projection,
    boundaries: list,
    colors: dict,
) -> plt.Figure:
    """Plots one map per compared run and horizon of the capacity difference to the reference run."""
    compared = runs[1:]

    # Capacity difference to the reference run in GW, per run, horizon, line and link
    diffs = {}
    for run in compared:
        for h in horizons:
            ref = capacities[(reference, h)]
            df = capacities[(run, h)]
            diff = df.optimal.sub(ref.optimal, fill_value=0.0) / 1e3
            diffs[(run, h)] = df.combine_first(ref).assign(diff=diff)
    max_gw = max(d["diff"].abs().max() for d in diffs.values())
    scale = MAX_LINE_WIDTH / max_gw if max_gw > 0 else 0.0

    fig, axes = plt.subplots(
        len(compared),
        len(horizons),
        figsize=(MAP_SIZE * len(horizons), MAP_SIZE * len(compared) + 0.8),
        subplot_kw={"projection": projection},
        squeeze=False,
        facecolor=SURFACE,
        layout="constrained",
    )

    for i, run in enumerate(compared):
        for j, h in enumerate(horizons):
            ax = axes[i, j]
            ax.set_extent(boundaries, crs=ccrs.PlateCarree())
            ax.add_geometries(
                regions.geometry,
                crs=ccrs.PlateCarree(),
                facecolor=LAND,
                edgecolor=BORDER,
                linewidth=0.3,
                zorder=0,
            )
            ax.spines["geo"].set_edgecolor(BORDER)

            ref = capacities[(reference, h)]
            draw_lines(
                ax,
                ref,
                np.full(len(ref), 0.6),
                np.full(len(ref), REFERENCE_GRID),
                zorder=1,
            )

            df = diffs[(run, h)]
            df = df[df["diff"].abs() >= MIN_SHARE * max_gw].sort_values(
                "diff", key=abs
            )
            line_colors = np.where(
                df["diff"] < 0, REDUCTION, df.carrier.map(colors).fillna(REDUCTION)
            )
            draw_lines(ax, df, df["diff"].abs().to_numpy() * scale, line_colors, 2)

            # Total change of the transmission volume, in TWkm
            volume = (
                diffs[(run, h)]["diff"] * diffs[(run, h)].length
            ).sum() / 1e3
            ax.text(
                0.02,
                0.02,
                f"{volume:+,.0f} TWkm",
                transform=ax.transAxes,
                fontsize=8,
                color=TEXT_SECONDARY,
                va="bottom",
            )
            if i == 0:
                ax.set_title(str(h), fontsize=10, color=TEXT_PRIMARY)
            if j == 0:
                ax.text(
                    -0.04,
                    0.5,
                    run,
                    transform=ax.transAxes,
                    rotation=90,
                    ha="right",
                    va="center",
                    fontsize=10,
                    fontweight="bold",
                    color=TEXT_PRIMARY,
                )

    # Legend: colors and line widths
    handles = [
        Line2D([], [], color=color, linewidth=3, label=f"{carrier} more capacity")
        for carrier, color in colors.items()
    ]
    handles += [
        Line2D([], [], color=REDUCTION, linewidth=3, label="less capacity"),
        Line2D([], [], color=REFERENCE_GRID, linewidth=0.6, label=f"{reference} grid"),
    ]
    handles += [
        Line2D([], [], color=TEXT_SECONDARY, linewidth=v * scale, label=f"{v:g} GW")
        for v in legend_values(max_gw)
    ]
    fig.legend(
        handles=handles,
        loc="outside lower center",
        ncol=len(handles),
        frameon=False,
        fontsize=8,
        labelcolor=TEXT_PRIMARY,
    )
    fig.suptitle(
        f"Transmission capacity compared to {reference}",
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
            "plot_transmission_expansion_map",
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
    keys = [(run, h) for run in runs for h in horizons]
    capacities = {
        key: read_capacities(path)
        for key, path in zip(keys, snakemake.input.capacities)
    }

    plotting = snakemake.params.plotting
    projection_kwargs = dict(plotting.get("projection", {"name": "EqualEarth"}))
    projection = getattr(ccrs, projection_kwargs.pop("name"))(**projection_kwargs)
    regions = gpd.read_file(snakemake.input.regions).to_crs(4326)
    boundaries = plotting["map"]["boundaries"]
    if boundaries is None:
        boundaries = list(regions.total_bounds[[0, 2, 1, 3]] + [-1, 1, -1, 1])

    fig = plot_maps(
        capacities,
        runs,
        horizons,
        reference,
        regions,
        projection,
        boundaries,
        snakemake.params.colors,
    )
    fig.savefig(snakemake.output[0], dpi=200)
    plt.close(fig)

    logger.info(
        f"Plotted maps of the transmission expansion of {runs[1:]} compared to "
        f"{reference} to {snakemake.output[0]}."
    )
