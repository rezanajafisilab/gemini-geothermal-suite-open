from common import *
from dioscuri_plant.investor import capital_flows
d, s = lead_session()
r=0.052; N=30
e = next(x for x in s.candidates if x.alternative.uid=='A33')
ref = engine.reference(e.brief, None)
def pvcap(en):
    spend, left, buys = capital_flows(en.economics.capex_items, N, r)
    return sum(x/(1+r)**t for t,x in enumerate(spend)) - left/(1+r)**N, buys
pd, bd = pvcap(e); pr, br = pvcap(ref)
sav = (ref.economics.opex_meur_per_year - e.economics.opex_meur_per_year)
npv = sum(sav/(1+r)**t for t in range(1,N+1)) - pd + pr
print('explicit DCF NPV with replacements and residual', round(npv,2), '| design re-buys', [(k,round(c,2)) for k,c in bd if k>0])
