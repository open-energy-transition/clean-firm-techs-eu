# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Exports the use of nuclear CHP per node of a solved network.

Per node (AC bus) with nuclear CHP (``catf_model.nuclear_chp``), writes its
country code, the reactor thermal output (steam), the electricity output and the district heat
output in TWh per year, and the reactor and heat extraction capacities in MW
(thermal, steam at the link input). All vintages at a node are summed. The CSV
has a header only if the network has no nuclear CHP.
"""

import logging

import pandas as pd
import pypsa

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

CARRIERS = {
    "steam": "nuclear steam",
    "electricity": "nuclear electricity",
    "heat": "nuclear heat",
}
COLUMNS = [
    "steam_TWh",
    "electricity_TWh",
    "heat_TWh",
    "reactor_MW",
    "heat_extraction_MW",
]


def nuclear_chp_per_node(n: pypsa.Network) -> pd.DataFrame:
    """Returns the nuclear CHP output (TWh/a) and capacities (MW) per node."""
    links = n.links
    # Node of each link: the location of its steam bus (bus1 of the reactor,
    # bus0 of the turbine links)
    steam_bus = links.bus1.where(links.carrier == CARRIERS["steam"], links.bus0)
    node = steam_bus.map(n.buses.location)

    weights = n.snapshot_weightings.generators
    nyears = weights.sum() / 8760
    # Output at bus1 (negative in PyPSA's sign convention), per year
    output = -n.links_t.p1.multiply(weights, axis=0).sum() / nyears / 1e6

    data = {}
    for name, carrier in CARRIERS.items():
        i = links.index[links.carrier == carrier]
        data[f"{name}_TWh"] = output.reindex(i, fill_value=0).groupby(node[i]).sum()
    for column, carrier in [
        ("reactor_MW", CARRIERS["steam"]),
        ("heat_extraction_MW", CARRIERS["heat"]),
    ]:
        i = links.index[links.carrier == carrier]
        data[column] = links.loc[i, "p_nom_opt"].groupby(node[i]).sum()

    df = pd.DataFrame(data, columns=COLUMNS).fillna(0).round(4)
    df.index.name = "node"
    df.insert(0, "country", df.index.map(n.buses.country))
    return df


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "export_nuclear_chp",
            configfiles=["config/catf_model/config.base.yaml"],
            run="high-nuclear",
            horizon="2050",
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    n = pypsa.Network(snakemake.input.network)
    df = nuclear_chp_per_node(n)
    df.to_csv(snakemake.output[0])
    logger.info(
        f"Exported nuclear CHP for {len(df)} nodes "
        f"({df.electricity_TWh.sum():.1f} TWh electricity, "
        f"{df.heat_TWh.sum():.1f} TWh heat) to {snakemake.output[0]}."
    )
