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

Rule ``build_cost_sensitivity`` scales all groups by the factor given in the
output file name. Rule ``build_scenario_cost_sensitivity`` scales only the
groups set in ``catf_model.cost_sensitivity``, each by its own factor, so that
several groups (e.g. onshore and offshore wind) can be combined in one scenario.

Scaling is done on the cost table rather than via ``adjustments`` so that each
asset vintage is scaled exactly once under myopic foresight. Fixed operation
and maintenance costs are given in %/year of investment and therefore scale
along with it.
"""

import logging

import pandas as pd

from scripts._helpers import configure_logging

logger = logging.getLogger(__name__)


def get_scaling(
    groups: dict[str, dict[str, list[str]]], factors: dict[str, float]
) -> dict[tuple[str, str], tuple[str, float]]:
    """
    Return the group and factor for every (technology, parameter) to scale.
    """
    unknown = set(factors) - set(groups)
    if unknown:
        raise ValueError(
            f"Unknown cost sensitivity groups {sorted(unknown)}, choose from {sorted(groups)}."
        )

    scaling = {}
    for group, factor in factors.items():
        for param, techs in groups[group].items():
            for tech in techs:
                if (tech, param) in scaling:
                    raise ValueError(
                        f"{param} of {tech} is in both groups "
                        f"'{scaling[(tech, param)][0]}' and '{group}'."
                    )
                scaling[(tech, param)] = (group, float(factor))
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
    costs: pd.DataFrame,
    scaling: dict[tuple[str, str], tuple[str, float]],
    cost_year: str,
) -> pd.DataFrame:
    """
    Return scaled cost rows for applying sensitivities in the format of the custom cost file.
    """
    keys = list(zip(costs.technology, costs.parameter))
    selection = [key in scaling for key in keys]
    scaled = costs.loc[selection].copy()

    if len(scaled) != len(scaling):
        found = set(zip(scaled.technology, scaled.parameter))
        missing = set(scaling) - found
        raise ValueError(f"Missing cost entries for {cost_year}: {sorted(missing)}")

    matched = [scaling[key] for key in zip(scaled.technology, scaled.parameter)]
    groups = [group for group, _ in matched]
    factors = [factor for _, factor in matched]
    scaled["value"] = (scaled["value"] * factors).round(6)
    scaled["planning_horizon"] = cost_year
    scaled["further description"] = [
        f"Original value {v:.4f} scaled by {f} (group {g})"
        for v, f, g in zip(costs.loc[selection, "value"], factors, groups)
    ]
    scaled["source"] = "CATF established-technology cost sensitivity"
    logger.info("Applied scaling for cost sensitivity scenarios")
    return scaled


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "build_scenario_cost_sensitivity",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.sensitivity.yaml",
            ],
            run="high-wind",
        )
    configure_logging(snakemake)

    base_factors = snakemake.params.cost_factors or {}
    groups = snakemake.params.groups
    if hasattr(snakemake.wildcards, "factor"):
        # build_cost_sensitivity: one factor for all groups
        factors = {group: float(snakemake.wildcards.factor) for group in groups}
    else:
        # build_scenario_cost_sensitivity: factors per group from the scenario
        factors = snakemake.params.cost_sensitivity or {}
    scaling = get_scaling(groups, factors)
    cost_years = snakemake.params.cost_years

    default = apply_cost_factors(
        pd.read_csv(snakemake.input.default, dtype={"planning_horizon": "str"}),
        base_factors,
        "marginal_cost",
    )

    scaled = [
        scale_sensitivity_costs(
            apply_cost_factors(pd.read_csv(fn), base_factors, "investment"),
            scaling,
            year,
        )
        for fn, year in zip(snakemake.input.costs, cost_years)
    ]

    df = pd.concat([default, *scaled], ignore_index=True)[default.columns]
    df.to_csv(snakemake.output[0], index=False)
    logger.info(
        f"Scaled {len(df) - len(default)} cost entries with factors {factors} for {cost_years}"
    )
