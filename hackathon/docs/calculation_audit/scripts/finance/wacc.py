from common import *
from dataclasses import replace
L = pickle.load(open(HERE+'/lead.pkl','rb'))
D, E, Rd, Re, t, i = 0.7, 0.3, 0.0575, 0.145, 0.258, 0.02
after_nom = D*Rd*(1-t)+E*Re; pre_nom = D*Rd+E*Re/(1-t)
print('after-tax nominal', after_nom, 'real', (1+after_nom)/(1+i)-1, '| pre-tax nominal', pre_nom, 'real', (1+pre_nom)/(1+i)-1)
for r in (0.052, (1+pre_nom)/(1+i)-1):
    e = dp.economics(L['plant'], L['year'], replace(L['prices'], discount_rate=r), rules=L['rules'])
    re_ = dp.economics(L['rplant'], L['ryear'], replace(L['prices'], discount_rate=r), rules=L['rules'])
    print(f'r={r:.4f} LCOE {e.lcoe_eur_per_mwh} LCOH {e.lcoh_eur_per_mwh} | ref LCOH {re_.lcoh_eur_per_mwh}')
