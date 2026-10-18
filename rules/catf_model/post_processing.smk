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


rule catf_post_processing:
    """Collects all CATF post-processing outputs."""
    input:
        rules.export_all_marginal_prices.input,
