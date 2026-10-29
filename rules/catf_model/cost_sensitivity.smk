# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: CC0-1.0


def cost_sensitivity_years(w):
    """Cost years used for the planning horizons of a run (see cost_year in rules/common.smk)."""
    cfg = get_config(w)
    return sorted({str(cfg["costs"]["year"] or h) for h in cfg["planning_horizons"]})


rule build_cost_sensitivity:
    """Builds the CATF custom cost file: baseline cost factors (e.g. solar +30%) followed by the sensitivity factor for the cost sensitivity scenarios."""
    input:
        costs=lambda w: [
            rules.retrieve_cost_data.output["costs"].format(horizon=year)
            for year in cost_sensitivity_years(w)
        ],
        default="data/custom_costs.csv",
    output:
        resources("custom_costs_x{factor}.csv"),
    log:
        logs("build_cost_sensitivity_x{factor}.log"),
    wildcard_constraints:
        factor=r"[0-9]+(\.[0-9]+)?",
    threads: 1
    resources:
        mem_mb=1000,
    params:
        cost_years=cost_sensitivity_years,
        cost_factors=config_provider("catf_model", "cost_factors", default={}),
    script:
        scripts("catf_model/build_cost_sensitivity.py")
