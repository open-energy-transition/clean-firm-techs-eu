# SPDX-FileCopyrightText: clean-firm-techs-eu authors
#
# SPDX-License-Identifier: MIT
"""
Extends the lifetime of existing and planned nuclear power plants.

Sets ``DateOut`` of the nuclear plants in the power plant list to
``DateIn + lifetime - 1`` (``catf_model.nuclear.lifetime_extension``, e.g. 80
years), irrespective of their decommissioning date, unless ``DateOut`` is
later already. Plants decommissioned before the power plant list was built
(``electricity.custom_powerplants``, e.g. ``DateOut >= 2024``) are not in the
list and stay closed.

The list is read by ``add_existing_baseyear`` (existing plants, first horizon)
and ``add_planned_capacities`` (planned plants, every horizon), so the
extension applies before plants closing before the first horizon are dropped.
"""

import logging

import pandas as pd

from scripts._helpers import configure_logging, set_scenario_config

logger = logging.getLogger(__name__)


def extend_nuclear_lifetime(ppl: pd.DataFrame, lifetime: int) -> pd.DataFrame:
    """Returns the power plants with DateOut of nuclear plants at least DateIn + lifetime - 1."""
    ppl = ppl.copy()
    no_date_in = (ppl.Fueltype == "Nuclear") & ppl.DateIn.isna()
    if no_date_in.any():
        logger.warning(
            f"{no_date_in.sum()} nuclear plants without DateIn keep their DateOut "
            f"(no lifetime extension): {ppl.loc[no_date_in, 'Name'].tolist()}"
        )
    nuclear = (ppl.Fueltype == "Nuclear") & ~no_date_in
    date_out = ppl.loc[nuclear, "DateIn"] + lifetime - 1
    before = ppl.loc[nuclear, "DateOut"]
    ppl.loc[nuclear, "DateOut"] = before.clip(lower=date_out).fillna(date_out)
    extended = ppl.index.isin(before.index[ppl.loc[nuclear, "DateOut"] != before])
    logger.info(
        f"Extended the lifetime of {extended.sum()} of {nuclear.sum()} nuclear plants "
        f"({ppl.loc[extended, 'Capacity'].sum() / 1e3:.1f} GW) to {lifetime} years"
    )
    return ppl


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "extend_nuclear_lifetime",
            configfiles=[
                "config/catf_model/config.base.yaml",
                "config/catf_model/config.advanced.yaml",
            ],
            run="high-nuclear",
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    ppl = pd.read_csv(snakemake.input.powerplants, index_col=0)
    ppl = extend_nuclear_lifetime(ppl, snakemake.params.lifetime)
    ppl.to_csv(snakemake.output[0])
