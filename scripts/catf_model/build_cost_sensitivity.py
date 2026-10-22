# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Build a custom cost file for the CATF established-technology cost sensitivity.

For every cost year of the configured planning horizons, the investment costs
of established technologies (solar, wind, batteries and gas power plants) and
the natural gas fuel price are read from the technology-data cost files and
multiplied by the factor given in the output file name. The scaled values are
appended to the default custom cost file, which is then selected per scenario
through ``costs: custom_cost_fn``.

Scaling is done on the cost table rather than via ``adjustments`` so that each
asset vintage is scaled exactly once under myopic foresight. Fixed operation
and maintenance costs are given in %/year of investment and therefore scale
along with it.
"""

import logging

import pandas as pd

from scripts._helpers import configure_logging

logger = logging.getLogger(__name__)

INVESTMENT_TECHNOLOGIES = [
    # Solar ("solar" is overwritten by "solar-utility" in prepare_costs)
    "solar",
    "solar-utility",
    "solar-utility single-axis tracking",
    "solar-rooftop",
    "solar-rooftop commercial",
    "solar-rooftop residential",
    # Onshore wind
    "onwind",
    # Grid connection of onshore wind and utility solar (add_electricity_grid_connection)
    "distribution grid reinforcement",
    # Offshore wind turbines, substations and grid connections
    "offwind",
    "offwind-float",
    "offwind-ac-station",
    "offwind-ac-connection-submarine",
    "offwind-ac-connection-underground",
    "offwind-dc-station",
    "offwind-dc-connection-submarine",
    "offwind-dc-connection-underground",
    "offwind-float-station",
    "offwind-float-connection-submarine",
    "offwind-float-connection-underground",
    # Batteries (combined battery costs are derived from these in prepare_costs)
    "battery storage",
    "battery inverter",
    "home battery storage",
    "home battery inverter",
    # Gas power plants
    "OCGT",
    "CCGT",
    "central gas CHP",
]

FUEL_TECHNOLOGIES = ["gas"]


def apply_base_costs(
    costs: pd.DataFrame, base_factors: dict[str, float]
) -> pd.DataFrame:
    """
    Return costs dataframe with base costs scaled for technologies specified in the config parameter 'cost_factors' in the format of the custom cost file.
    """
    for tech, factor in base_factors.items():
        tech_rows = costs.query(
            "technology == @tech and parameter.isin(['investment', 'marginal_cost', 'VOM'])"
        ).index
        costs.loc[tech_rows, "value"] = (costs.loc[tech_rows, "value"] * factor).round(
            6
        )
        costs.loc[tech_rows, "source"] = (
            f"CATF established-technology base cost scaling by {factor}"
        )

    return costs


def scale_costs(costs: pd.DataFrame, factor: float, cost_year: str) -> pd.DataFrame:
    """
    Return scaled cost rows in the format of the custom cost file.
    """
    selection = (
        costs.technology.isin(INVESTMENT_TECHNOLOGIES)
        & (costs.parameter == "investment")
    ) | (costs.technology.isin(FUEL_TECHNOLOGIES) & (costs.parameter == "fuel"))
    scaled = costs.loc[selection].copy()

    expected = len(INVESTMENT_TECHNOLOGIES) + len(FUEL_TECHNOLOGIES)
    if len(scaled) != expected:
        found = set(scaled.technology)
        missing = set(INVESTMENT_TECHNOLOGIES + FUEL_TECHNOLOGIES) - found
        raise ValueError(f"Missing cost entries for {cost_year}: {sorted(missing)}")

    scaled["value"] = (scaled["value"] * factor).round(6)
    scaled["planning_horizon"] = cost_year
    scaled["further description"] = [
        f"Original value {v:.4f} scaled by {factor}"
        for v in costs.loc[selection, "value"]
    ]
    scaled["source"] = "CATF established-technology cost sensitivity"

    return scaled


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "build_cost_sensitivity",
            configfiles=["config/catf_model/config.base.yaml"],
            factor="1.33",
        )
    configure_logging(snakemake)

    base_factors = snakemake.params.cost_factors
    factor = float(snakemake.wildcards.factor)
    cost_years = snakemake.params.cost_years

    default = apply_base_costs(pd.read_csv(snakemake.input.default, dtype={"planning_horizon": "str"}), base_factors)

    scaled = [
        scale_costs(apply_base_costs(pd.read_csv(fn), base_factors), factor, year)
        for fn, year in zip(snakemake.input.costs, cost_years)
    ]

    df = pd.concat([default, *scaled], ignore_index=True)[default.columns]
    df.to_csv(snakemake.output[0], index=False)
    logger.info(
        f"Scaled {len(df) - len(default)} cost entries by {factor} for {cost_years}"
    )
