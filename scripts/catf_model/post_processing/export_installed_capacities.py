# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/oet/clean-firm-techs-eu> 
#
# SPDX-License-Identifier: MIT
"""
Exports the installed capacity by sector across runs and planning horizons.

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
    """
        Sums statistics per carrier
    """
    summed = pd.concat([s.groupby(level=-1).sum() for s in stats])
    return summed.groupby(level=0).sum().rename_axis("carrier")


def capacity_by_carrier(n: pypsa.Network) -> pd.Series:
    """
        Returns the optimal capacity in MW per carrier, with links at their output port.
    """
    one_port = n.statistics.optimal_capacity(
        components=["Generator", "StorageUnit"], groupby="carrier", nice_names=False
    )
    links = n.statistics.optimal_capacity(
        components=["Link"], at_port="bus1", groupby="carrier", nice_names=False
    )
    return sum_by_carrier(one_port, links)


def map_sector(
    capacity: pd.Series, sectors: dict[str, list[str]]
) -> tuple[pd.Series, list[str], list[str]]:
    """
    Maps technology to a sector, merges capacity data and sector mapping and returns the same 
    """
    unlimited = capacity.index[~np.isfinite(capacity)].tolist()
    capacity = capacity[np.isfinite(capacity)]
    carrier_to_sector = {c: s for s, carriers in sectors.items() for c in carriers}
    mapped = pd.Series(capacity.index.map(carrier_to_sector), index=capacity.index)
    mapped.loc[mapped.isna()] = "Other"
    df_mapped = pd.concat([capacity / 1e3, mapped], axis=1)
    df_mapped.columns = ["Capacity","Sector"]
    return df_mapped, unlimited


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("plot_installed_capacity")

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    sectors = snakemake.params.sectors
    runs = snakemake.params.runs
    horizons = snakemake.params.planning_horizons

    # Networks are ordered by run, then horizon
    keys = [(run, int(h)) for run in runs for h in horizons]
    results = {}
    for key, path in zip(keys, snakemake.input.networks):
        n = pypsa.Network(path)
        results[key], unlimited = map_sector(
            capacity_by_carrier(n), sectors
        )
        if unlimited:
            logger.info(f"{key}: carriers with unlimited capacity, left out: {unlimited}")

    data = pd.concat(results).reset_index().rename(columns={'level_0':'scenario','level_1':'planning_horizon'})
    data.to_csv(snakemake.output.csv, index=False)

    logger.info(f"Exported installed capacity data by sector and planning horizon to {snakemake.output.csv}.")
