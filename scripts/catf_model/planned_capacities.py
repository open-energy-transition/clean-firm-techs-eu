# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Add planned power plants in the planning horizon in which they come online.

Under myopic foresight, add_existing_baseyear adds power plants in the first
planning horizon only, up to the last power grouping year. Plants commissioned
after that and up to the current horizon are added here with the same upstream
function, with the current horizon as build year, and carried over by
add_brownfield until ``DateOut``.

Renewables are not added, as add_existing_baseyear takes them from IRENA
statistics instead of the power plant data.
"""

import io
import logging

import pandas as pd
import pypsa

from scripts.add_existing_baseyear import add_power_capacities_installed_before_baseyear
from scripts.prepare_sector_network import define_spatial

logger = logging.getLogger(__name__)


def add_planned_capacities(
    n: pypsa.Network,
    inputs,
    params,
    costs: pd.DataFrame,
    current_horizon: int,
) -> None:
    # Plants up to the last power grouping year are added by add_existing_baseyear
    horizons = params.horizons
    start_year = max(params.existing_capacities["grouping_years_power"])
    if current_horizon != horizons[0]:
        start_year = max(start_year, horizons[horizons.index(current_horizon) - 1])

    ppl = pd.read_csv(inputs.powerplants, index_col=0)
    planned = ppl.query("DateIn > @start_year and DateIn <= @current_horizon")
    if planned.empty:
        return
    # Otherwise only created by the existing renewables, which are not added here
    planned = planned.assign(resource_class=0)

    logger.info(
        f"Adding planned power plants commissioned in {start_year + 1}-{current_horizon}:\n"
        f"{planned.groupby('Fueltype').Capacity.sum().div(1e3).round(2)}"
    )
    add_power_capacities_installed_before_baseyear(
        n=n,
        costs=costs,
        grouping_years=[start_year, current_horizon],
        baseyear=current_horizon,
        powerplants_file=io.StringIO(planned.to_csv()),
        countries=params.countries,
        capacity_threshold=params.existing_capacities["threshold_capacity"],
        lifetime_values=params.costs["fill_values"],
        renewable_carriers=[],
        spatial=define_spatial(n.buses[n.buses.carrier == "AC"].index, params.sector),
        solar_rooftop_ratio=params.existing_capacities["solar_rooftop_ratio"],
    )
