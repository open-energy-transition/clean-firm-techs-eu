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

The planned plants are separate fixed links named ``<bus> <carrier>
planned-<horizon>``. Upstream would otherwise only set ``p_nom_min`` of the
extendable link of the same name (e.g. new-build nuclear in the
advanced-technology scenarios), so that the planned plants would get the costs
and lifetime of new build and conflict with its potential (e.g. ``p_nom_max``
0 in 2030). Their costs are taken from the cost file without the scenario's
``catf_model.cost_overwrites``, which apply to new build only; their lifetime
follows from ``DateOut``.
"""

import io
import logging

import pandas as pd
import pypsa

from scripts.add_existing_baseyear import add_power_capacities_installed_before_baseyear
from scripts.prepare_sector_network import define_spatial

logger = logging.getLogger(__name__)


def rename_links(n: pypsa.Network, names: dict[str, str]) -> None:
    """
    Rename links in the static and time-varying data. Unlike
    n.rename_component_names, no cross references are updated, as no component
    refers to links (it fails in PyPSA 1.2 on components without such a column).
    """
    c = n.components.links
    c.static = c.static.rename(index=names)
    for attr, df in c.dynamic.items():
        c.dynamic[attr] = df.rename(columns=names)


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
    # Rename the extendable links of this horizon temporarily, so that upstream
    # adds the planned plants as new links instead of setting p_nom_min of them
    suffix = f"-{current_horizon}"
    extendable = n.links.index[
        n.links.p_nom_extendable & n.links.index.str.endswith(suffix)
    ]
    hidden = {name: f"{name} hidden" for name in extendable}
    rename_links(n, hidden)
    before = n.links.index

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

    added = n.links.index.difference(before)
    rename_links(
        n, {name: name.removesuffix(suffix) + f" planned{suffix}" for name in added}
    )
    rename_links(n, {v: k for k, v in hidden.items()})
