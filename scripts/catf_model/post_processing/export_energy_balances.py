# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Exports the annual energy balance of a solved network as a long-format CSV.

Each row is the net annual flow of one technology (component and carrier)
into (positive) or out of (negative) the buses of one bus carrier, weighted by
the snapshot weightings. Rows are labelled with a ``category`` so that plots
can drop flows that net out over the year:

- ``transmission``: lines, DC links and pipelines between buses of the same
  carrier, which only add their losses to an aggregated balance.
- ``storage``: cyclic stores, storage units without inflow (e.g. pumped hydro)
  and storage chargers and dischargers, which only add their losses.
- ``technology``: everything else.
"""

import logging
import re

import pandas as pd
import pypsa
from pypsa.statistics import get_transmission_carriers

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

# Links that charge or discharge a storage. The BEV charger is excluded, as it
# supplies the electric vehicle demand.
STORAGE_LINK_PATTERN = re.compile(r"(?<!BEV) (dis)?charger$")


def storage_carriers(n: pypsa.Network) -> set[tuple[str, str]]:
    """Returns the (component, carrier) pairs of storage technologies."""
    stores = n.stores
    cyclic = stores.e_cyclic
    inflow = n.storage_units_t.inflow.sum().reindex(n.storage_units.index, fill_value=0)

    return (
        {("Store", c) for c in stores.carrier[cyclic].unique()}
        | {("StorageUnit", c) for c in n.storage_units.carrier[inflow == 0].unique()}
        | {("Link", c) for c in n.links.carrier.unique() if STORAGE_LINK_PATTERN.search(c)}
    )


def energy_balance(n: pypsa.Network) -> pd.DataFrame:
    """Returns the annual energy balance per component, carrier and bus carrier."""
    balance = n.statistics.energy_balance(nice_names=False).rename("value")
    balance = balance.reset_index()

    transmission = set(map(tuple, get_transmission_carriers(n)))
    storage = storage_carriers(n)
    pairs = list(zip(balance.component, balance.carrier))
    balance["category"] = [
        "transmission" if p in transmission else "storage" if p in storage else "technology"
        for p in pairs
    ]

    units = n.buses.groupby("carrier").unit.first().replace("", "MWh")
    balance["unit"] = balance.bus_carrier.map(units).fillna("MWh")

    return balance[["bus_carrier", "component", "carrier", "category", "unit", "value"]]


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "export_energy_balances",
            horizon=2050,
            configfiles=["config/catf_model/config.base.yaml"],
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    n = pypsa.Network(snakemake.input.network)

    balance = energy_balance(n)
    balance = balance.sort_values(["bus_carrier", "category", "value"])
    balance.round({"value": 1}).to_csv(snakemake.output[0], index=False)

    logger.info(
        f"Exported {len(balance)} energy balance entries for "
        f"{balance.bus_carrier.nunique()} bus carriers to {snakemake.output[0]}."
    )
