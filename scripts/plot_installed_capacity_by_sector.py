#!/usr/bin/env python3
"""Aggregate installed capacities from solved PyPSA networks across scenarios and horizons.

Outputs:
- Results/20-10-2026 Cost sensitivities/plots/installed_capacity_by_sector.csv
- Results/20-10-2026 Cost sensitivities/plots/installed_capacity_by_sector_2050.png
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pypsa
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = REPO_ROOT.parent / "Results" / "20-10-2026 Cost sensitivities"
CONFIG_PATH = REPO_ROOT / "config" / "config.catf.default.yaml"
PLANNING_HORIZONS = [2030, 2040, 2050]
SCENARIOS = {
    "low": "catf-cost-low",
    "central": "catf-cost-central",
    "high": "catf-cost-high",
}


def load_sector_map() -> dict[str, list[str]]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["catf_model"]["post_processing"]["installed_capacity"]["sectors"]


def collect_capacity_rows() -> pd.DataFrame:
    sector_map = load_sector_map()
    carrier_to_sector = {
        carrier: sector
        for sector, carriers in sector_map.items()
        for carrier in carriers
    }

    rows: list[pd.DataFrame] = []

    for scenario_label, scenario_folder in SCENARIOS.items():
        for year in PLANNING_HORIZONS:
            network_path = RESULTS_ROOT / scenario_folder / "networks" / f"solved_{year}.nc"
            if not network_path.exists():
                print(f"Skipping missing network: {network_path}")
                continue

            n = pypsa.Network(str(network_path))
            frames = []

            if not n.generators.empty:
                generators = n.generators[["carrier", "p_nom_opt"]].copy()
                generators = generators.rename(columns={"p_nom_opt": "capacity"})
                frames.append(generators)

            if not n.links.empty:
                links = n.links[["carrier", "p_nom_opt"]].copy()
                links = links.rename(columns={"p_nom_opt": "capacity"})
                frames.append(links)

            if not n.stores.empty:
                stores = n.stores[["carrier", "e_nom_opt"]].copy()
                stores = stores.rename(columns={"e_nom_opt": "capacity"})
                frames.append(stores)

            if not frames:
                continue

            df = pd.concat(frames, ignore_index=True)
            df["capacity"] = df["capacity"].fillna(0)
            df = df[df["carrier"].isin(carrier_to_sector)].copy()
            df["sector"] = df["carrier"].map(carrier_to_sector)
            df["scenario"] = scenario_label
            df["year"] = year

            df = (
                df.groupby(["scenario", "year", "sector", "carrier"], as_index=False)["capacity"]
                .sum()
            )
            rows.append(df)

    if not rows:
        raise FileNotFoundError(f"No network files were found under {RESULTS_ROOT}")

    capacity_df = pd.concat(rows, ignore_index=True)
    return capacity_df


def save_capacity_csv(capacity_df: pd.DataFrame) -> Path:
    out_dir = RESULTS_ROOT / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "installed_capacity_by_sector.csv"
    capacity_df.to_csv(out_file, index=False)
    print(f"Saved capacity CSV to: {out_file}")
    return out_file


def plot_capacity(capacity_df: pd.DataFrame) -> Path:
    out_dir = RESULTS_ROOT / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Total capacity per sector and scenario in 2050
    plot_df = (
        capacity_df[capacity_df["year"] == 2050]
        .groupby(["scenario", "sector"], as_index=False)["capacity"]
        .sum()
    )

    scenario_order = ["low", "central", "high"]
    sectors = sorted(plot_df["sector"].unique())

    fig, ax = plt.subplots(figsize=(10, 6))
    x = list(range(len(scenario_order)))
    width = 0.8 / max(len(sectors), 1)

    for idx, sector in enumerate(sectors):
        values = []
        for scenario in scenario_order:
            value = plot_df.loc[
                (plot_df["scenario"] == scenario) & (plot_df["sector"] == sector),
                "capacity",
            ]
            values.append(float(value.sum()) if not value.empty else 0.0)
        offset = (idx - (len(sectors) - 1) / 2) * width
        ax.bar(
            [xi + offset for xi in x],
            values,
            width=width,
            label=sector,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(scenario_order)
    ax.set_title("Installed capacity by sector in 2050")
    ax.set_xlabel("Scenario")
    ax.set_ylabel("Capacity")
    ax.grid(True, linestyle="--", alpha=0.35, axis="y")
    ax.legend(title="Sector", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()

    out_file = out_dir / "installed_capacity_by_sector_2050.png"
    fig.savefig(out_file, dpi=200)
    plt.close(fig)
    print(f"Saved plot to: {out_file}")
    return out_file


def main() -> None:
    capacity_df = collect_capacity_rows()
    save_capacity_csv(capacity_df)
    plot_capacity(capacity_df)


if __name__ == "__main__":
    main()
