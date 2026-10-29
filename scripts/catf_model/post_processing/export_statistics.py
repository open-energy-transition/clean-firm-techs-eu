# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Exports the costs, installed capacities, generation and demand of a solved network.

Capacities and generation are exported per panel set in
``catf_model.post_processing.statistics.panels`` (Electricity, Heat, Hydrogen,
Fuels & conversion). A technology is counted in a panel if it supplies energy to
the panel's bus carriers, and is measured at the port connected to them:

- a CHP is counted in Electricity with its electrical and in Heat with its
  thermal capacity;
- heat pumps are counted in Heat with their thermal capacity;
- consumers (e.g. chargers, or resistive heaters on the electricity side) are
  not counted, as they do not supply the panel's buses;
- lines and links between buses of the panel (transmission, distribution grid)
  and the carriers in ``exclude`` are left out.

The Storage panel holds the energy capacity of the built storage listed in
``statistics.storage``: Store ``e_nom`` and StorageUnit ``p_nom`` times ``max_hours``.

Costs are per component and carrier. The CO2 load sink (Generator ``load``) is a
slack with a penalty per tonne, not a technology; its cost is logged.

Demand is the annual consumption of loads per carrier, without loads at CO2 buses.

All CSVs are in MW, MWh and EUR/a.
"""

import logging

import pandas as pd
import pypsa

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

DECIMAL = 4


def internal_links(n: pypsa.Network, bus_carriers: list[str]) -> list[str]:
    """Returns the carriers of links between buses of the given carriers, e.g. DC, distribution grid, pipelines."""
    bus0 = n.links.bus0.map(n.buses.carrier)
    bus1 = n.links.bus1.map(n.buses.carrier)
    inside = bus0.isin(bus_carriers) & bus1.isin(bus_carriers)
    return n.links.carrier[inside].unique().tolist()


def panel_statistics(
    n: pypsa.Network, bus_carriers: list[str], exclude: list[str]
) -> pd.DataFrame:
    """
    Returns the capacity (MW) and generation (MWh) per carrier of the
    technologies supplying the given bus carriers, measured at the port
    connected to them.
    """
    # Lines are left out as transmission, Stores as their capacity is energy (MWh), not power
    kwargs = dict(
        components=["Generator", "StorageUnit", "Link"],
        bus_carrier=bus_carriers,
        groupby="carrier",
        nice_names=False,
    )
    supply = n.statistics.supply(**kwargs)
    capacity = n.statistics.optimal_capacity(at_port=True, **kwargs)

    # Keep technologies that supply energy, except links within the panel and excluded carriers
    left_out = internal_links(n, bus_carriers) + exclude
    logger.info(f"{bus_carriers}: left out {left_out}")
    carriers = supply.index.get_level_values("carrier")
    supply = supply[(supply > 0) & ~carriers.isin(left_out)]

    # Heat pumps are defined in reverse (bus0 = heat), so their capacity at the heat port is negative
    capacity = capacity.reindex(supply.index).abs()

    stats = pd.DataFrame({"capacity": capacity, "generation": supply})
    return stats.groupby(level="carrier").sum()


def storage_capacity(n: pypsa.Network, carriers: list[str]) -> pd.Series:
    """Returns the energy capacity (MWh) per carrier of the given stores and storage units."""
    stores = n.stores.groupby("carrier").e_nom_opt.sum()
    units = n.storage_units
    units = (units.p_nom_opt * units.max_hours).groupby(units.carrier).sum()
    energy = pd.concat([stores, units])
    return energy[energy.index.isin(carriers)]


def to_long(values: dict[str, pd.Series], unit: str) -> pd.DataFrame:
    """Combines a series per panel into a table with the columns panel, carrier, unit and value."""
    data = pd.concat(values, names=["panel", "carrier"]).rename("value").reset_index()
    data.insert(2, "unit", unit)
    return data


def extract_costs(n: pypsa.Network, path: str) -> None:
    """Exports the opex, capex and system costs per component and carrier in EUR/a."""
    costs = pd.concat(
        {
            "opex": n.statistics.opex(nice_names=False),
            "capex": n.statistics.capex(nice_names=False),
            "system cost": n.statistics.system_cost(nice_names=False),
        },
        axis=1,
    ).fillna(0)

    slack = costs.loc[costs.index.isin([("Generator", "load")]), "system cost"].sum()
    if slack > 0:
        logger.warning(
            f"The CO2 load sink costs {slack / 1e9:.1f} bn EUR/a, exported as Generator 'load'."
        )

    costs.round(DECIMAL).to_csv(path)
    logger.info(f"Exported costs per component and carrier to {path}")


def extract_capacities_and_generation(
    n: pypsa.Network, statistics: dict, capacity_path: str, generation_path: str
) -> None:
    """Exports the capacities (incl. storage) and the generation per panel and carrier."""
    stats = {
        panel: panel_statistics(n, spec["bus_carriers"], spec.get("exclude", []))
        for panel, spec in statistics["panels"].items()
    }

    capacities = pd.concat(
        [
            to_long({p: s.capacity for p, s in stats.items()}, "MW"),
            to_long({"Storage": storage_capacity(n, statistics["storage"])}, "MWh"),
        ]
    )
    capacities.round({"value": DECIMAL}).to_csv(capacity_path, index=False)
    logger.info(f"Exported capacities to {capacity_path}")

    generation = to_long({p: s.generation for p, s in stats.items()}, "MWh")
    generation.round({"value": DECIMAL}).to_csv(generation_path, index=False)
    logger.info(f"Exported generation to {generation_path}")


def extract_demands(n: pypsa.Network, path: str) -> None:
    """Exports the annual demand per load carrier in MWh, without loads at CO2 buses."""
    co2_loads = n.loads.carrier[n.loads.bus.map(n.buses.unit).eq("t_co2")].unique()
    logger.info(f"Demand: left out loads at CO2 buses: {co2_loads.tolist()}")

    # Loads withdraw energy, so their balance is negative
    balance = n.statistics.energy_balance(
        components=["Load"], groupby="carrier", nice_names=False
    )
    demand = -balance.droplevel("component").drop(co2_loads, errors="ignore")

    data = demand.rename("value").reset_index()
    data.insert(1, "unit", "MWh")
    data.round({"value": DECIMAL}).to_csv(path, index=False)
    logger.info(f"Exported demand per carrier to {path}")


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "export_statistics",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.initial.yaml",
            ],
            run="baseline",
            horizon=2050,
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    n = pypsa.Network(snakemake.input.network)

    extract_costs(n, snakemake.output.costs)
    extract_capacities_and_generation(
        n,
        snakemake.params.statistics,
        snakemake.output.capacities,
        snakemake.output.generation,
    )
    extract_demands(n, snakemake.output.demand)
