# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Separates advanced (new-build) capacity from existing and planned capacity in the exports.

All nuclear links have the carrier ``nuclear``, whether they are existing plants
(``add_existing_baseyear``, built in a grouping year up to 2025), planned plants
(``<bus> nuclear planned-<horizon>``) or new build with the advanced-technology
costs (extendable from a planning horizon on in the advanced-technology
scenarios, and kept fixed in later horizons). For the carriers in
``catf_model.post_processing.advanced_carriers``, the generators and links built
in a planning horizon that are not planned plants get the carrier
``advanced <carrier>`` in the solved network before it is exported, so that the
plots can show them as their own technology group.

The fuel they burn (e.g. uranium) is bought by one generator for both. Its
costs are split by the fuel used: the share of the advanced plants is exported
as ``<fuel> for advanced <carrier>``.
"""

import logging

import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

PREFIX = "advanced "


def split_advanced(n: pypsa.Network, carriers: list[str], first_horizon: int) -> None:
    """Gives new-build generators and links of the carriers the carrier ``advanced <carrier>``."""
    for carrier in carriers:
        for c in ("Generator", "Link"):
            static = n.static(c)
            new = (
                (static.carrier == carrier)
                & (static.build_year >= first_horizon)
                & ~static.index.str.contains(" planned-")
            )
            if not new.any():
                continue
            static.loc[new, "carrier"] = PREFIX + carrier
            if PREFIX + carrier not in n.carriers.index:
                n.carriers.loc[PREFIX + carrier] = n.carriers.loc[carrier]
            logger.info(f"{c}: {new.sum()} {carrier} assets are advanced (new build)")


def fuel_shares(n: pypsa.Network, carriers: list[str]) -> dict[tuple[str, str], float]:
    """
    Returns the share of the fuel (bus0 carrier) of the links of the carriers
    used by the advanced plants, per fuel and advanced carrier.
    """
    advanced = [PREFIX + c for c in carriers]
    links = n.links[n.links.carrier.isin(carriers + advanced)]
    if links.empty or n.links_t.p0.empty:
        return {}
    used = n.links_t.p0[links.index].mul(n.snapshot_weightings.generators, axis=0).sum()
    fuel = links.bus0.map(n.buses.carrier)
    is_advanced = links.carrier.isin(advanced)
    shares = (
        used[is_advanced].groupby([fuel[is_advanced], links.carrier[is_advanced]]).sum()
        / used.groupby(fuel).sum()
    )
    return shares.dropna().to_dict()


def split_fuel_costs(
    costs: pd.DataFrame, shares: dict[tuple[str, str], float]
) -> pd.DataFrame:
    """Moves the advanced plants' share of the fuel generators' costs to ``<fuel> for advanced <carrier>``."""
    original = costs
    costs = costs.copy()
    for (fuel, carrier), share in shares.items():
        if ("Generator", fuel) not in costs.index or share == 0:
            continue
        name = f"{fuel} for {carrier}"
        moved = original.loc[("Generator", fuel)] * share
        costs.loc[("Generator", name), :] = moved
        costs.loc[("Generator", fuel), :] -= moved
        logger.info(f"Moved {share:.1%} of the {fuel} costs to {name}")
    return costs
