from common import *
d, s = lead_session()
r=0.052; AF=(1-(1+r)**-30)/r
for uid in ('A1','A33','A163','A47'):
    e = next(x for x in s.candidates if x.alternative.uid==uid)
    ref = engine.reference(e.brief, None); prices = engine.prices_for(None, e.brief)
    v = engine.versus_reference(e, ref, prices)
    def annual(en):
        return sum(float(x[2]) for x in en.economics.lines_heat)+sum(float(x[2]) for x in en.economics.lines_cold)
    consistent = AF*(annual(ref)-annual(e))
    print(uid, e.alternative.code, 'versus NPV', v['npv_meur'], 'annuity-consistent NPV', round(consistent,2), 'diff %', round((v['npv_meur']-consistent)/abs(consistent)*100,1), 'items', sorted({(it['item'], it['life_years']) for it in e.economics.capex_items if it['life_years']<30}))
