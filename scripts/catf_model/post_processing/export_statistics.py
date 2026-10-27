# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/oet/clean-firm-techs-eu> 
#
# SPDX-License-Identifier: MIT
"""
Exports the statistics
"""

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

DECIMAL = 4

def extract_costs(n: pypsa.Network, op_path: str):
    """
        Extract capex, opex and system costs per technology
    """
    opex = n.statistics.opex().round(DECIMAL)
    capex = n.statistics.capex().round(DECIMAL)
    system_cost = n.statistics.system_cost().round(DECIMAL)

    assert not ((opex.sum() + capex.sum() - system_cost.sum()).round()), "System costs could not be validated as sum of CAPEX and OPEX"

    df_costs=pd.concat([opex,capex,system_cost],axis=1)
    df_costs.columns=["opex (Eur/a)","capex (Eur/a)","system cost (Eur/a)"]
    df_costs=df_costs.reset_index().drop(['component'],axis=1)
    df_costs.to_csv(op_path, index=False)
    logger.info(f"Exported costs summary to {op_path}")


def sum_by_carrier(*stats: pd.Series) -> pd.Series:
    """
        Sums statistics per carrier
    """
    summed = pd.concat([s.groupby(level=-1).sum() for s in stats])
    return summed.groupby(level=0).sum().rename_axis("carrier")


def link_carriers(n: pypsa.Network) -> dict[str, list[str]]:
    """
        Splits the link carriers by the port they are read at and what to leave out:
        - "bus1": links read at their output port bus1
        - "bus0": heat pumps, which are defined in reverse (bus0 = heat, bus1 = electricity)
        - "co2": links whose read port is a CO2 bus (unit t_co2), left out of MW/MWh statistics
        - "charger": storage chargers, whose output is energy into storage, not generation
        - "pass_through": links that only pass a fuel to a load of the same carrier
          (e.g. gas for industry), whose output equals that demand
    """
    links = n.links
    heat_pump = links.carrier.str.endswith("heat pump")
    port_bus = links.bus1.where(~heat_pump, links.bus0)
    co2 = port_bus.map(n.buses.unit).eq("t_co2")
    charger = links.carrier.str.endswith("charger") & ~links.carrier.str.endswith("discharger")
    pass_through = links.carrier.eq(links.bus1.map(n.buses.carrier)) & links.carrier.isin(n.loads.carrier)

    def carriers(mask: pd.Series) -> list[str]:
        return links.carrier[mask].unique().tolist()

    return {
        "bus1": carriers(~heat_pump & ~co2),
        "bus0": carriers(heat_pump & ~co2),
        "co2": carriers(co2),
        "charger": carriers(charger & ~co2),
        "pass_through": carriers(pass_through & ~co2),
    }


def stat_by_carrier(n: pypsa.Network, stat_name: str, exclude: tuple[str, ...] | list[str] = ()) -> pd.Series:
    """
        Returns the statistics per carrier, with links read at bus1 and heat pumps at bus0.
        Links at CO2 buses and the link carriers in exclude are left out.
        For eg:
            stat_name: optimal_capacity returns the optimal capacity per carrier in MW
    """
    stats = getattr(n.statistics, stat_name)
    one_port = stats(
        components=["Generator", "StorageUnit"], groupby="carrier", nice_names=False
    )

    carriers = link_carriers(n)
    logger.info(f"{stat_name}: left out links at CO2 buses: {carriers['co2']}")
    link_stats = []
    for port in ["bus1", "bus0"]:
        port_carriers = [c for c in carriers[port] if c not in exclude]
        if port_carriers:
            link_stats.append(stats(
                components=["Link"], at_port=port, carrier=port_carriers, groupby="carrier", nice_names=False
            ))
    return sum_by_carrier(one_port, *link_stats)

def extract_generations(n: pypsa.Network, op_path) -> pd.Series:
    """
        Returns the generation in MWh per carrier.
        Storage chargers and pass-through links to loads are left out, so that
        energy into storage and fuel delivered to a load are not counted as generation.
    """
    carriers = link_carriers(n)
    exclude = carriers["charger"] + carriers["pass_through"]
    logger.info(f"Generation: left out chargers and pass-through links: {exclude}")
    generations = stat_by_carrier(n, "energy_balance", exclude=exclude)
    generations.name="Generations (MWh)"
    generations.round(DECIMAL).to_csv(op_path)
    logger.info(f"Export generation by technology to {op_path}")

def extract_capacities(n: pypsa.Network, op_path: str):
    """
        Extract optimal capacities in the network
    """
    capacities = stat_by_carrier(n, "optimal_capacity")
    capacities.name="Capacities (MW)"
    capacities.round(DECIMAL).to_csv(op_path)
    logger.info(f"Exported optimal capacities by technology to {op_path}")

def extract_demands(n: pypsa.Network, op_path: str):
    """
        Extract demands by carrier in the network.
        Loads at CO2 buses (e.g. process emissions, in t_co2) are left out.
    """
    co2_loads = n.loads.carrier[n.loads.bus.map(n.buses.unit).eq("t_co2")].unique().tolist()
    logger.info(f"Demand: left out loads at CO2 buses: {co2_loads}")
    demand_series = n.statistics.energy_balance(
        components=['Load'], groupby="carrier", nice_names=False
    )
    demand_series = demand_series[~demand_series.index.get_level_values(-1).isin(co2_loads)]
    demands=sum_by_carrier(demand_series)
    demands.name="Demand (MWh)"
    demands.abs().round(DECIMAL).to_csv(op_path)
    logger.info(f"Extracted demands by carrier to {op_path}")

if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("export_costs")

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    # Read PyPSA Network
    n = pypsa.Network(snakemake.input.network)

    extract_costs(n, snakemake.output.costs)
    extract_capacities(n, snakemake.output.capacities)
    extract_generations(n, snakemake.output.generation)
    extract_demands(n, snakemake.output.demand)


