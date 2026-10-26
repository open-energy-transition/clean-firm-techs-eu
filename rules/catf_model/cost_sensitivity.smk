# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: CC0-1.0


def cost_sensitivity_years(w):
    """Cost years used for the planning horizons of a run (see cost_year in rules/common.smk)."""
    cfg = get_config(w)
    return sorted({str(cfg["costs"]["year"] or h) for h in cfg["planning_horizons"]})


rule build_cost_sensitivity:
    """Scales established-technology costs by a factor for the CATF cost sensitivity."""
    input:
        costs=lambda w: [
            rules.retrieve_cost_data.output["costs"].format(horizon=year)
            for year in cost_sensitivity_years(w)
        ],
        # Unscaled default file from the base config. The scenario's custom_cost_fn
        # is the output of this rule, so it cannot be used here.
        default=config["costs"]["custom_cost_fn"],
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
    script:
        scripts("catf_model/build_cost_sensitivity.py")
