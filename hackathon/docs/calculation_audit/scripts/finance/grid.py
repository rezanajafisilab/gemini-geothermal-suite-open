from common import *
import numpy as np
from dioscuri_plant.components import Components
d, s = lead_session()
prices = engine.prices_for(None, s.chosen.brief)
eff = Components().electric_boiler_efficiency
print('eboiler eff', eff)
import datetime
days = [datetime.date(2027,1,1)+datetime.timedelta(i) for i in range(365)]
for e in s.candidates:
    a = e.alternative
    if a.uid not in ('A33','A39','A163','A102','A107'): continue
    plant, y, rules, pr, demand, model = rebuild(e)
    econ = dp.economics(plant, y, pr, rules=rules)
    eb = (a.sizes_mw or {}).get('electric_boiler', 0)
    daily = np.asarray(y.daily_mw.get('power', {}).get('electric_boiler') or [0.0])
    peak = daily.max()
    hours = y.electricity_gwh.get('electric_boiler',0)*1000/peak if peak else 0
    contracted = eb/eff*1000
    line = [m for (i,k,m) in econ.lines_heat if i=='Electric boiler grid capacity']
    std = 123.0*contracted/1e6
    months = {}
    for dd,v in zip(days, daily):
        months[dd.month] = max(months.get(dd.month,0), v)
    run_months = sum(1 for v in months.values() if v>0.01)
    monthly = (3.99*12*contracted + 6.24*sum(v*1000 for v in months.values()))/1e6
    tot = sum(m for _,_,m in econ.lines_heat)+sum(m for _,_,m in econ.lines_cold)
    mwh = (y.heat_delivered_gwh+y.cool_delivered_gwh)*1000
    print(a.uid, a.code, 'EB MW', eb, 'hours', round(hours), 'peak daily MW', round(peak,2), 'grid line', line, 'std', round(std,3), 'with monthly peaks', round(monthly,3), 'months running', run_months, 'LCOE', econ.lcoe_eur_per_mwh, 'cached', e.economics.lcoe_eur_per_mwh, 'LCOE w/ monthly peaks', round((tot - (line[0] if line else 0) + (monthly if hours>600 else (line[0] if line else 0)))*1e6/mwh,2))
