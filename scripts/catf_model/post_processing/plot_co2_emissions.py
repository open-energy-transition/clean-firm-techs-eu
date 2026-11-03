# SPDX-FileCopyrightText: Contributors to clean-firm-techs-eu <https://github.com/oet/clean-firm-techs-eu>
#
# SPDX-License-Identifier: MIT
"""
Plots the net CO2 emissions relative to 1990 across runs and planning horizons.

Reads the ``summary.csv`` written by ``export_co2_emissions`` for each run
(``results/{run}/csvs/co2_emissions/summary.csv``) and plots one line per run
with the planning horizons on the x-axis. The CO2 cap relative to 1990 (from
``co2_budget``) is drawn as a dashed line; it is taken from the first run.
"""

import logging

import matplotlib.pyplot as plt
import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

METRIC = "net emissions relative to 1990"
CAP = "cap relative to 1990"


def read_metric(path: str, metric: str) -> pd.Series:
    """Returns a metric of a CO2 emissions summary per planning horizon."""
    summary = pd.read_csv(path, index_col="metric").drop(columns="unit")
    values = summary.loc[metric].astype(float)
    values.index = values.index.astype(int)
    return values


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("plot_co2_emissions")

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    runs = snakemake.params.runs

    # Summaries are ordered by run
    data = pd.DataFrame(
        {run: read_metric(path, METRIC) for run, path in zip(runs, snakemake.input.summaries)}
    ).T
    cap = read_metric(snakemake.input.summaries[0], CAP)

    fig, ax = plt.subplots(figsize=(8, 5))
    for run in data.index:
        ax.plot(data.columns, data.loc[run], marker="o", linewidth=2.3, label=run)

    ax.plot(
        cap.index,
        cap.values,
        color="black",
        linestyle="--",
        marker="o",
        linewidth=1.5,
        label="CO2 cap",
    )

    ax.set_title("Net CO2 emissions by scenario")
    ax.set_xlabel("Year")
    ax.set_xticks(data.columns)
    ax.set_ylabel("Net emissions relative to 1990 (%)")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(title="Scenario")
    fig.tight_layout()

    fig.savefig(snakemake.output.plot, dpi=200)
    plt.close(fig)
    logger.info(f"Plotted net CO2 emissions of {len(runs)} runs to {snakemake.output.plot}.")
