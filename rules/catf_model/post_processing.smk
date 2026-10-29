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


CATF_RUNS = (
    config["run"]["name"]
    if isinstance(config["run"]["name"], list)
    else [config["run"]["name"]]
)
CATF_COMPARISON = "results/" + (
    config["run"]["prefix"] + "/" if config["run"].get("prefix") else ""
)


rule plot_co2_emissions:
    """Plots the net CO2 emissions relative to 1990 of all runs against the CO2 cap."""
    input:
        # Ordered by run, as the script expects
        summaries=expand(
            RESULTS + "csvs/co2_emissions/summary.csv",
            run=CATF_RUNS,
        ),
    output:
        plot=CATF_COMPARISON + "plots/co2_emissions_comparison.png",
    log:
        CATF_COMPARISON + "logs/plot_co2_emissions.log",
    threads: 1
    resources:
        mem_mb=2000,
    params:
        runs=CATF_RUNS,
    script:
        scripts("catf_model/post_processing/plot_co2_emissions.py")


rule export_statistics:
    """Exports the statistics of a PyPSA network for a given planning horizon"""
    input:
        network=RESULTS + "networks/solved_{horizon}.nc",
    output:
        costs=RESULTS + "csvs/statistics/summary_costs_{horizon}.csv",
        capacities=RESULTS + "csvs/statistics/optimal_capacities_{horizon}.csv",
        generation=RESULTS + "csvs/statistics/generation_{horizon}.csv",
        demand=RESULTS + "csvs/statistics/demand_{horizon}.csv",
    log:
        RESULTS + "logs/export_statistics_{horizon}.log",
    benchmark:
        RESULTS + "benchmarks/export_statistics_{horizon}"
    threads: 1
    resources:
        mem_mb=4000,
    script:
        scripts("catf_model/post_processing/export_statistics.py")


rule export_all_statistics:
    """Collects the cost summary CSVs for all runs (one per sensitivity run) and planning horizons."""
    input:
        expand(
            RESULTS + "csvs/statistics/summary_costs_{horizon}.csv",
            run=CATF_RUNS,
            horizon=config["planning_horizons"],
        ),



rule export_statistics_summary:
    """Summarises the installed capacity, generation and demand by sector across all runs from the per-run statistics CSVs"""
    params:
        runs=CATF_RUNS,
        planning_horizons=config["planning_horizons"],
        sectors=config_provider(
            "catf_model",
            "post_processing",
            "sectors",
        ),
    input:
        # Ordered by run, then horizon, as the script expects
        capacities=expand(
            RESULTS + "csvs/statistics/optimal_capacities_{horizon}.csv",
            run=CATF_RUNS,
            horizon=config["planning_horizons"],
        ),
        generation=expand(
            RESULTS + "csvs/statistics/generation_{horizon}.csv",
            run=CATF_RUNS,
            horizon=config["planning_horizons"],
        ),
        demand=expand(
            RESULTS + "csvs/statistics/demand_{horizon}.csv",
            run=CATF_RUNS,
            horizon=config["planning_horizons"],
        ),
    output:
        csv=CATF_COMPARISON + "statistics_summary.csv",
    log:
        CATF_COMPARISON + "logs/export_statistics_summary.log",
    benchmark:
        CATF_COMPARISON + "benchmarks/export_statistics_summary"
    threads: 1
    resources:
        mem_mb=8000,
    script:
        scripts("catf_model/post_processing/export_statistics_summary.py")


rule plot_statistics:
    """Plots the statistics by sector across all runs and planning horizons."""
    input:
        statistics_summary=rules.export_statistics_summary.output.csv
    output:
        capacities=CATF_COMPARISON + "plots/installed_capacity_by_sector.png",
        generation=CATF_COMPARISON + "plots/generation_by_sector.png",
        #costs=CATF_COMPARISON + "plots/costs_by_sector.png",
        demand=CATF_COMPARISON + "plots/demand_by_sector.png",
    log:
        CATF_COMPARISON + "logs/plot_statistics.log",
    threads: 1
    resources:
        mem_mb=8000,
    params:
        statistics=["capacities","generation","demand"],
        sectors=config_provider(
            "catf_model",
            "post_processing",
            "sectors",
        ),
        colors=config_provider(
            "catf_model",
            "post_processing",
            "colors"
        )
    script:
        scripts("catf_model/post_processing/plot_statistics.py")


rule catf_post_processing:
    """Collects all CATF post-processing outputs."""
    input:
        rules.export_all_marginal_prices.input,
        rules.export_all_co2_emissions.input,
        rules.plot_co2_emissions.output,
        rules.plot_statistics.output,
        rules.export_all_statistics.input,
