# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Nuclear availability for the CATF model, applied in compose_network.

The availability (``p_max_pu``) of nuclear links is set to the mean energy
availability factor per country over the configured years for plants built up
to the last of these years, and to a technology-specific value for plants
built afterwards, including planned and extendable ones.
"""

import logging

import pandas as pd
import pypsa

logger = logging.getLogger(__name__)


def set_nuclear_availability(
    n: pypsa.Network,
    availability_fn: str,
    availability_years: list[int],
    new_build_p_max_pu: float,
) -> None:
    """
    Set p_max_pu of nuclear links from historical availability or for new builds.
    """
    links = n.links.index[n.links.carrier == "nuclear"]
    if links.empty:
        return

    eaf = pd.read_csv(availability_fn, index_col=0)
    eaf.columns = eaf.columns.astype(int)
    first, last = availability_years
    eaf = eaf.loc[:, first:last].mean(axis=1)

    country = n.links.loc[links, "bus1"].map(n.buses.country)
    p_max_pu = country.map(eaf).fillna(eaf.mean())

    is_new = n.links.loc[links, "p_nom_extendable"] | (
        n.links.loc[links, "build_year"] > last
    )
    p_max_pu[is_new] = new_build_p_max_pu

    n.links.loc[links, "p_max_pu"] = p_max_pu
    logger.info(
        f"Set nuclear availability to {first}-{last} mean for {(~is_new).sum()} "
        f"existing links and {new_build_p_max_pu} for {is_new.sum()} new links"
    )
