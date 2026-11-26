# SPDX-FileCopyrightText: : 2023- The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT

import xarray as xr


def custom_extra_functionality(n, snapshots, snakemake):
    """
    Add custom extra functionality constraints.

    Nuclear CHP: ties the "nuclear electricity" and "nuclear heat" links at each
    steam bus together as one extraction-condensing turbine:

    - backpressure (every hour): heat output <= max_heat_share * steam used,
      with the power loss per unit of heat (c_v) set by the link efficiencies;
    - electricity link capacity = reactor capacity (extendable links).

    The heat link capacity is optimised freely, so heat extraction is optional.
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

    # No limit on total steam through the turbine links is needed: the steam bus
    # has no store, so their steam use equals the reactor output, which is limited
    # by the reactor capacity. The heat link capacity is left to the optimiser
    # (heat extraction is optional); the backpressure caps its use at
    # max_heat_share of the steam used.

    # Extendable links: the electricity link has no costs of its own, so its
    # capacity is set equal to the reactor capacity (both in MW steam at bus0) to
    # keep it well defined for the statistics and the brownfield. Fixed links
    # (earlier horizons, operations runs) already have equal capacities.
    elec_ext = elec[elec.p_nom_extendable]
    if not elec_ext.empty:
        reactor_ext = elec_ext.index.str.replace(
            "steam electricity link", "nuclear steam link"
        )
        missing = reactor_ext.difference(n.links.index[n.links.p_nom_extendable])
        if not missing.empty:
            raise ValueError(
                f"nuclear_chp: no extendable reactor link for {list(missing)}."
            )

        p_nom = n.model["Link-p_nom"]
        n.model.add_constraints(
            p_nom.loc[elec_ext.index] - p_nom.loc[reactor_ext] == 0,
            name="nuclear_chp-elec_reactor_p_nom",
        )
