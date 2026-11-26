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
``catf_model.post_processing.advanced_carriers``, the links built in a
planning horizon that are not planned plants get the carrier
``advanced <carrier>`` in the solved network before it is exported, so that the
plots can show them as their own technology group.
"""

import logging

import pypsa

logger = logging.getLogger(__name__)

PREFIX = "advanced "


def split_advanced(n: pypsa.Network, carriers: list[str], first_horizon: int) -> None:
    """Gives new-build links of the carriers the carrier ``advanced <carrier>``."""
    links = n.links
    for carrier in carriers:
        new = (
            (links.carrier == carrier)
            & (links.build_year >= first_horizon)
            & ~links.index.str.contains(" planned-")
        )
        if not new.any():
            continue
        links.loc[new, "carrier"] = PREFIX + carrier
        if PREFIX + carrier not in n.carriers.index:
            n.carriers.loc[PREFIX + carrier] = n.carriers.loc[carrier]
        logger.info(f"{new.sum()} {carrier} links are advanced (new build)")
