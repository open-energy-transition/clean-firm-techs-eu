# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: CC0-1.0

# Cost years used for the configured planning horizons (see cost_year in rules/common.smk)
CATF_COST_YEARS = sorted(
    {str(config["costs"]["year"] or h) for h in config["planning_horizons"]}
)


rule build_cost_sensitivity:
    """Scales established-technology costs by a factor for the CATF cost sensitivity."""
    input:
        costs=[
            rules.retrieve_cost_data.output["costs"].format(horizon=year)
            for year in CATF_COST_YEARS
        ],
        default=config["costs"]["custom_cost_fn"],
    output:
        "resources/catf_model/custom_costs_x{factor}.csv",
    log:
        "logs/catf_model/build_cost_sensitivity_x{factor}.log",
    wildcard_constraints:
        factor=r"[0-9]+(\.[0-9]+)?",
    threads: 1
    resources:
        mem_mb=1000,
    params:
        cost_years=CATF_COST_YEARS,
    script:
        scripts("catf_model/build_cost_sensitivity.py")
