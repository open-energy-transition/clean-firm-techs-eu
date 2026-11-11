# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: CC0-1.0


def cost_sensitivity_years(w):
    """Cost years used for the planning horizons of a run (see cost_year in rules/common.smk)."""
    cfg = get_config(w)
    return sorted({str(cfg["costs"]["year"] or h) for h in cfg["planning_horizons"]})


def cost_factors_with_sensitivity(w):
    """Base cost factors of a run, with the grid connection factor of each carrier multiplied by the sensitivity factor of its group (used in add_electricity_grid_connection)."""
    cfg = get_config(w)["catf_model"]
    factors = copy.deepcopy(cfg.get("cost_factors") or {})
    grid = factors.setdefault("distribution grid reinforcement", {})
    for group, factor in (cfg.get("cost_sensitivity") or {}).items():
        for carrier in cfg["cost_sensitivity_groups"][group].get("grid_connection", []):
            grid[carrier] = round(grid.get(carrier, 1.0) * factor, 6)
    return factors


rule build_cost_sensitivity:
    """Builds the CATF custom cost file of a run: baseline cost factors (e.g. solar +30%) followed by the per-group factors in catf_model.cost_sensitivity and the absolute values in catf_model.cost_overwrites."""
    input:
        costs=lambda w: [
            rules.retrieve_cost_data.output["costs"].format(horizon=year)
            for year in cost_sensitivity_years(w)
        ],
        default="data/custom_costs.csv",
    output:
        resources("custom_costs.csv"),
    log:
        # Named like the output, so that it is also excluded from shared resources
        logs("custom_costs.log"),
    threads: 1
    resources:
        mem_mb=1000,
    params:
        cost_years=cost_sensitivity_years,
        cost_factors=config_provider("catf_model", "cost_factors", default={}),
        groups=config_provider("catf_model", "cost_sensitivity_groups"),
        cost_sensitivity=config_provider("catf_model", "cost_sensitivity", default={}),
        cost_overwrites=config_provider("catf_model", "cost_overwrites", default={}),
        cost_overwrite_years=config_provider(
            "catf_model", "cost_overwrite_years", default=[]
        ),
    script:
        scripts("catf_model/build_cost_sensitivity.py")
