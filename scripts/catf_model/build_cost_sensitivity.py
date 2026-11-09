# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Build a custom cost file for the CATF established-technology cost sensitivity.

For every cost year of the configured planning horizons, the costs of the
technology groups in ``catf_model.cost_sensitivity_groups`` (e.g. investment
costs of solar, wind, batteries and gas power plants, and the natural gas fuel
price) are read from the technology-data cost files and multiplied by a factor
per group. The scaled values are appended to the default custom cost file,
which is then selected per scenario through ``costs: custom_cost_fn``.

The groups set in ``catf_model.cost_sensitivity`` are scaled each by its own
factor, so that several groups (e.g. onshore and offshore wind) can be combined
in one scenario. All other groups are written with factor 1.0, so the base
``cost_factors`` apply. The grid connection costs of the carriers in a group's
``grid_connection`` are not part of the cost file; they are scaled per carrier
in ``add_electricity_grid_connection`` (see ``cost_factors_with_sensitivity``
in rules/catf_model/cost_sensitivity.smk).

Instead of a factor, a group can be set by a dict with ``factor`` (default
1.0), ``year`` (technology-data year to take the values from, written for all
planning horizons) and ``value`` (absolute value in the unit of the cost row,
only for groups with a single row), e.g. ``hydrogen: {factor: 0.6, year: 2040}``.

Scaling is done on the cost table rather than via ``adjustments`` so that each
asset vintage is scaled exactly once under myopic foresight. Fixed operation
and maintenance costs are given in %/year of investment and therefore scale
along with it.
"""

import logging

import pandas as pd

from scripts._helpers import configure_logging

logger = logging.getLogger(__name__)


def get_spec(group: str, spec, rows: list) -> dict:
    """
    Return the settings of a group as a dict with factor, year and value.
    """
    spec = dict(spec) if isinstance(spec, dict) else {"factor": spec}
    if unknown := set(spec) - {"factor", "year", "value"}:
        raise ValueError(f"Unknown settings {sorted(unknown)} for group '{group}'.")
    if "value" in spec and (len(rows) != 1 or "factor" in spec):
        raise ValueError(f"'value' of group '{group}' needs a single row, no factor.")
    spec["factor"] = float(spec.get("factor", 1.0))
    if "year" in spec:
        spec["year"] = str(spec["year"])
    return spec


def get_scaling(
    groups: dict[str, dict[str, list[str]]], factors: dict
) -> dict[tuple[str, str], tuple[str, dict]]:
    """
    Return the group and its settings for every (technology, parameter) to scale.
    """
    unknown = set(factors) - set(groups)
    if unknown:
        raise ValueError(
            f"Unknown cost sensitivity groups {sorted(unknown)}, choose from {sorted(groups)}."
        )

    scaling = {}
    for group, factor in factors.items():
        # Carriers in grid_connection are scaled per carrier in add_electricity_grid_connection
        rows = [
            (tech, param)
            for param, techs in groups[group].items()
            if param != "grid_connection"
            for tech in techs
        ]
        spec = get_spec(group, factor, rows)
        for tech, param in rows:
            if (tech, param) in scaling:
                raise ValueError(
                    f"{param} of {tech} is in both groups "
                    f"'{scaling[(tech, param)][0]}' and '{group}'."
                )
            scaling[(tech, param)] = (group, spec)
    return scaling


def apply_cost_factors(
    costs: pd.DataFrame, base_factors: dict[str, float], param: str
) -> pd.DataFrame:
    """
    Return costs dataframe with base costs scaled for technologies specified in the config parameter 'cost_factors' in the format of the custom cost file.
    """
    for tech, factor in base_factors.items():
        if tech != "distribution grid reinforcement":
            tech_rows = costs.query("technology == @tech and parameter == @param").index

            if tech_rows.empty:
                logger.warning(
                    f"Technology {tech} not found to raise {param} by factor {factor}"
                )
                continue

            if factor != 1:
                costs.loc[tech_rows, "value"] = (
                    costs.loc[tech_rows, "value"] * factor
                ).round(6)
                costs.loc[tech_rows, "source"] = (
                    f"CATF established-technology base cost scaling by {factor}"
                )
    logger.info(f"Applied cost factor scaling to {param}")
    return costs


def scale_sensitivity_costs(
    costs: dict[str, pd.DataFrame],
    scaling: dict[tuple[str, str], tuple[str, dict]],
    cost_year: str,
) -> pd.DataFrame:
    """
    Return scaled cost rows for applying sensitivities in the format of the custom cost file.
    """
    rows = []
    for (tech, param), (group, spec) in scaling.items():
        year = spec.get("year", cost_year)
        row = costs[year].query("technology == @tech and parameter == @param").copy()
        if row.empty:
            raise ValueError(f"Missing cost entry for {tech} {param} in {year}.")
        original = row["value"].iloc[0]
        if "value" in spec:
            row["value"] = float(spec["value"])
            change = f"set to {spec['value']}"
        else:
            row["value"] = round(original * spec["factor"], 6)
            change = f"scaled by {spec['factor']}"
        row["further description"] = (
            f"costs_{year} value {original:.4f} {change} (group {group})"
        )
        rows.append(row)

    scaled = pd.concat(rows, ignore_index=True)
    scaled["planning_horizon"] = cost_year
    scaled["source"] = "CATF cost sensitivity"
    logger.info(f"Applied scaling for cost sensitivity scenarios in {cost_year}")
    return scaled


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "build_cost_sensitivity",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.sensitivity.yaml",
            ],
            run="high-wind",
        )
    configure_logging(snakemake)

    base_factors = snakemake.params.cost_factors or {}
    groups = snakemake.params.groups
    # Factors per group from the scenario, other groups at 1.0 so they keep the
    # base cost factors (e.g. solar +30%)
    factors = {group: 1.0 for group in groups} | (
        snakemake.params.cost_sensitivity or {}
    )
    scaling = get_scaling(groups, factors)
    cost_years = snakemake.params.cost_years
    default = apply_cost_factors(
        pd.read_csv(snakemake.input.default, dtype={"planning_horizon": "str"}),
        base_factors,
        "marginal_cost",
    )

    # Cost files of the planning horizons and of the years set with `year`
    costs = {
        year: apply_cost_factors(pd.read_csv(fn), base_factors, "investment")
        for fn, year in zip(snakemake.input.costs, snakemake.params.source_years)
    }
    scaled = [scale_sensitivity_costs(costs, scaling, year) for year in cost_years]

    df = pd.concat([default, *scaled], ignore_index=True)[default.columns]
    df.to_csv(snakemake.output[0], index=False)
    logger.info(
        f"Scaled {len(df) - len(default)} cost entries with factors {factors} for {cost_years}"
    )
