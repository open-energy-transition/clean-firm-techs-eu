# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT


rule export_marginal_prices:
    """Exports the marginal prices of the configured bus carriers as one CSV per carrier."""
    input:
        network=RESULTS + "networks/solved_{horizon}.nc",
    output:
        directory=directory(RESULTS + "csvs/marginal_prices/{horizon}"),
        snapshot_weightings=RESULTS + "csvs/snapshot_weightings/{horizon}.csv",
    log:
        RESULTS + "logs/export_marginal_prices_{horizon}.log",
    benchmark:
        (RESULTS + "benchmarks/export_marginal_prices_{horizon}")
    threads: 1
    resources:
        mem_mb=4000,
    params:
        carriers=config_provider(
            "catf_model",
            "post_processing",
            "marginal_prices",
            "carriers",
        ),
    script:
        scripts("catf_model/post_processing/export_marginal_prices.py")


rule export_all_marginal_prices:
    """Collects the marginal price CSVs for all runs and planning horizons."""
    input:
        expand(
            [
                RESULTS + "csvs/marginal_prices/{horizon}",
                RESULTS + "csvs/snapshot_weightings/{horizon}.csv",
            ],
            run=config["run"]["name"],
            horizon=(
                config["planning_horizons"][-1]
                if config["foresight"] == "perfect"
                else config["planning_horizons"]
            ),
        ),


rule export_co2_emissions:
    """Exports CO2 emissions of all planning horizons, absolute and relative to 1990, and their breakdown by technology."""
    input:
        networks=expand(
            RESULTS + "networks/solved_{horizon}.nc",
            horizon=config["planning_horizons"],
            allow_missing=True,
        ),
        eurostat=resources("eurostat_energy_balances.csv"),
        co2=rules.retrieve_ghg_emissions.output["csv"],
    output:
        summary=RESULTS + "csvs/co2_emissions/summary.csv",
        by_technology=RESULTS + "csvs/co2_emissions/by_technology.csv",
    log:
        RESULTS + "logs/export_co2_emissions.log",
    benchmark:
        RESULTS + "benchmarks/export_co2_emissions"
    threads: 1
    resources:
        mem_mb=8000,
    params:
        countries=config_provider("countries"),
        sector=config_provider("sector"),
        co2_budget=config_provider("co2_budget"),
        foresight=config_provider("foresight"),
        planning_horizons=config_provider("planning_horizons"),
    script:
        scripts("catf_model/post_processing/export_co2_emissions.py")


rule export_all_co2_emissions:
    """Collects the CO2 emission CSVs for all runs."""
    input:
        expand(
            RESULTS + "csvs/co2_emissions/summary.csv",
            run=config["run"]["name"],
        ),


rule catf_post_processing:
    """Collects all CATF post-processing outputs."""
    input:
        rules.export_all_marginal_prices.input,
        rules.export_all_co2_emissions.input,
