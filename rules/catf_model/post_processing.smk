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


rule export_energy_balances:
    """Exports the annual energy balance per technology and bus carrier as a long-format CSV."""
    input:
        network=RESULTS + "networks/solved_{horizon}.nc",
    output:
        RESULTS + "csvs/energy_balances/{horizon}.csv",
    log:
        RESULTS + "logs/export_energy_balances_{horizon}.log",
    benchmark:
        (RESULTS + "benchmarks/export_energy_balances_{horizon}")
    threads: 1
    resources:
        mem_mb=4000,
    script:
        scripts("catf_model/post_processing/export_energy_balances.py")


rule export_all_energy_balances:
    """Collects the energy balance CSVs for all runs and planning horizons."""
    input:
        expand(
            RESULTS + "csvs/energy_balances/{horizon}.csv",
            run=config["run"]["name"],
            horizon=(
                config["planning_horizons"][-1]
                if config["foresight"] == "perfect"
                else config["planning_horizons"]
            ),
        ),


rule plot_energy_balances_developer:
    """Plots the annual energy balance per bus carrier and technology for developers."""
    input:
        balance=RESULTS + "csvs/energy_balances/{horizon}.csv",
    output:
        RESULTS + "plots/energy_balances/developer_{horizon}.png",
    log:
        RESULTS + "logs/plot_energy_balances_developer_{horizon}.log",
    benchmark:
        (RESULTS + "benchmarks/plot_energy_balances_developer_{horizon}")
    threads: 1
    resources:
        mem_mb=2000,
    params:
        carriers=config_provider(
            "catf_model",
            "post_processing",
            "energy_balances",
            "developer",
            "carriers",
        ),
    script:
        scripts("catf_model/post_processing/plot_energy_balances_developer.py")


rule plot_all_energy_balances_developer:
    """Collects the developer energy balance plots for all runs and planning horizons."""
    input:
        expand(
            RESULTS + "plots/energy_balances/developer_{horizon}.png",
            run=config["run"]["name"],
            horizon=(
                config["planning_horizons"][-1]
                if config["foresight"] == "perfect"
                else config["planning_horizons"]
            ),
        ),


CATF_COMPARISON = (
    "results/"
    + (config["run"]["prefix"] + "/" if config["run"].get("prefix") else "")
    + "catf_comparison/"
)


rule plot_energy_balances:
    """Plots the energy balances of all runs and planning horizons per reporting carrier."""
    input:
        # Ordered by run, then horizon, as the script expects
        balances=expand(
            RESULTS + "csvs/energy_balances/{horizon}.csv",
            run=config["run"]["name"],
            horizon=config["planning_horizons"],
        ),
    output:
        plots=expand(
            CATF_COMPARISON + "plots/energy_balance_{carrier}.png",
            carrier=[
                c.lower().replace(" ", "_")
                for c in config["catf_model"]["post_processing"]["energy_balances"][
                    "report"
                ]["carriers"]
            ],
        ),
        csv=CATF_COMPARISON + "energy_balances_summary.csv",
    log:
        CATF_COMPARISON + "logs/plot_energy_balances.log",
    benchmark:
        CATF_COMPARISON + "benchmarks/plot_energy_balances"
    threads: 1
    resources:
        mem_mb=2000,
    params:
        runs=config["run"]["name"],
        planning_horizons=config["planning_horizons"],
        report=config_provider(
            "catf_model",
            "post_processing",
            "energy_balances",
            "report",
        ),
    script:
        scripts("catf_model/post_processing/plot_energy_balances.py")


rule catf_post_processing:
    """Collects all CATF post-processing outputs."""
    input:
        rules.plot_energy_balances.output,
        rules.export_all_marginal_prices.input,
        rules.export_all_co2_emissions.input,
        rules.export_all_energy_balances.input,
        rules.plot_all_energy_balances_developer.input,
