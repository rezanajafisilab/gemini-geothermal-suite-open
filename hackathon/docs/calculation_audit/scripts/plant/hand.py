"""Independent re-implementation of the lead design's year (1 doublet @3000 m, HP 0.5, boiler 30, chillers 15, FC)."""
import sys, json
import numpy as np
from dataclasses import replace
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
import dioscuri_plant as dp
from dioscuri_plant import weather
brief = DesignBrief(); rules = engine.rules_for(brief); demand = engine.demand_of(brief)
model = engine.doublet_model(rules)
H, C = demand.arrays()
print('demand GWh', H.sum()*24/1000, C.sum()*24/1000, H.max(), C.max(), np.argmax(H), np.argmax(C))
rho, cp = 1030., 3990.
ucb = rho*cp/3600/1e6  # MW/K per m3/h
TS, TR = 100., 60.
eta = 0.5
stop = set(range(189, 224))
wb = weather.typical_year()['wet_bulb_c']
def cop_hp(tout): return eta*(TS+273.15)/(TS-tout)
res = dict(geo=0, hp=0, hp_el=0, boiler=0, short=0, fuel=0, used=0, flared=0, ch4=0, pumps=0, free=0, chill=0, chill_el=0, tower=0, brine=0, maxcool=0)
cop_ch = 0.5*(18+273.15)/(35-18)
for d in range(365):
    h = H[d]; cw = h/(TS-TR)
    q = 0.0
    if d not in stop and h > 0:
        q = min(max(cw/ucb, 50.0), 300.0)
    if q > 0:
        p = model(q, 3000.0)
        twh = p['wellhead_c']; cb = q*ucb
        tx = min(twh-5, TS)
        cw1 = min(cw, cb)
        qhx = cw1*(tx-TR)
        tb = twh - qhx/cb
        rem = h - qhx
        ch4 = q*0.8*0.8*35.8/3600
        free_gas = min(ch4*0.95, 30.0, rem)
        left = rem - free_gas
        floor = twh - 40
        # HP: solve source outlet by bisection
        want = min(left, 0.5)
        # max heat at floor
        cf = cop_hp(floor); mx = cb*(tb-floor)*cf/(cf-1) if tb > floor else 0
        want = min(want, mx)
        if want > 0:
            lo, hi = floor, tb
            for _ in range(60):
                m = 0.5*(lo+hi)
                if cb*(tb-m) > want*(1-1/cop_hp(m)): lo = m
                else: hi = m
            tout = 0.5*(lo+hi); hpel = want/cop_hp(tout)
        else:
            tout = tb; hpel = 0
        boiler = min(rem - want, 30.0)
        res['maxcool'] = max(res['maxcool'], twh - tout)
        pumps = p['esp_mw'] + p['injector_pump_mw']
    else:
        qhx = 0; want = 0; hpel = 0; boiler = min(h, 30.0); ch4 = 0; pumps = 0
    fuel = boiler/0.95; used = min(fuel, ch4)
    res['geo'] += qhx; res['hp'] += want; res['hp_el'] += hpel; res['boiler'] += boiler
    res['short'] += h - qhx - want - boiler
    res['fuel'] += fuel; res['used'] += used; res['flared'] += ch4 - used; res['ch4'] += ch4
    res['pumps'] += pumps; res['brine'] += q
    c = C[d]
    share = np.clip((25 - (wb[d]+6))/5, 0, 1)
    fc = min(share*c, 15*(1+1/cop_ch)); ch = c - fc; chel = ch/cop_ch
    res['free'] += fc; res['chill'] += ch; res['chill_el'] += chel; res['tower'] += 0.0125*(ch+chel+fc)
out = {k: (v*24/1000 if k not in ('maxcool','brine') else v) for k, v in res.items()}
out['brine_m3'] = res['brine']*24
out['purchased'] = out['fuel'] - out['used']
el = out['hp_el'] + out['chill_el'] + out['pumps'] + out['tower']
out['elec'] = el
out['co2_gas'] = out['purchased']*1000*0.202
out['co2_prod'] = res['brine']*24*0.8*44.01/22.414/1000
out['co2_el'] = el*1000*0.2
out['co2_tot'] = out['co2_gas'] + out['co2_prod'] + out['co2_el']
for k, v in out.items(): print(f'{k:10s} {v:12.3f}')
print('chiller COP', cop_ch)
