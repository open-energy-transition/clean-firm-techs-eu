# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Plots the annual energy balance of one run and planning horizon for developers.

Reads the CSV of ``export_energy_balances`` and draws one panel per bus carrier
with a horizontal bar per ``component: carrier``, sorted by magnitude and
coloured by category (technology, storage, transmission). Positive values are
supply into the bus carrier, negative values consumption. The bus carriers are
set in ``catf_model.post_processing.energy_balances.developer.carriers``
(``all`` plots every bus carrier).
"""

import logging

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)

CATEGORY_COLORS = {
    "technology": "tab:blue",
    "storage": "tab:orange",
    "transmission": "tab:grey",
}

# Figure height per bar and per panel (title and axis label) in inches
ROW_HEIGHT = 0.2
PANEL_MARGIN = 0.9


def scale_unit(unit: str) -> tuple[float, str]:
    """Returns the factor and label to show a MWh or t unit in TWh or Mt."""
    if unit.startswith("t"):
        return 1e-6, "Mt" + unit[1:]
    return 1e-6, unit.replace("MWh", "TWh")


def plot_balances(
    balance: pd.DataFrame, carriers: list[str], title: str
) -> plt.Figure:
    """Draws one horizontal bar panel per bus carrier."""
    panels = []
    for carrier in carriers:
        df = balance[balance.bus_carrier == carrier]
        df = df.assign(label=df.component + ": " + df.carrier)
        df = df.reindex(df.value.abs().sort_values().index)
        panels.append((carrier, df))

    # Each bar gets one row of the same height in every panel, plus space for
    # the title and axis label of each panel
    rows = [max(len(df), 1) for _, df in panels]
    fig, axes = plt.subplots(
        len(panels),
        1,
        figsize=(11, sum(rows) * ROW_HEIGHT + len(panels) * PANEL_MARGIN),
        height_ratios=rows,
        layout="constrained",
        squeeze=False,
    )

    for ax, n_rows, (carrier, df) in zip(axes[:, 0], rows, panels):
        factor, unit = scale_unit(df.unit.iloc[0] if len(df) else "MWh")
        ax.barh(
            df.label,
            df.value * factor,
            color=df.category.map(CATEGORY_COLORS),
            edgecolor="k",
            height=0.7,
        )
        ax.set_ylim(-0.5, n_rows - 0.5)
        ax.axvline(0, color="k", linewidth=0.8)
        ax.set_title(f"{carrier} (net: {df.value.sum() * factor:.2f} {unit})")
        ax.set_xlabel(f"Energy balance [{unit}]")
        ax.grid(axis="x", alpha=0.3)

    handles = [Patch(color=c, label=k) for k, c in CATEGORY_COLORS.items()]
    fig.legend(handles=handles, loc="outside lower center", frameon=False, ncol=3)
    fig.suptitle(title)

    return fig


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "plot_energy_balances_developer",
            horizon=2050,
            configfiles="config/catf_model/config.base.yaml",
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    balance = pd.read_csv(snakemake.input.balance)

    carriers = snakemake.params.carriers
    if carriers == "all":
        carriers = sorted(balance.bus_carrier.unique())
    missing = set(carriers) - set(balance.bus_carrier)
    if missing:
        logger.warning(f"Bus carriers not in the energy balance: {sorted(missing)}")
    carriers = [c for c in carriers if c not in missing]

    title = f"Energy balance, {snakemake.wildcards.get('run', '')} {snakemake.wildcards.horizon}"
    fig = plot_balances(balance, carriers, title.replace("  ", " "))
    fig.savefig(snakemake.output[0], bbox_inches="tight", dpi=150)

    logger.info(f"Plotted {len(carriers)} bus carriers to {snakemake.output[0]}.")
