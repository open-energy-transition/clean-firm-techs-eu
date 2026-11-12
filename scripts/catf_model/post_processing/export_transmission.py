# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Exports the electricity transmission capacities of a solved network.

Each row is one AC line or DC link with the coordinates of its buses, its
length, its existing capacity (``s_nom`` / ``p_nom``, today's grid) and its
optimal capacity (``s_nom_opt`` / ``p_nom_opt``) in MW. Multiplied with the
length, they give the transmission volume used by
``plot_transmission_expansion``; the coordinates are used by
``plot_transmission_expansion_map``.
"""

import logging

import pandas as pd
import pypsa

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)


def transmission_capacities(n: pypsa.Network) -> pd.DataFrame:
    """Returns the existing and optimal capacity of each AC line and DC link."""
    lines = n.lines
    links = n.links[n.links.carrier == "DC"]

    df = pd.concat(
        [
            pd.DataFrame(
                {
                    "component": "Line",
                    "carrier": "AC",
                    "bus0": lines.bus0,
                    "bus1": lines.bus1,
                    "length": lines.length,
                    "existing": lines.s_nom,
                    "optimal": lines.s_nom_opt,
                }
            ),
            pd.DataFrame(
                {
                    "component": "Link",
                    "carrier": "DC",
                    "bus0": links.bus0,
                    "bus1": links.bus1,
                    "length": links.length,
                    "existing": links.p_nom,
                    "optimal": links.p_nom_opt,
                }
            ),
        ]
    )
    df.index.name = "name"

    for end in ["0", "1"]:
        buses = n.buses.loc[df["bus" + end]]
        df["x" + end] = buses.x.to_numpy()
        df["y" + end] = buses.y.to_numpy()
    return df


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "export_transmission",
            horizon=2050,
            run="lcopt",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.sensitivity.yaml",
            ],
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    n = pypsa.Network(snakemake.input.network)

    capacities = transmission_capacities(n)
    capacities.round(
        {"length": 1, "existing": 1, "optimal": 1, "x0": 4, "y0": 4, "x1": 4, "y1": 4}
    ).to_csv(
        snakemake.output[0]
    )

    volume = capacities[["existing", "optimal"]].mul(capacities.length, axis=0)
    volume = volume.groupby(capacities.carrier).sum() / 1e6
    logger.info(
        f"Exported {len(capacities)} lines and DC links to {snakemake.output[0]}; "
        f"volume in TWkm (existing, optimal):\n{volume.round(1)}"
    )
