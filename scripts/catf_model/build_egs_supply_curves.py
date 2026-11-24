# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
EGS supply curves from site-level cost data, used by build_egs_potentials.

If ``sector.enhanced_geothermal.supply_curve`` is set, the potentials and costs
of enhanced geothermal systems (EGS) are built from a site-level table in the
format of ``EU_EGS_SupplyCurves_GEOELEC.csv`` instead of the default
Aghahosseini and Breyer (2020) data. The table has one row per grid cell, with
``CAP_<d>``, ``CAPEX_Well_<d>``, ``CAPEX_Surf_<d>``, ``TotAnn_<d>``,
``Ann_Well_<d>``, ``Ann_Surf_<d>``, ``OM_Well_<d>``, ``OM_Surf_<d>`` and
``MEAN<d>`` for each depth ``<d>`` (e.g. ``4_5``), plus ``Cell_ID``,
``Longitude`` and ``Latitude``. Capacities are in MW, capital costs in
currency/MW, annuities and O&M in currency/MW-yr.

1. Every (cell, depth) pair is one resource. Cells are assigned to the bus
   regions by centroid; the region's country is the bus-name prefix.
2. Each country's potential is capped. The cap is allocated to its regions
   cheapest-first, after first giving every region its cheapest
   ``min_potential_per_region_gw`` (or an equal share of the cap if the cap
   cannot cover that minimum everywhere).
3. Within each region, the allocated resources, all depths pooled, are grouped
   into ``n_clusters`` supply-curve steps by Ward clustering on the cost metric.
4. Membership is fixed from ``cost_data``. For every planning horizon, costs are
   re-evaluated from that horizon's data: the capacity-weighted mean subsurface
   CAPEX per step, and one surface (ORC) CAPEX per region, taken as a quantile
   over the cheapest ``surface_cost_reference_gw`` of the region's supply curve.

