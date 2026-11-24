# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT


rule extend_nuclear_lifetime:
    """Extends the lifetime of existing and planned nuclear plants to catf_model.nuclear.lifetime_extension years. Used by compose_network instead of powerplants.csv if the option is set (all runs by default)."""
    input:
        powerplants=resources("powerplants.csv"),
    output:
        resources("powerplants_nuclear_lifetime.csv"),
    log:
        # Named like the output, so that it is also excluded from shared resources
        logs("powerplants_nuclear_lifetime.log"),
    threads: 1
    resources:
        mem_mb=2000,
    params:
        lifetime=config_provider("catf_model", "nuclear", "lifetime_extension"),
    script:
        scripts("catf_model/extend_nuclear_lifetime.py")
