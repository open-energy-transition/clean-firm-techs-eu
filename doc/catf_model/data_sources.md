<!-- SPDX-FileCopyrightText: Contributors to clean-techs-firm-eu <https://github.com/open-energy-transition/clean-firm-techs-eu/> -->
<!-- SPDX-FileCopyrightText: Open Energy Transition gGmbH -->
<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Data sources

Sources of the data and assumptions added for the CATF model.

## `data/catf_model/custom_powerplants.csv`

Existing and planned nuclear, hard coal and lignite power plants with
plant-specific commissioning and decommissioning dates. It replaces these fuel
types from powerplantmatching (see `electricity: powerplants_filter`,
`custom_powerplants` and `custom_powerplants_fn` in
`config/catf_model/config.base.yaml`).

### Origin

The file was taken from the heat-demand-peaks project of Open Energy Transition
(2024):
[`data/custom_powerplants.csv` at commit `d14959e`](https://github.com/open-energy-transition/heat-demand-peaks/blob/d14959ed76604c180336acf4860c376f3028726c/data/custom_powerplants.csv).
In that project:

- the nuclear reactors were listed at reactor level, and the planned reactors
  were added from the sources in [Planned nuclear reactors](#planned-nuclear-reactors);
- the coal and lignite plants were added from the Beyond Fossil Fиuels
  *European Coal Plant Database* (status 15 April 2024,
  [beyondfossilfuels.org](https://beyondfossilfuels.org/europes-coal-exit/),
  contact data@bff.earth), published under the
  [Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1.0/).

### Planned nuclear reactors

Plants with `DateIn` after 2024. Their `DateOut` assumes 40 years of
operation, and 60 years for the French EPR2.

| Country | Plants | Capacity | Online | Sources |
|---|---|---|---|---|
| FR | Penly 3-4, Gravelines 7-8, Bugey 6-7 (EPR2) | 6 x 1650 MW | 2035, 2038, 2045 | [1], [2], [3], [19] |
| CZ | Dukovany 5-6, Temelín 3-4 | 2 x 1200 MW, 2400 MW | 2036, 2050 | [4], [5], [6] |
| HU | Paks 5-6 | 2 x 1200 MW | 2032 | [7], [8] |
| PL | Pomerania 1-3, Patnów 1-2 | 3 x 1250 MW, 2 x 1400 MW | 2033, 2035 | [9], [10], [11] |
| NL | Borssele 2-3 | 2 x 1650 MW | 2035 | [12] |
| RO | Cernavodă 3-4 | 2 x 720 MW | 2031, 2032 | [13] |
| SE | Ringhals 5-6 | 2 x 1250 MW | 2035 | [14] |
| SK | Bohunice 5 | 1200 MW | 2040 | [15] |
| SI | Krško 2 | 1200 MW | 2035 | [16] |
| GB | Hinkley Point C1-C2, Bradwell B1-B2 | 2 x 1630 MW, 2 x 1150 MW | 2029-2030 | [17], [18] |

1. <https://balkangreenenergynews.com/france-boosts-its-nuclear-energy-plan-with-eight-more-large-reactors/>
2. <https://www.tf1info.fr/environnement-ecologie/nucleaire-la-france-a-t-elle-les-moyens-de-construire-14-nouveaux-reacteurs-epr2-edf-2283039.html>
3. <https://www.tf1info.fr/societe/nucleaire-ce-que-l-on-sait-sur-les-futurs-reacteurs-epr2-dont-emmanuel-macron-a-annonce-la-construction-2210584.html>
4. <https://www.reuters.com/business/energy/cez-gets-3-initial-bids-build-new-unit-dukovany-nuclear-plant-2022-11-30/>
5. <https://apnews.com/article/czech-nuclear-reactors-fossil-fuels-energy-fafe34fb2e16446a75eeca7fddfe5e02>
6. <https://world-nuclear.org/information-library/country-profiles/countries-a-f/czech-republic.aspx>
7. <https://www.aa.com.tr/en/europe/russia-hungary-sign-schedule-for-construction-of-paks-2-nuclear-power-plant/3053667>
8. <https://world-nuclear.org/information-library/country-profiles/countries-g-n/hungary.aspx>
9. <https://english.elpais.com/international/2023-09-27/plans-for-polands-first-nuclear-power-plant-move-ahead-as-us-and-polish-officials-sign-an-agreement.html>
10. <https://world-nuclear.org/information-library/country-profiles/countries-o-s/poland.aspx>
11. <https://www.world-nuclear-news.org/Articles/Second-large-Polish-nuclear-plant-gets-approval>
12. <https://www.enerdata.net/publications/daily-energy-news/netherlands-plans-build-two-new-nuclear-reactors-2035.html>
13. <https://world-nuclear.org/information-library/country-profiles/countries-o-s/romania.aspx>
14. <https://world-nuclear.org/information-library/country-profiles/countries-o-s/sweden.aspx>
15. <https://cnpp.iaea.org/countryprofiles/Slovakia/Slovakia.htm>
16. <https://world-nuclear.org/information-library/country-profiles/countries-o-s/slovenia.aspx>
17. <https://world-nuclear.org/information-library/country-profiles/countries-t-z/united-kingdom.aspx>
18. <https://en.wikipedia.org/wiki/Nuclear_power_in_the_United_Kingdom>
19. <https://www.lemonde.fr/en/france/article/2023/07/20/france-chooses-third-location-for-next-generation-nuclear-reactors_6060561_7.html>

### Changes made for the CATF model (November 2026)

Compared with the heat-demand-peaks file, the following values were changed.
All other rows are unchanged.

**Country codes**: `EL` → `GR` (Agios Dimitrios, Melitis, Megalopoli B,
Ptolemaida V) and `KS` → `XK` (Kosovo A, Kosovo B), the codes used by
PyPSA-Eur. Plants with the wrong codes were otherwise not assigned to a bus.

**Capacities**: Chooz B1 and B2 from 1.5 to 1500 MW and Flamanville 3 from 1.6
to 1620 MW (values given in GW instead of MW).

**Coordinates** (the coordinates of other sites had been copied):
Belleville 1-2 (longitude typo 2875 → 2.875), Blayais 1-4, Flamanville 1-3,
Cofrentes, Trillo, Hartlepool A1-A2, Heysham A1-A2 and B1-B2, Torness 1-2.

**Nuclear decommissioning dates**, updated to national decisions:

| Plants | Old | New | Reason | Source |
|---|---|---|---|---|
| Doel 4, Tihange 3 (BE) | 2025 | 2035 | 10-year extension agreed with Engie | [WNA Belgium](https://world-nuclear.org/information-library/country-profiles/countries-a-f/belgium) |
| Loviisa 1-2 (FI) | 2027, 2030 | 2050 | licence extended to 2050 | [WNA Finland](https://world-nuclear.org/information-library/country-profiles/countries-a-f/finland) |
| Borssele 1 (NL) | 2034 | 2054 | operation beyond 2033 planned by law change | [WNA Netherlands](https://world-nuclear.org/information-library/country-profiles/countries-g-n/netherlands) |
| Beznau 1-2 (CH) | 2051 | 2033, 2032 | closure dates announced by Axpo | [WNA Switzerland](https://world-nuclear.org/information-library/country-profiles/countries-o-s/switzerland) |
| Almaraz 1-2, Ascó 1-2, Cofrentes, Vandellòs 2 (ES) | 2027-2034 | 2030-2035 | Spanish phase-out schedule (2027-2035) | [WNA Spain](https://world-nuclear.org/information-library/country-profiles/countries-o-s/spain) |
| Hartlepool A1-A2, Heysham A1-A2 (GB) | 2024 | 2030 | extended by EDF | [WNA United Kingdom](https://world-nuclear.org/information-library/country-profiles/countries-t-z/united-kingdom) |
| Sizewell B (GB) | 2035 | 2055 | 20-year extension planned by EDF | [WNA United Kingdom](https://world-nuclear.org/information-library/country-profiles/countries-t-z/united-kingdom) |

**Coal and lignite decommissioning dates**, capped at national coal phase-out
dates or set to the actual or announced closure. Source: Beyond Fossil Fuels,
[Europe's coal exit](https://beyondfossilfuels.org/europes-coal-exit/) and
[coal exit tracker](https://beyondfossilfuels.org/coal-exit-tracker/).

| Plants | Old | New |
|---|---|---|
| Ratcliffe (GB) | 2040 | 2024 (closed) |
| Moneypoint (IE) | 2040 | 2025 |
| Abono, Soto de Ribera (ES) | 2040 | 2025 |
| Alcudia II, Los Barrios, La Pereda (ES) | 2025-2030 | 2026 |
| Cordemais (FR) | 2040 | 2027 |
| Brindisi Nord, Monfalcone, Fiume Santo, Sulcis (IT) | 2027-2040 | 2020, 2025, 2028, 2028 |
| Oroszlány (HU) | 2040 | 2015 (closed) |
| Plomin (HR) | 2040 | 2033 |
| All Czech plants with later dates | 2040 | 2033 |
| Te-Tol, Šoštanj (SI) | 2040 | 2033 |
| Craiova II, Iași II, Govora (RO) | 2040 | 2032 |
| All Bulgarian plants with later dates | 2040 | 2038 |

German and Polish coal plants were left unchanged.

## Nuclear availability (`catf_model: nuclear`)

**Existing plants**: `p_max_pu` is the mean energy availability factor per
country over `availability_years` (2015-2024) from `data/nuclear_p_max_pu.csv`,
which PyPSA-Eur takes from the IAEA PRIS database:
<https://pris.iaea.org/PRIS/WorldStatistics/ThreeYrsEnergyAvailabilityFactor.aspx>.

**New plants** (`new_build_p_max_pu: 0.9`) are planned and extendable plants.
The value is an assumption based on the availability of fleets with high
availability:

- US nuclear fleet capacity factor 90.8-93.4% in 2016-2025: EIA, Electric
  Power Monthly, [Table 6.07.B](https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_6_07_b);
- best European fleets 2015-2024 (Slovenia 91.3%, Romania 91.3%, Finland
  90.8%): IAEA PRIS, link above.
