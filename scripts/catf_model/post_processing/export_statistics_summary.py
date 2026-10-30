# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/open-energy-transition/clean-firm-techs-eu>
#
# SPDX-License-Identifier: MIT
"""
Summarises the installed capacity, generation, demand and system costs across
runs and planning horizons.

Reads the per-run CSVs written by ``export_statistics`` and groups the carriers:
capacities and generation by the technology groups in
``catf_model.post_processing.statistics.groups``, per panel; demand by the
sectors in ``catf_model.post_processing.sectors.demand``, in a single panel
"Demand". Carriers not assigned to a group are summed as "Other" and logged.

Costs are summarised as capex and opex per cost category (technology groups
merged as in ``statistics.cost_categories``), and as the total
split into capex, opex and the penalty of the CO2 load sink, a slack that is
used when the CO2 cap cannot be met.

Writes one long-format CSV with the columns scenario, planning_horizon,
statistic, panel, group, value and unit: capacity in GW (storage in GWh),
generation and demand in TWh, costs in bn EUR/a. The system costs are also
written as a table with one row per run and horizon.
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


def category_mapping(statistics: dict) -> dict[str, str]:
    """Returns the cost category of each carrier, through its technology group."""
    category = {
        group: name
        for name, spec in statistics["cost_categories"].items()
        for group in spec["groups"]
    }
    groups = group_mapping(statistics["groups"], "Costs")
    missing = sorted(set(groups.values()) - set(category))
    if missing:
        logger.warning(f"costs: groups without a cost category, summed as '{OTHER}': {missing}")
    return {carrier: category.get(group, OTHER) for carrier, group in groups.items()}


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


def summarise_costs(paths: list[str], keys: list[tuple[str, int]]) -> pd.DataFrame:
    """
    Returns the system costs per run and horizon in bn EUR/a, split into capex,
    opex and the penalty of the CO2 load sink, which is a slack, not a technology.
    """
    rows = []
    for (run, horizon), path in zip(keys, paths):
        costs = pd.read_csv(path, index_col=["component", "carrier"])
        slack = costs.index == ("Generator", "load")
        rows.append(
            {
                "scenario": run,
                "planning_horizon": horizon,
                "Capex": costs.loc[~slack, "capex"].sum() / 1e9,
                "Opex": costs.loc[~slack, "opex"].sum() / 1e9,
                "CO2 cap penalty": costs.loc[slack, "system cost"].sum() / 1e9,
            }
        )
    return pd.DataFrame(rows)


def technology_costs(
    paths: list[str], keys: list[tuple[str, int]], mapping: dict[str, str]
) -> pd.DataFrame:
    """
    Returns the capex and opex per cost category, run and horizon in bn EUR/a,
    without the CO2 load sink. The columns panel ("Capex" or "Opex") and group
    (the cost category) match the summary.
    """
    tables, unmapped = [], set()
    for (run, horizon), path in zip(keys, paths):
        costs = pd.read_csv(path)
        costs = costs[~((costs.component == "Generator") & (costs.carrier == "load"))]

        costs["group"] = costs.carrier.map(mapping).fillna(OTHER)
        other = costs[(costs.group == OTHER) & (costs.capex + costs.opex != 0)]
        unmapped |= set(other.carrier)

        costs = costs.groupby("group", sort=False)[["capex", "opex"]].sum() / 1e9
        costs = costs.rename(columns={"capex": "Capex", "opex": "Opex"})
        costs = costs.melt(ignore_index=False, var_name="panel").reset_index()
        costs.insert(0, "scenario", run)
        costs.insert(1, "planning_horizon", horizon)
        tables.append(costs)

    if unmapped:
        logger.warning(f"costs: carriers summed as '{OTHER}': {sorted(unmapped)}")

    return pd.concat(tables, ignore_index=True)


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
    # Costs: capex and opex per cost category (statistics "capex" and "opex"),
    # and the total split into capex, opex and the CO2 cap penalty (statistic "costs")
    system_costs = summarise_costs(snakemake.input.costs, keys)
    totals = system_costs.melt(
        id_vars=["scenario", "planning_horizon"], var_name="group", value_name="value"
    )
    by_technology = technology_costs(snakemake.input.costs, keys, category_mapping(statistics))
    costs = pd.concat(
        [
            by_technology.assign(statistic=by_technology.panel.str.lower()),
            totals.assign(statistic="costs", panel="Total"),
        ]
    )
    costs = costs.assign(unit="bn EUR/a")

    # System costs table: one row per run and horizon
    system_costs["Total"] = system_costs[["Capex", "Opex", "CO2 cap penalty"]].sum(axis=1)
    system_costs.round(2).to_csv(snakemake.output.system_costs, index=False)
    logger.info(f"Exported system costs to {snakemake.output.system_costs}.")

    data = pd.concat(
        [
            summarise(snakemake.input.capacities, keys, "capacities", groups),
            summarise(snakemake.input.generation, keys, "generation", groups),
            summarise(snakemake.input.demand, keys, "demand", sectors),
            costs[["scenario", "planning_horizon", "statistic", "panel", "group", "value", "unit"]],
        ],
        ignore_index=True,
    )
    data.round({"value": 4}).to_csv(snakemake.output.csv, index=False)

    logger.info(f"Exported capacities, generation, demand and costs to {snakemake.output.csv}.")
