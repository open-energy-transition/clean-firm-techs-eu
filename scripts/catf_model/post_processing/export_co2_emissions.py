# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Exports the CO2 emissions of the solved sector-coupled networks of all planning
horizons as CSV files, with one column per horizon.

Writes two files:

- ``summary.csv`` with the CO2 cap, CO2 flows into and out of the atmosphere,
  net emissions, emissions above the cap (absorbed by the CO2 load sink at
  its penalty price) and the CO2 price, in absolute terms and relative to 1990.
- ``by_technology.csv`` with the CO2 flows into (positive) and out of
  (negative) the atmosphere per component and carrier.

Flows are annual sums per technology carrier. Flows out of the atmosphere
include biogenic carbon uptake (e.g. by biofuel and biogas production) that
is emitted again by other technologies, so they are not limited to permanent
removals such as DAC or BECCS. Net emissions are unaffected by this.

The 1990 baseline is computed in the same way as for the CO2 cap in
``prepare_network``, so it is also available for horizons with a zero cap.
"""

import logging

import pandas as pd
import pypsa

from scripts._helpers import configure_logging, set_scenario_config
from scripts.co2_budget import co2_limit_name
from scripts.prepare_sector_network import co2_emissions_year

logger = logging.getLogger(__name__)

DECIMALS = 4

# Emissions above the cap below this threshold are treated as solver noise
ABOVE_CAP_WARNING_THRESHOLD = 0.01  # MtCO2


def co2_limit_constraint(n: pypsa.Network, horizon: int) -> pd.Series | None:
    """Returns the upper CO2 limit global constraint, if present."""
    for name in [co2_limit_name("upper", horizon), co2_limit_name("upper")]:
        if name in n.global_constraints.index:
            return n.global_constraints.loc[name]
    return None


def co2_atmosphere_balance(n: pypsa.Network) -> pd.Series:
    """Returns the annual CO2 balance of the atmosphere bus in tCO2 per component and carrier."""
    if "co2" not in n.buses.carrier.values:
        raise ValueError(
            "Network has no 'co2' bus; CO2 emissions can only be exported for sector-coupled networks."
        )
    return (
        n.statistics.energy_balance(bus_carrier="co2")
        .groupby(level=["component", "carrier"])
        .sum()
    )


def horizon_emissions(
    n: pypsa.Network, horizon: int, baseline_1990: float
) -> tuple[pd.Series, pd.Series]:
    """Returns the emission summary and the CO2 flows per technology of one horizon."""
    balance = co2_atmosphere_balance(n)

    # The atmosphere store holds the emissions counted towards the cap; the load
    # sink absorbs emissions above the cap at its penalty price.
    counted = -balance.xs("Store", level="component").sum()
    above_cap = -balance.get(("Generator", "load"), 0.0)
    flows = balance.drop("Store", level="component").drop(
        [("Generator", "load")], errors="ignore"
    )

    inflows = flows[flows > 0].sum()
    outflows = flows[flows < 0].sum()
    net = counted + above_cap

    constraint = co2_limit_constraint(n, horizon)
    if constraint is None:
        logger.warning(f"No upper CO2 limit found in the network of {horizon}.")
        cap, co2_price = float("nan"), float("nan")
    else:
        cap, co2_price = constraint["constant"], -constraint["mu"]

    if above_cap / 1e6 >= ABOVE_CAP_WARNING_THRESHOLD:
        logger.warning(
            f"{horizon}: net emissions exceed the CO2 cap by {above_cap / 1e6:.1f} MtCO2 "
            f"(absorbed by the CO2 load sink at {co2_price:.0f} EUR/tCO2)."
        )
    logger.info(
        f"{horizon}: net emissions {net / 1e6:.1f} MtCO2 "
        f"({net / baseline_1990 * 100:.1f}% of 1990)."
    )

    summary = pd.Series(
        {
            ("1990 baseline", "MtCO2"): baseline_1990 / 1e6,
            ("cap", "MtCO2"): cap / 1e6,
            ("cap relative to 1990", "%"): cap / baseline_1990 * 100,
            ("flows into atmosphere", "MtCO2"): inflows / 1e6,
            ("flows out of atmosphere", "MtCO2"): outflows / 1e6,
            ("net emissions", "MtCO2"): net / 1e6,
            ("net emissions counted towards cap", "MtCO2"): counted / 1e6,
            ("net emissions above cap", "MtCO2"): above_cap / 1e6,
            ("flows into atmosphere relative to 1990", "%"): (
                inflows / baseline_1990 * 100
            ),
            ("net emissions relative to 1990", "%"): net / baseline_1990 * 100,
            ("CO2 price", "EUR/tCO2"): co2_price,
        }
    )
    summary.index.names = ["metric", "unit"]

    return summary, flows / 1e6


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("export_co2_emissions")

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    if snakemake.params.foresight == "perfect":
        raise NotImplementedError(
            "CO2 emission export is not implemented for perfect foresight."
        )

    co2_budget = snakemake.params.co2_budget

    baseline_1990 = (
        co2_emissions_year(
            countries=snakemake.params.countries,
            input_eurostat=snakemake.input.eurostat,
            options=snakemake.params.sector,
            emissions_scope=co2_budget["emissions_scope"],
            input_co2=snakemake.input.co2,
            year=1990,
        )
        * 1e9  # GtCO2 to tCO2
    )

    summaries, flows = {}, {}
    for horizon, path in zip(
        snakemake.params.planning_horizons, snakemake.input.networks
    ):
        n = pypsa.Network(path)
        summaries[horizon], flows[horizon] = horizon_emissions(
            n, int(horizon), baseline_1990
        )

    summary = pd.DataFrame(summaries)
    summary.columns.name = "horizon"
    (summary.round(DECIMALS) + 0.0).to_csv(snakemake.output.summary)  # avoid -0.0

    by_technology = pd.DataFrame(flows).fillna(0.0)
    by_technology.columns.name = "horizon"
    by_technology = by_technology.loc[
        by_technology.sum(axis=1).sort_values(ascending=False).index
    ]
    (by_technology.round(DECIMALS) + 0.0).to_csv(snakemake.output.by_technology)

    logger.info(
        f"Exported CO2 emissions for {len(summaries)} horizons to "
        f"{snakemake.output.summary} and {snakemake.output.by_technology}."
    )