The potentials have one row per step and planning horizon, with ``p_nom_max``
in GW, ``CAPEX_well`` and ``CAPEX_surface`` in currency/kW and ``FOM_well`` and
``FOM_surface`` in %/year; add_enhanced_geothermal selects the rows of its
horizon.
"""

import logging

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import ward

logger = logging.getLogger(__name__)

DEFAULTS = {
    "cost_data_by_year": {},
    "currency_factor": 1.0,
    "cost_multipliers": {"subsurface": {}, "surface": {}},
    "cost_metric": "TotAnn",
    "min_resource_mw": 0.0,
    "max_potential_gw": {"default": 10.0},
    "min_potential_per_region_gw": 20.0,
    "n_clusters": {"default": 1},
    "surface_cost_reference_gw": 20.0,
    "surface_cost_quantile": 0.5,
    "well_cost_basis": "subsurface",
    "capacity_factor_scale": 1.0,
    "snap_distance_km": 10.0,
}

# GISCO / NUTS codes to the ISO 3166 codes used by PyPSA-Eur
COUNTRY_ALIASES = {"EL": "GR", "UK": "GB"}

# Columns per depth of the site table, by column name in the resource table
PER_DEPTH = {
    "cap": "CAP_{}",
    "capex_well": "CAPEX_Well_{}",
    "capex_surf": "CAPEX_Surf_{}",
    "ann_well": "Ann_Well_{}",
    "ann_surf": "Ann_Surf_{}",
    "om_well": "OM_Well_{}",
    "om_surf": "OM_Surf_{}",
    "totann": "TotAnn_{}",
    "temp_c": "MEAN{}",
}

MONETARY = [
    "capex_well",
    "capex_surf",
    "ann_well",
    "ann_surf",
    "om_well",
    "om_surf",
    "totann",
]


def load_resources(
    path: str, currency_factor: float = 1.0, min_resource_mw: float = 0.0
) -> pd.DataFrame:
    """
    Read the site table into a table with one row per (cell, depth) resource.
    """
    header = pd.read_csv(path, nrows=0).columns
    depths = sorted(c.removeprefix("CAP_") for c in header if c.startswith("CAP_"))
    if not depths:
        raise ValueError(f"No CAP_<depth> columns in {path}.")

    site_cols = ["Cell_ID", "Longitude", "Latitude"]
    usecols = site_cols + [p.format(d) for d in depths for p in PER_DEPTH.values()]
    missing = sorted(set(usecols) - set(header))
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")
    # Optional, prevents snapping cells across borders (see assign_regions)
    if "Country_Code" in header:
        usecols.append("Country_Code")
        site_cols.append("Country_Code")
    df = pd.read_csv(
        path,
        usecols=usecols,
        dtype={"Cell_ID": str, "Country_Code": str},
        keep_default_na=False,
        na_values=[""],
    )

    parts = []
    for d in depths:
        part = df[site_cols].copy()
        for col, pattern in PER_DEPTH.items():
            part[col] = df[pattern.format(d)].values
        part["depth_km"] = float(d.replace("_", "."))
        part["resource"] = part.Cell_ID + "|" + d
        parts.append(part.dropna(subset=["cap", "capex_well", "capex_surf"]))
    res = pd.concat(parts, ignore_index=True)
    res = res[res.cap > max(min_resource_mw, 0.0)]

    res[MONETARY] *= currency_factor
    # Costs in TotAnn beyond wells and plant, e.g. interconnection
    res["other_ann"] = res.totann - res[
        ["ann_well", "om_well", "ann_surf", "om_surf"]
    ].sum(axis=1)
    return res.set_index("resource")


def interpolate_multiplier(spec: dict | None, year: int) -> float:
    """
    Return the factor of a year from year-keyed factors, linear in between and
    flat outside; 1.0 if none are given.
    """
    if not spec:
        return 1.0
    spec = {int(k): float(v) for k, v in spec.items()}
    years = sorted(spec)
    return float(np.interp(year, years, [spec[y] for y in years]))


def cost_metric(res: pd.DataFrame, metric: str) -> pd.Series:
    """
    Return the total resource cost used for ranking and clustering.
    """
    if metric == "TotAnn":
        return res.ann_well + res.om_well + res.ann_surf + res.om_surf + res.other_ann
    if metric == "CAPEX":
        return res.capex_well + res.capex_surf
    raise ValueError(f"cost_metric must be 'TotAnn' or 'CAPEX', not {metric!r}.")


def data_file_for(horizon: int, cfg: dict) -> str:
    """
    Return the latest cost_data_by_year file at or before the horizon, else
    cost_data.
    """
    by_year = {int(k): v for k, v in (cfg["cost_data_by_year"] or {}).items()}
    earlier = [year for year in by_year if year <= horizon]
    return by_year[max(earlier)] if earlier else cfg["cost_data"]


def region_country(name: str) -> str:
    return COUNTRY_ALIASES.get(name[:2], name[:2])


def assign_regions(
    res: pd.DataFrame, regions: gpd.GeoDataFrame, snap_distance_km: float
) -> pd.DataFrame:
    """
    Assign each resource to the bus region containing its cell centroid.

    Centroids outside every region (coastlines) snap to the nearest region
    within ``snap_distance_km``, limited to regions of the cell's own country
    if the data have ``Country_Code``. Resources without a region are dropped.
    """
    cells = res.drop_duplicates("Cell_ID")[
        res.columns.intersection(["Cell_ID", "Longitude", "Latitude", "Country_Code"])
    ]
    points = gpd.GeoDataFrame(
        cells, geometry=gpd.points_from_xy(cells.Longitude, cells.Latitude), crs=4326
    )
    regions = regions[["name", "geometry"]].to_crs(4326)
    hit = gpd.sjoin(points, regions, how="left", predicate="within")
    hit = hit[~hit.index.duplicated()]

    miss = hit.name.isna()
    if miss.any() and snap_distance_km > 0:
        near = gpd.sjoin_nearest(
            points[miss].to_crs(3035),
            regions.to_crs(3035),
            how="left",
            max_distance=snap_distance_km * 1e3,
        )
        near = near[~near.index.duplicated()].dropna(subset=["name"])
        if "Country_Code" in near:
            same_country = near.name.map(region_country) == near.Country_Code.replace(
                COUNTRY_ALIASES
            )
            near = near[same_country]
        hit.loc[near.index, "name"] = near["name"]
        logger.info(f"Snapped {len(near)} cells to a region within {snap_distance_km} km")

    out = res.assign(region=res.Cell_ID.map(hit.set_index("Cell_ID")["name"]))
    dropped = out.region.isna()
    if dropped.any():
        logger.info(
            f"Dropped {dropped.sum()} resources ({out.cap[dropped].sum() / 1e3:.1f} GW) "
            "outside every bus region"
        )
    out = out[~dropped]
    out["country"] = out.region.map(region_country)
    return out


def take_cheapest(cap: pd.Series, amount: float) -> pd.Series:
    """
    Return the capacity taken from each entry of cost-sorted ``cap`` up to
    ``amount`` in total.
    """
    before = cap.cumsum().shift(fill_value=0.0)
    return (amount - before).clip(lower=0.0, upper=cap)


def water_fill(bounds: pd.Series, total: float) -> pd.Series:
    """
    Return equal shares of ``total``, each capped at its bound.
    """
    if bounds.sum() <= total:
        return bounds.copy()
    values = np.sort(bounds.values)
    level, remaining, n = 0.0, total, len(values)
    for i, value in enumerate(values):
        if value * (n - i) >= remaining:
            level = remaining / (n - i)
            break
        remaining -= value
    return bounds.clip(upper=level)


def allocate_country(
    res: pd.DataFrame, cap_mw: float, min_region_mw: float
) -> pd.Series:
    """
    Return the allocated MW per resource of a country: the per-region minimum
    first, then the cheapest resources across the country up to the cap.
    """
    res = res.sort_values("metric", kind="mergesort")
    potential = res.groupby("region").cap.sum()
    total = min(cap_mw, potential.sum())
    floors = water_fill(potential.clip(upper=min_region_mw), total)

    alloc = pd.Series(0.0, index=res.index)
    for region, group in res.groupby("region", sort=False):
        alloc[group.index] = take_cheapest(group.cap, floors[region])
    alloc += take_cheapest(res.cap - alloc, total - alloc.sum())
    return alloc[alloc > 1e-9]


def country_setting(table: dict, country: str, fallback: float) -> float:
    return table.get(country, table.get("default", fallback))


def ward_groups(values: np.ndarray, k: int) -> list[list[int]]:
    """
    Return the member positions of each group after the first n-k merges of
    agglomerative Ward linkage on the (unweighted) 1-D cost values.
    """
    n = len(values)
    if n <= k:
        return [[i] for i in range(n)]
    linkage = ward(np.asarray(values, dtype=float).reshape(-1, 1))
    members = {i: [i] for i in range(n)}
    for i, (a, b) in enumerate(linkage[: n - k, :2].astype(int)):
        members[n + i] = members.pop(a) + members.pop(b)
    return list(members.values())


def weighted_mean(x, weights) -> float:
    return float(np.average(x, weights=weights))


def weighted_quantile(x: pd.Series, weights: pd.Series, q: float) -> float:
    """
    Return the smallest x at which the cumulative weight reaches the share q.
    """
    order = np.argsort(x.values, kind="mergesort")
    cumulative = np.cumsum(weights.values[order])
    return float(x.values[order][np.searchsorted(cumulative, q * cumulative[-1])])


def build_clusters(
    res: pd.DataFrame, cfg: dict
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Cap, allocate and cluster the resources into supply-curve steps.

    Returns the steps (index ``cluster``) and their member resources.
    """
    min_region_mw = cfg["min_potential_per_region_gw"] * 1e3
    alloc = pd.concat(
        allocate_country(
            group,
            country_setting(cfg["max_potential_gw"], country, np.inf) * 1e3,
            min_region_mw,
        )
        for country, group in res.groupby("country")
    )
    chosen = res.loc[alloc.index].assign(alloc=alloc)

    cluster_rows, member_rows = [], []
    for region, group in chosen.groupby("region", sort=True):
        k = int(country_setting(cfg["n_clusters"], region_country(region), 1))
        steps = ward_groups(group.metric.values, k)
        steps.sort(
            key=lambda m: weighted_mean(group.metric.values[m], group.alloc.values[m])
        )
        for rank, positions in enumerate(steps):
            sub = group.iloc[positions]
            cluster_rows.append(
                {
                    "bus": region,
                    "country": region_country(region),
                    "step": rank,
                    "p_nom_max": sub.alloc.sum() / 1e3,
                    "n_resources": len(sub),
                    "temp_c_mean": weighted_mean(sub.temp_c, sub.alloc),
                    "depth_km_mean": weighted_mean(sub.depth_km, sub.alloc),
                }
            )
            member_rows.append(
                sub.assign(bus=region, step=rank)[
                    ["Cell_ID", "depth_km", "bus", "step", "alloc", "cap"]
                ]
            )

    clusters = pd.DataFrame(cluster_rows)
    clusters.index.name = "cluster"
    members = pd.concat(member_rows)
    cluster_of = {
        (bus, step): c for c, bus, step in zip(clusters.index, clusters.bus, clusters.step)
    }
    members["cluster"] = [cluster_of[key] for key in zip(members.bus, members.step)]
    return clusters, members.drop(columns="step")


