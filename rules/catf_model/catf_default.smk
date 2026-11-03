# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT

# Scenario files may use {prefix} in costs.custom_cost_fn (e.g.
# resources/{prefix}/{run}/custom_costs_x1.33.csv), so that they work with any
# run.prefix, e.g. config/catf_model/config.test.yaml.
_prefix = run.get("prefix", "")
for _overrides in scenarios.values():
    _fn = _overrides.get("costs", {}).get("custom_cost_fn")
    if _fn:
        _overrides["costs"]["custom_cost_fn"] = _fn.replace(
            "{prefix}/", f"{_prefix}/" if _prefix else ""
        )


include: "cost_sensitivity.smk"
include: "post_processing.smk"
