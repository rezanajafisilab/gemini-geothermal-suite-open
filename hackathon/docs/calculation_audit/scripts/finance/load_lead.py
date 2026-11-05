import json, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent.agent import Session
d = json.load(open(str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/hackathon/evals/runs/lead/challenge.json'))
s = Session.from_dict(d['session'])
c = s.chosen
print(type(c))
print(c.alternative.code, c.alternative.uid)
e = c.economics
y = c.year
print('plant', e.plant)
print('LCOH', e.lcoh_eur_per_mwh, 'LCOC', e.lcoc_eur_per_mwh, 'LCOE', e.lcoe_eur_per_mwh, 'capex', e.capex_meur, 'opex', e.opex_meur_per_year)
for it in e.capex_items: print(it)
print('heat lines'); [print(' ', l) for l in e.lines_heat]
print('cold lines'); [print(' ', l) for l in e.lines_cold]
print('heat_delivered', y.heat_delivered_gwh, 'cool', y.cool_delivered_gwh)
print('heat_split', y.heat_split_gwh); print('cool_split', y.cool_split_gwh)
print('elec', y.electricity_gwh); print('gas purchased', y.purchased_gas_gwh, 'sold', getattr(y,'produced_gas_sold_gwh',None), 'flared', getattr(y,'produced_gas_flared_gwh',None))
print('co2', y.co2_t); print('peak brine', y.peak_brine_heat_mw, 'free cooling', getattr(y,'free_cooling_mw',None))
print('network', y.network); print('storage', y.storage, 'solar', y.solar)
print('abs cop', y.absorption_cop, 'max brine cooling', getattr(y,'max_brine_cooling_k',None))
print('co2 saving', e.co2_saving_vs_gas)
print('notes'); 
for sr in s.searches:
    for k in ('notes',):
        pass
print([k for k in d['session'].keys()])
