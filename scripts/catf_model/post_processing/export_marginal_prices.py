# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Exports the marginal prices of selected bus carriers of a solved network as CSV files.

The carriers are set in ``catf_model.post_processing.marginal_prices.carriers``
(``all`` exports every bus carrier). Writes one wide CSV per bus carrier (e.g.
``AC.csv``, ``low_voltage.csv``, ``H2.csv``) with snapshots as rows and bus
names as columns. Alongside the prices, ``carriers.csv`` lists each carrier
with its file name, number of buses and price unit. Snapshot weightings are
written separately to ``csvs/snapshot_weightings/{horizon}.csv`` so other
post-processing metrics can reuse them for correct averages under time
aggregation.
"""

import logging
from pathlib import Path

import pandas as pd
import pypsa

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

DECIMALS = 4

UNIT_TO_PRICE_UNIT = {
    "t_co2": "EUR/tCO2",
}


def carrier_to_filename(carrier: str) -> str:
    """Converts a carrier name into a CSV file name without spaces."""
    return f"{carrier.replace(' ', '_')}.csv"


def price_unit(unit: str) -> str:
    """Maps a bus unit to the unit of its marginal price."""
    return UNIT_TO_PRICE_UNIT.get(unit, f"EUR/{unit or 'MWh'}")


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("export_marginal_prices", horizon=2050)

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    n = pypsa.Network(snakemake.input.network)

    output_dir = Path(snakemake.output.directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    prices = n.buses_t.marginal_price
    units = n.buses["unit"] if "unit" in n.buses else pd.Series("", n.buses.index)
    units = units.fillna("")

    buses_by_carrier = n.buses.groupby("carrier").groups
    carriers = snakemake.params.carriers
    if carriers == "all":
        carriers = list(buses_by_carrier)

    summary = []
    for carrier in carriers:
        if carrier not in buses_by_carrier:
            logger.warning(f"Carrier '{carrier}' not found in the network, skipping.")
            continue

        buses = prices.columns.intersection(buses_by_carrier[carrier])
        if buses.empty:
            logger.warning(f"No marginal prices found for carrier '{carrier}'.")
            continue

        filename = carrier_to_filename(carrier)
        prices[buses].round(DECIMALS).to_csv(output_dir / filename)

        bus_units = units[buses].unique()
        if len(bus_units) > 1:
            logger.warning(f"Carrier '{carrier}' has mixed bus units: {bus_units}.")

        summary.append(
            {
                "carrier": carrier,
                "file": filename,
                "buses": len(buses),
                "unit": price_unit(bus_units[0]),
            }
        )

    pd.DataFrame(summary).to_csv(output_dir / "carriers.csv", index=False)
    n.snapshot_weightings.to_csv(snakemake.output.snapshot_weightings)

    logger.info(
        f"Exported marginal prices for {len(summary)} carriers to {output_dir}."
    )
