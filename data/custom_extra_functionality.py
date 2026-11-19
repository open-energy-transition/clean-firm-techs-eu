# SPDX-FileCopyrightText: : 2023- The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT

import xarray as xr

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

    max_heat_share = nuclear_chp["parameters"]["max_heat_share"]
    if not 0 < max_heat_share <= 1:
        raise ValueError(
            f"nuclear_chp max_heat_share must be in (0, 1], got {max_heat_share}."
        )

    elec = n.links.query('carrier == "nuclear electricity"')
    if elec.empty:
        return

    # pair each electricity link with the heat link of the same node (and build year)
    heat = n.links.loc[
        elec.index.str.replace("steam electricity link", "steam heat link")
    ]

    # Turbine coefficients per link, derived from the link efficiencies so they
    # stay consistent with the cost data: eta_h = eta_e / c_v
    eta_e = elec.efficiency.values
    c_v = eta_e / heat.efficiency.values
    # Electricity + heat output may not exceed the steam used:
    # eta_e * F + (1 - c_v) * Q <= F at Q = max_heat_share * F
    share_limit = ((1 - eta_e) / (1 - c_v)).min()
    if max_heat_share > share_limit:
        raise ValueError(
            f"nuclear_chp max_heat_share {max_heat_share} gives a total output above "
            f"the reactor thermal output; it must be at most {share_limit:.3f}."
        )
    # At the backpressure point P = c_b * Q and P = eta_e * F - c_v * Q, so the
    # heat output is Q = eta_e * F / (c_b + c_v). Setting Q = max_heat_share * F:
    c_b = eta_e / max_heat_share - c_v
    # Maximum heat / maximum electricity output (both at full steam F)
    n_m = max_heat_share / eta_e

    p = n.model["Link-p"]
    # Link dimension of the dispatch variable ("Link", or "name" in PyPSA v1)
    link_dim = next(d for d in p.dims if d != "snapshot")

    def per_link(values, index):
        # Per-link coefficients must carry the link dimension: a bare numpy
        # array is broadcast against the first dimension (snapshot) instead
        return xr.DataArray(values, coords={link_dim: index}, dims=link_dim)

    # Backpressure: c_b * heat output <= electricity output
    # i.e. heat output <= max_heat_share * steam used, in every hour
    # dispatch only, so it applies to extendable and fixed links
    n.model.add_constraints(
        per_link(c_b * heat.efficiency.values, heat.index) * p.loc[:, heat.index]
        - per_link(eta_e, elec.index) * p.loc[:, elec.index]
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
            n_m[is_ext] * elec_ext.efficiency.values * pnom_elec
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
            <= per_link(elec_fix.p_nom.values, elec_fix.index),
            name="nuclear_chp-top_iso_fuel_line_fix",
        )
