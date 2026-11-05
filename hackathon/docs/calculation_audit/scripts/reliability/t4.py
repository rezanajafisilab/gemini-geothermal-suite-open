from common import *
from dioscuri_plant import failure_costs as fc
from dioscuri_plant.economics import crf
for uid in ('A1','A47'):
    a, e = alt(uid)
    b = DesignBrief(**e['brief']); r = engine.rules_for(b)
    p = engine.plant_of(a)
    base = dp.simulate_year(p, DEMAND, MODEL, r)
    runs = fc.outage_runs(p, DEMAND, MODEL, r, prices=PRICES, base=base)
    out = fc.failure_costs(p, DEMAND, MODEL, r, prices=PRICES, base=base)
    print(uid, a.code, 'total', out['total_keur'], 'with spare', out['with_spare']['total_keur'], 'lost', out['lost_mwh'])
    tot=0
    for run in runs:
        if run['kind'] is None: print('  skip', run['name']); continue
        rate = fc.RATES[run['kind']]
        days = rate.no_spare_days if rate.no_spare_days else rate.repair_days
        n = run['count']*rate.per_year
        share = n*days/365
        t = share*(run['running_meur']*1000 + (run['heat_mwh']+run['cold_mwh'])*122/1000) + n*rate.repair_meur*1000
        tot+=t
        print('  ', run['unit'], 'n', n, 'days', round(days,3), 'running all-year k€', round(run['running_meur']*1000,1), 'lost all-year MWh', round(run['heat_mwh']+run['cold_mwh'],1), 'hand k€', round(t,2))
    print('  hand total', round(tot,1))
    s = out['spare_esp']
    print('  spare', {k: s[k] for k in ('yearly_keur','saving_keur','net_keur','worth','break_even_per_year','life_years','discount_rate')})
    d = [run for run in runs if run['kind']=='esp'][0]
    gap = (120-7)/365
    per = gap*(d['running_meur']*1000 + (d['heat_mwh']+d['cold_mwh'])*122/1000)
    cost = 0.3*crf(PRICES.discount_rate, PRICES.wells_life_years)*1000
    print('  hand spare: saving', round(0.5*per,1), 'cost', round(cost,1), 'net', round(0.5*per-cost,1), 'break-even', round(cost/per,4))
