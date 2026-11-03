<!-- SPDX-FileCopyrightText: Contributors to clean-techs-firm-eu <https://github.com/open-energy-transition/clean-firm-techs-eu/> -->
<!-- SPDX-FileCopyrightText: Open Energy Transition gGmbH -->
<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Release Notes

<!-- Upcoming Release -->
<!-- ================= -->

* Add export of costs, capacities, generation and demand per run, and plots comparing scenarios: capacity and generation per carrier (electricity, heat, hydrogen, fuels and storage) and final demand by sector ([#28](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/28)).

* Adjust demand response in initial scenarios: High Need scenario limits EV demand response to 25% of BEVs, Low Need scenario enables residential heat demand response ([#33](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/33)).

* Update investment costs for solar related technologies by +30% ([#26](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/26)).

* Add initial scenarios (baseline, High Need, and Low Need) scaling investment costs of solar, wind, batteries and gas plants, and the gas fuel price ([#24](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/24)).

* Add scripts to export carrier-specific marginal prices and co2 emissions ([#23](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/23))

* Add config file for baseline scenario that includes a sector-coupled model with the following sectors `electricity`, `transport`, `biomass`, `heat`, `industry`, and `agriculture` ([#22](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/22)). 
