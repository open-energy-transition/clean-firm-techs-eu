<!-- SPDX-FileCopyrightText: Contributors to clean-techs-firm-eu <https://github.com/open-energy-transition/clean-firm-techs-eu/> -->
<!-- SPDX-FileCopyrightText: Open Energy Transition gGmbH -->
<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Release Notes

<!-- Upcoming Release -->
<!-- ================= -->

* Show biogenic fuels (e.g. biogas) as lower emissions of their consumers instead of negative emissions in the CO2 balance plot ([#53](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/53)).

* Increase `build_biomass_potentials` memory in the slurm profile to avoid out-of-memory failures ([#58](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/58)).

* Add slurm profiles for parallelising the scenario runs ([#52](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/52)).

* Add a scenario for running the model with sensitivities as individual level ([#35](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/35/changes)).

* Add a test config file ([#45](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/45))

* Add a fix for handling non-availability of stores with `co2` bus_carrier in the energy balance ([#47](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/47)).

* Add option `sector: electricity_demand_factors` to scale the electricity loads per carrier (households, services and rail; industry; agriculture) in all hours; High Need and Low Need scenarios increase and decrease the households, services and rail load by 10%, while industry and agriculture stay at 1.0 ([#39](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/39))

* Add export of annual energy balances per technology and bus carrier, a developer plot per run and planning horizon, and report plots comparing scenarios for electricity, heat, hydrogen and CO2 ([#29](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/29)).

* Add export of costs, capacities, generation and demand per run, and plots comparing scenarios: capacity and generation per carrier (electricity, heat, hydrogen, fuels and storage) and final demand by sector ([#28](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/28)).

* Adjust demand response in initial scenarios: High Need scenario limits EV demand response to 25% of BEVs, Low Need scenario enables residential heat demand response ([#33](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/33)).

* Update investment costs for solar related technologies by +30% ([#26](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/26)).

* Add initial scenarios (baseline, High Need, and Low Need) scaling investment costs of solar, wind, batteries and gas plants, and the gas fuel price ([#24](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/24)).

* Add scripts to export carrier-specific marginal prices and co2 emissions ([#23](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/23))

* Add config file for baseline scenario that includes a sector-coupled model with the following sectors `electricity`, `transport`, `biomass`, `heat`, `industry`, and `agriculture` ([#22](https://github.com/open-energy-transition/clean-firm-techs-eu/pull/22)). 
