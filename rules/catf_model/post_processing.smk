# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT


rule export_marginal_prices:
    """Exports the marginal prices of the configured bus carriers as one CSV per carrier."""
    input:
        network=RESULTS + "networks/solved_{horizon}.nc",
    output:
        directory=directory(RESULTS + "csvs/marginal_prices/{horizon}"),
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
            RESULTS + "csvs/marginal_prices/{horizon}",
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


CATF_RUNS = (
    config["run"]["name"]
    if isinstance(config["run"]["name"], list)
    else [config["run"]["name"]]
)
CATF_COMPARISON = (
    "results/"
    + (config["run"]["prefix"] + "/" if config["run"].get("prefix") else "")
    + "catf_comparison/"
)


rule export_installed_capacities:
    """Extracts the installed capacity values across all runs"""
    params:
        runs=CATF_RUNS,
        planning_horizons=config["planning_horizons"],
        sectors=config_provider(
            "catf_model",
            "post_processing",
            "installed_capacity",
            "sectors",
        ),
    input:
        # Ordered by run, then horizon, as the script expects
        networks=expand(
            RESULTS + "networks/solved_{horizon}.nc",
            run=CATF_RUNS,
            horizon=config["planning_horizons"],
        ),
    output:
        csv=CATF_COMPARISON + "installed_capacities.csv",
    log:
        CATF_COMPARISON + "logs/export_installed_capacities.log",
    benchmark:
        CATF_COMPARISON + "benchmarks/export_installed_capacities"
    threads: 1
    resources:
        mem_mb=8000,
    script:
        scripts("catf_model/post_processing/export_installed_capacities.py")


rule plot_installed_capacity:
    """Plots the installed capacity by sector across all runs and planning horizons."""
    input:
        networks=expand(
            RESULTS + "networks/solved_{horizon}.nc",
            run=CATF_RUNS,
            horizon=config["planning_horizons"],
        ),
    output:
        plot=CATF_COMPARISON + "installed_capacity_by_sector.png",
        csv=CATF_COMPARISON + "installed_capacity_by_sector.csv",
    log:
        CATF_COMPARISON + "logs/plot_installed_capacity.log",
    threads: 1
    resources:
        mem_mb=8000,
    params:
        runs=CATF_RUNS,
        planning_horizons=config["planning_horizons"],
        sectors=config_provider(
            "catf_model",
            "post_processing",
            "installed_capacity",
            "sectors",
        ),
    script:
        scripts("catf_model/post_processing/plot_installed_capacity.py")


rule catf_post_processing:
    """Collects all CATF post-processing outputs."""
    input:
        rules.export_all_marginal_prices.input,
        rules.export_all_co2_emissions.input,
        rules.plot_installed_capacity.output,
