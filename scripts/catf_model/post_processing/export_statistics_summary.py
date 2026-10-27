# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/oet/clean-firm-techs-eu> 
#
# SPDX-License-Identifier: MIT
"""
Exports the installed capacity, generation and demand by sector across runs
and planning horizons.

Values are read from the per-run CSVs written by ``export_statistics``
(``results/{run}/csvs/statistics/{optimal_capacities,generation,demand}_{horizon}.csv``,
in MW and MWh) and grouped into
the sectors set in ``catf_model.post_processing.installed_capacity.sectors``.
Carriers not assigned to a sector are mapped to "Other". Carriers with
unlimited values (e.g. the capacity of the CO2 load sink) are left out and
listed in the log.

Generator and storage unit capacities are their nominal power. Link
capacities and generation are measured at the output port ``bus1`` (input
capacity times efficiency), e.g. electrical output for CCGT and CHP.

Heat pumps are the exception: they are defined in reverse (``bus0`` = heat,
``bus1`` = electricity, efficiency = 1/COP). Their nominal power is on the
heat side and their static efficiency is 1, so their capacity is the thermal
output capacity (MW_th). Their generation at ``bus1`` is their electricity
consumption, reported as negative values, not their heat output.

Store energy capacities (MWh) are not included. Demand is per load carrier,
which mostly maps to "Other" unless load carriers are listed in the sectors.

Writes one long-format CSV with the columns scenario, planning_horizon,
statistic, carrier, Sector, value and unit: capacity in GW, generation and
demand in TWh.
"""

import logging

import numpy as np
import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)


# Statistic: (unit, divisor from MW/MWh to the exported unit)
STATISTICS = {
    "capacities": ("GW", 1e3),
    "generation": ("TWh", 1e6),
    "demand": ("TWh", 1e6),
}


def read_statistic(path: str) -> pd.Series:
    """
        Reads a statistic per carrier exported by export_statistics
    """
    return pd.read_csv(path, index_col="carrier").squeeze("columns")


def map_sector(
    values: pd.Series, sectors: dict[str, list[str]], divisor: float
) -> tuple[pd.DataFrame, list[str]]:
    """
    Maps technology to a sector, merges the statistic and sector mapping and returns the same
    """
    unlimited = values.index[~np.isfinite(values)].tolist()
    values = values[np.isfinite(values)]
    carrier_to_sector = {c: s for s, carriers in sectors.items() for c in carriers}
    mapped = pd.Series(values.index.map(carrier_to_sector), index=values.index)
    mapped.loc[mapped.isna()] = "Other"
    df_mapped = pd.concat([mapped, values / divisor], axis=1)
    df_mapped.columns = ["Sector", "value"]
    return df_mapped, unlimited


def summarise(
    paths: list[str], keys: list[tuple[str, int]], sectors: dict[str, list[str]], statistic: str
) -> pd.DataFrame:
    """
    Combines the per-run CSVs of a statistic into one table with scenario and planning horizon
    """
    unit, divisor = STATISTICS[statistic]
    results = {}
    for key, path in zip(keys, paths):
        results[key], unlimited = map_sector(
            read_statistic(path), sectors, divisor
        )
        if unlimited:
            logger.info(f"{statistic} {key}: carriers with unlimited values, left out: {unlimited}")

    data = pd.concat(results).reset_index().rename(columns={'level_0':'scenario','level_1':'planning_horizon'})
    data.insert(2, "statistic", statistic)
    data["unit"] = unit
    return data


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("export_statistics_summary")

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    sectors = snakemake.params.sectors
    runs = snakemake.params.runs
    horizons = snakemake.params.planning_horizons

    # CSVs are ordered by run, then horizon
    keys = [(run, int(h)) for run in runs for h in horizons]
    data = pd.concat(
        [
            summarise(getattr(snakemake.input, statistic), keys, sectors, statistic)
            for statistic in STATISTICS
        ],
        ignore_index=True,
    )
    data.to_csv(snakemake.output.csv, index=False)

    logger.info(f"Exported {', '.join(STATISTICS)} by sector and planning horizon to {snakemake.output.csv}.")
