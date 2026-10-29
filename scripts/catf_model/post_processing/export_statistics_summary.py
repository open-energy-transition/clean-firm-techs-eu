# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/open-energy-transition/clean-firm-techs-eu>
#
# SPDX-License-Identifier: MIT
"""
Summarises the installed capacity, generation and demand across runs and
planning horizons.

Reads the per-run CSVs written by ``export_statistics`` and groups the carriers:
capacities and generation by the technology groups in
``catf_model.post_processing.statistics.groups``, per panel; demand by the
sectors in ``catf_model.post_processing.sectors.demand``, in a single panel
"Demand". Carriers not assigned to a group are summed as "Other" and logged.

Writes one long-format CSV with the columns scenario, planning_horizon,
statistic, panel, group, value and unit: capacity in GW (storage in GWh),
generation and demand in TWh.
"""

import logging

import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

# Group of carriers not assigned in the config, matches the key in the plot colors
OTHER = "Other"

# Summary unit per statistic and exported unit
UNITS = {
    "capacities": {"MW": "GW", "MWh": "GWh"},
    "generation": {"MWh": "TWh"},
    "demand": {"MWh": "TWh"},
}

# Divisor from the exported MW or MWh to the summary unit
DIVISORS = {"GW": 1e3, "GWh": 1e3, "TWh": 1e6}


def group_mapping(groups: dict, panel: str) -> dict[str, str]:
    """
    Returns the group of each carrier in a panel. Groups restricted to other
    panels are skipped; later groups override earlier ones.
    """
    mapping = {}
    for group, spec in groups.items():
        if panel in spec.get("panels", [panel]):
            mapping.update(dict.fromkeys(spec["carriers"], group))
    return mapping


def summarise(
    paths: list[str], keys: list[tuple[str, int]], statistic: str, mappings: dict
) -> pd.DataFrame:
    """
    Combines the per-run CSVs of a statistic into one table, with the carriers
    summed per group and converted to the summary units.
    """
    tables, unmapped = [], set()
    for (run, horizon), path in zip(keys, paths):
        data = pd.read_csv(path)
        # The demand CSV has no panel column, all demand goes into one panel
        if "panel" not in data:
            data.insert(0, "panel", "Demand")

        data["group"] = [
            mappings.get(p, {}).get(c, OTHER) for p, c in zip(data.panel, data.carrier)
        ]
        other = data[data.group == OTHER]
        unmapped |= set(zip(other.panel, other.carrier))

        data["unit"] = data.unit.map(UNITS[statistic])
        data["value"] /= data.unit.map(DIVISORS)

        data = data.groupby(["panel", "group", "unit"], sort=False).value.sum().reset_index()
        data.insert(0, "scenario", run)
        data.insert(1, "planning_horizon", horizon)
        tables.append(data)

    if unmapped:
        logger.warning(f"{statistic}: carriers summed as '{OTHER}': {sorted(unmapped)}")

    data = pd.concat(tables, ignore_index=True)
    data.insert(2, "statistic", statistic)
    return data[["scenario", "planning_horizon", "statistic", "panel", "group", "value", "unit"]]


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "export_statistics_summary",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.initial.yaml",
            ],
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    statistics = snakemake.params.statistics
    panels = [*statistics["panels"], "Storage"]
    groups = {p: group_mapping(statistics["groups"], p) for p in panels}
    sectors = {
        "Demand": {c: s for s, carriers in snakemake.params.sectors["demand"].items() for c in carriers}
    }

    # CSVs are ordered by run, then horizon
    keys = [(run, int(h)) for run in snakemake.params.runs for h in snakemake.params.planning_horizons]
    data = pd.concat(
        [
            summarise(snakemake.input.capacities, keys, "capacities", groups),
            summarise(snakemake.input.generation, keys, "generation", groups),
            summarise(snakemake.input.demand, keys, "demand", sectors),
        ],
        ignore_index=True,
    )
    data.round({"value": 4}).to_csv(snakemake.output.csv, index=False)

    logger.info(f"Exported capacities, generation and demand by group to {snakemake.output.csv}.")
