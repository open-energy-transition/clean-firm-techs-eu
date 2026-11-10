# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Exports the electricity dispatch of a solved network as time series.

Writes the electricity balance (buses of carrier AC and low voltage) summed over
Europe per carrier and snapshot in MW, positive for supply and negative for
consumption.

Snapshots are time segments of different length under temporal aggregation;
their lengths are in ``csvs/snapshot_weightings/{horizon}.csv``.
"""

import logging

import pandas as pd
import pypsa

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

BUS_CARRIERS = ["AC", "low voltage"]


def dispatch(n: pypsa.Network) -> pd.DataFrame:
    """Returns the electricity balance per snapshot (rows) and carrier (columns) in MW."""
    balance = n.statistics.energy_balance(
        groupby_time=False, bus_carrier=BUS_CARRIERS, nice_names=False
    )
    return balance.groupby("carrier").sum().T.round(3)


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "export_dispatch",
            configfiles=["config/catf_model/config.base.yaml"],
            run="baseline",
            horizon="2030",
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    n = pypsa.Network(snakemake.input.network)
    dispatch(n).to_csv(snakemake.output.dispatch)
    logger.info(f"Exported the electricity dispatch to {snakemake.output.dispatch}.")