def surface_price(
    bus_members: pd.DataFrame, ref_mw: float, q: float
) -> tuple[float, float]:
    """
    Return the quantile of the surface CAPEX and the implied FOM (%/year) over
    the cheapest ``ref_mw`` of a bus's supply curve, or all of it if the bus was
    allocated less.
    """
    members = bus_members.sort_values("metric", kind="mergesort")
    weights = take_cheapest(members.alloc, ref_mw)
    members, weights = members[weights > 0], weights[weights > 0]
    capex = weighted_quantile(members.capex_surf, weights, q)
    fom = 100 * (weights * members.om_surf).sum() / (weights * members.capex_surf).sum()
    return capex, fom


def costs_for_horizon(
    horizon: int,
    clusters: pd.DataFrame,
    members: pd.DataFrame,
    regions: gpd.GeoDataFrame,
    cfg: dict,
    cache: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """
    Return the step costs in a planning horizon, with the membership fixed.
    """
    path = data_file_for(horizon, cfg)
    if path not in cache:
        cache[path] = assign_regions(
            load_resources(path, cfg["currency_factor"], cfg["min_resource_mw"]),
            regions,
            cfg["snap_distance_km"],
        )
    multipliers = cfg["cost_multipliers"]
    res = cache[path].copy()
    res[["capex_well", "ann_well", "om_well"]] *= interpolate_multiplier(
        multipliers.get("subsurface"), horizon
    )
    res[["capex_surf", "ann_surf", "om_surf"]] *= interpolate_multiplier(
        multipliers.get("surface"), horizon
    )
    res["metric"] = cost_metric(res, cfg["cost_metric"])

    mem = members.join(
        res[["capex_well", "capex_surf", "om_well", "om_surf", "metric"]], how="left"
    )
    lost = mem.capex_well.isna()
    if lost.any():
        logger.warning(
            f"{horizon}: {lost.sum()} cluster members missing from {path}, "
            "averaging over the rest"
        )
        mem = mem[~lost]

    # Ranked by this horizon's costs, so the reference set can shift between years
    surface = {
        bus: surface_price(
            group, cfg["surface_cost_reference_gw"] * 1e3, cfg["surface_cost_quantile"]
        )
        for bus, group in mem.groupby("bus")
    }

    def weighted_sum(col: str) -> pd.Series:
        return (mem[col] * mem.alloc).groupby(mem.cluster).sum()

    alloc = mem.groupby("cluster").alloc.sum()
    out = clusters.copy()
    out["planning_horizon"] = horizon
    # EUR/MW to EUR/kW
    out["CAPEX_subsurface_mean"] = weighted_sum("capex_well") / alloc / 1e3
    out["CAPEX_surface_mean"] = weighted_sum("capex_surf") / alloc / 1e3
    out["FOM_well"] = 100 * weighted_sum("om_well") / weighted_sum("capex_well")
    out["CAPEX_surface"] = out.bus.map({b: v[0] for b, v in surface.items()}) / 1e3
    out["FOM_surface"] = out.bus.map({b: v[1] for b, v in surface.items()})

    if cfg["well_cost_basis"] == "subsurface":
        out["CAPEX_well"] = out.CAPEX_subsurface_mean
    elif cfg["well_cost_basis"] == "total_minus_surface":
        # Keeps each step's total cost exact; only the ORC sizing sees the regional price
        out["CAPEX_well"] = (
            out.CAPEX_subsurface_mean + out.CAPEX_surface_mean - out.CAPEX_surface
        )
    else:
        raise ValueError(
            "well_cost_basis must be 'subsurface' or 'total_minus_surface', "
            f"not {cfg['well_cost_basis']!r}."
        )
    out["CAPEX"] = out.CAPEX_well + out.CAPEX_surface
    return out


def build_egs_supply_curves(
    supply_curve: dict, regions_fn: str, horizons: list[int]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Return the EGS potentials (one row per supply-curve step and planning
    horizon) and the overlap of the bus regions with the steps (0/1).
    """
    cfg = DEFAULTS | dict(supply_curve)
    regions = gpd.read_file(regions_fn)
    if regions.crs is None:
        regions = regions.set_crs(4326)

    res = assign_regions(
        load_resources(cfg["cost_data"], cfg["currency_factor"], cfg["min_resource_mw"]),
        regions,
        cfg["snap_distance_km"],
    )
    res["metric"] = cost_metric(res, cfg["cost_metric"])
    clusters, members = build_clusters(res, cfg)

    cache = {cfg["cost_data"]: res.drop(columns="metric")}
    potentials = pd.concat(
        costs_for_horizon(int(h), clusters, members, regions, cfg, cache)
        for h in horizons
    )[
        [
            "bus",
            "planning_horizon",
            "p_nom_max",
            "CAPEX_well",
            "CAPEX_surface",
            "FOM_well",
            "FOM_surface",
            "CAPEX",
            "CAPEX_subsurface_mean",
            "CAPEX_surface_mean",
            "temp_c_mean",
            "depth_km_mean",
            "n_resources",
        ]
    ]

    overlap = pd.DataFrame(0.0, index=regions["name"], columns=clusters.index)
    for c, bus in clusters.bus.items():
        overlap.loc[bus, c] = 1.0
    overlap.index.name = "name"

    by_country = clusters.groupby("country").agg(
        GW=("p_nom_max", "sum"), regions=("bus", "nunique"), steps=("bus", "size")
    )
    logger.info(
        f"EGS supply curves: {clusters.p_nom_max.sum():.0f} GW in {len(clusters)} "
        f"steps across {clusters.bus.nunique()} regions\n{by_country}"
    )
    return potentials, overlap
