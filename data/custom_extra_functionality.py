# SPDX-FileCopyrightText: : 2023- The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT

from scripts._helpers import PYPSA_V1


def custom_extra_functionality(n, snapshots, snakemake):
    """
    Add custom extra functionality constraints.

    Nuclear CHP: ties the "nuclear electricity" and "nuclear heat" links at each
    steam bus together as one extraction-condensing turbine.
    """

    nuclear_chp = snakemake.params.catf_nuclear_chp
    if not nuclear_chp.get("enabled", False):
        return

    n_m = nuclear_chp["parameters"]["n_m"]
    c_b = nuclear_chp["parameters"]["c_b"]

    elec = n.links.query('carrier == "nuclear electricity"')
    if elec.empty:
        return
    # pair each electricity link with the heat link of the same node (and build year)
    heat = n.links.loc[
        elec.index.str.replace("steam electricity link", "steam heat link")
    ]

    p = n.model["Link-p"]

    # Backpressure: c_b * heat output <= electricity output
    # dispatch only, so it applies to extendable and fixed links
    n.model.add_constraints(
        c_b * heat.efficiency.values * p.loc[:, heat.index]
        - elec.efficiency.values * p.loc[:, elec.index]
        <= 0,
        name="nuclear_chp-backpressure",
    )

    # Extendable links: capacities are variables
    is_ext = elec.p_nom_extendable.values
    elec_ext = elec[is_ext]
    heat_ext = heat[is_ext]

    if not elec_ext.empty:
        p_nom = n.model["Link-p_nom"]
        pnom_elec = p_nom.loc[elec_ext.index]
        pnom_heat = p_nom.loc[heat_ext.index]

        # Heat output capacity = n_m * electricity output capacity
        n.model.add_constraints(
            n_m * elec_ext.efficiency.values * pnom_elec
            - heat_ext.efficiency.values * pnom_heat
            == 0,
            name="nuclear_chp-p_nom_ratio",
        )

        # Top iso-fuel line: steam through both links <= turbine capacity
        rename = {} if PYPSA_V1 else {"Link-ext": "Link"}
        n.model.add_constraints(
            p.loc[:, elec_ext.index]
            + p.loc[:, heat_ext.index]
            - p_nom.rename(rename).loc[elec_ext.index]
            <= 0,
            name="nuclear_chp-top_iso_fuel_line_ext",
        )

    # Fixed links (earlier myopic horizons, operations runs): capacity is a number
    elec_fix = elec[~is_ext]
    heat_fix = heat[~is_ext]

    if not elec_fix.empty:
        n.model.add_constraints(
            p.loc[:, elec_fix.index] + p.loc[:, heat_fix.index]
            <= elec_fix.p_nom.values,
            name="nuclear_chp-top_iso_fuel_line_fix",
        )
