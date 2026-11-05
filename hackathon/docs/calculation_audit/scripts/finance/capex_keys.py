from common import *
from gemini_agent import workbench
d, s = lead_session()
for uid in ('A33','A39','A1'):
    e = next(x for x in s.candidates if x.alternative.uid==uid)
    base = workbench._evaluate(e, {}, {}, ['lcoe','capex_meur'])
    for x in (0.8, 1.3):
        sens = workbench._evaluate(e, {}, {'capex': x}, ['lcoe','capex_meur'])
        ok = engine.reprice(e, {'capex_scale': x}).economics
        print(uid, e.alternative.code, 'x', x, '| sensitivity tab: capex', sens['capex_meur'], 'LCOE', sens['lcoe'], '| all capital scaled (engine.CAPEX_KEYS): capex', ok.capex_meur, 'LCOE', ok.lcoe_eur_per_mwh, '| base', base)
