from common import *
d, s = lead_session()
c = s.chosen
plant, year, rules, prices, demand, model = rebuild(c)
ref = s.reference
print('brief rules', c.brief.rules, 'prices', c.brief.prices)
rplant = engine.plant_of(ref.alternative)
ryear = dp.simulate_year(rplant, demand, model, rules)
recon = dp.economics(rplant, ryear, prices, rules=rules)
econ = dp.economics(plant, year, prices, reference=(ryear, recon), rules=rules)
print('plant', plant)
print('LCOH', econ.lcoh_eur_per_mwh, c.economics.lcoh_eur_per_mwh, 'LCOC', econ.lcoc_eur_per_mwh, c.economics.lcoc_eur_per_mwh,
      'LCOE', econ.lcoe_eur_per_mwh, c.economics.lcoe_eur_per_mwh, 'capex', econ.capex_meur, c.economics.capex_meur, 'opex', econ.opex_meur_per_year)
for it in econ.capex_items: print(it)
print('heat lines'); [print(' ', l) for l in econ.lines_heat]
print('cold lines'); [print(' ', l) for l in econ.lines_cold]
y=year
print('heat_delivered', y.heat_delivered_gwh, 'demand', y.heat_demand_gwh, 'cool', y.cool_delivered_gwh, y.cool_demand_gwh)
print('heat_split', y.heat_split_gwh); print('cool_split', y.cool_split_gwh)
print('elec', y.electricity_gwh); print('gas purchased', y.purchased_gas_gwh, 'burned', y.produced_gas_burned_gwh, 'sold', y.produced_gas_sold_gwh, 'flared', y.produced_gas_flared_gwh)
print('co2', y.co2_t); print('peak brine', y.peak_brine_heat_mw, 'free cooling', y.free_cooling_mw)
print('network', y.network); print('storage', y.storage, 'solar', y.solar)
print('abs cop', y.absorption_cop, 'max brine cooling', y.max_brine_cooling_k, 'hp cop', y.heat_pump_cop)
print('co2 saving', econ.co2_saving_vs_gas, 'co2 total', econ.co2_t_per_year)
print('REF plant', rplant); print('REF LCOH', recon.lcoh_eur_per_mwh, ref.economics.lcoh_eur_per_mwh, 'LCOC', recon.lcoc_eur_per_mwh, ref.economics.lcoc_eur_per_mwh, 'capex', recon.capex_meur)
for l in recon.lines_heat+recon.lines_cold: print('  ref', l)
print('REF heat split', ryear.heat_split_gwh, 'gas', ryear.purchased_gas_gwh, 'co2', ryear.co2_t, 'elec', ryear.electricity_gwh, 'cool', ryear.cool_split_gwh)
pickle.dump(dict(plant=plant, year=year, econ=econ, rplant=rplant, ryear=ryear, recon=recon, rules=rules, prices=prices), open(HERE+'/lead.pkl','wb'))
