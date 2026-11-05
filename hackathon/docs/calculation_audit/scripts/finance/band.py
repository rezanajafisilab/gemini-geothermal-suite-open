from common import *
d, s = lead_session()
ents=[e for e in s.candidates if e.alternative.role in ('chosen','candidate')]
over=[]
for e in ents:
    el = sum(v for v in e.year.electricity_gwh.values())
    gas = e.year.purchased_gas_gwh*3.6*1e3/1.11  # GJ GCV
    if el>20 or e.alternative.uid in ('A1','A2','A33','A39','A163','A47'):
        mwh=(e.year.heat_delivered_gwh+e.year.cool_delivered_gwh)*1e3
        print(e.alternative.uid, e.alternative.code, 'elec GWh', round(el,2), 'gas GJ(GCV)', round(gas), 'LCOE', e.economics.lcoe_eur_per_mwh, 'LCOE at band IE 130.7', round(e.economics.lcoe_eur_per_mwh - el*1e3*(185.7-130.7)/mwh,2) if el>20 else '')
    if el>20: over.append(e.alternative.uid)
print('designs >20 GWh electricity:', len(over), 'of', len(ents))
