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


def stat_by_carrier(n: pypsa.Network, stat_name: str) -> pd.Series:
    """
        Returns the statistics per carrier, with links read at "bus1".
        For eg: 
            stat_name: optimal_capacity returns the optimal capacity per carrier in MW
    """
    stats = getattr(n.statistics, stat_name)
    one_port = stats(
        components=["Generator", "StorageUnit"], groupby="carrier", nice_names=False
    )
    links = stats(
        components=["Link"], at_port="bus1", groupby="carrier", nice_names=False
    )
    return sum_by_carrier(one_port, links)

def extract_generations(n: pypsa.Network, op_path) -> pd.Series:
    """
        Returns the generation in MWh per carrier
    """
    generations = stat_by_carrier(n, "energy_balance")
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
        Extract demands by carrier in the network
    """
    demand_series = n.statistics.energy_balance(
        components=['Load'], groupby="carrier", nice_names=False
    )
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


