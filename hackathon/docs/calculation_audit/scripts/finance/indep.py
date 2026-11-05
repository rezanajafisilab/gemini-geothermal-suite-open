import pickle, math
from common import *
L = pickle.load(open(HERE+'/lead.pkl','rb'))
I = pickle.load(open(HERE+'/inv.pkl','rb'))
econ, year = L['econ'], L['year']
r = 0.052
def crf(r,n): return r/(1-(1+r)**-n)
def AF(r,n): return (1-(1+r)**-n)/r
# --- 1. independent capex
L_ah = 1.1*math.hypot(3000, 750)
well = 1.96*(790000+555*L_ah+0.05*L_ah**2)/1e6
print('along hole', L_ah, 'well M€', well)
items = [('wells',2*well,30),('surface',3.5+0.882*year.peak_brine_heat_mw,30),('hp',0.5*1.2,25),('boiler',30*0.075,25),('chill',15*0.245,25),('fc',year.free_cooling_mw*0.03,25)]
capex = sum(c for _,c,_ in items); print('capex', capex, 'code', econ.capex_meur)
ann = sum(c*crf(r,n) for _,c,n in items)
# --- opex independent
y = year
el = sum(v for k,v in y.electricity_gwh.items())*185.7/1e3
gas = y.purchased_gas_gwh*69.4/1e3
co2 = (y.co2_t['purchased_gas']+y.co2_t['produced_gas'])*73.9/1e6
brine = y.heat_split_gwh['geo'] + y.heat_split_gwh['hp']-y.electricity_gwh['hp']
om = 121*y.peak_brine_heat_mw/1e3 + 0.62*brine/1e3 + 3200*0.5/1e6 + 2.5*y.heat_split_gwh['hp']/1e3 + 2420*30/1e6 + 1.37*y.heat_split_gwh['boiler']/1e3 + 10500*15/1e6
opex = el+gas+co2+om
mwh = (y.heat_delivered_gwh+y.cool_delivered_gwh)*1e3
print('annuity', ann, 'opex', opex, 'code opex', econ.opex_meur_per_year, 'LCOE', (ann+opex)*1e6/mwh, 'code', econ.lcoe_eur_per_mwh)
# --- 2. discounted-cash-flow LCOE over 30 years with replacements and residual value (straight-line on remaining life)
N=30
pv_cost = sum(opex/(1+r)**t for t in range(1,N+1))
pv_cap = 0
pv_cap_sl = 0
for _,c,n in items:
    k=0
    while k < N:
        pv_cap += c/(1+r)**k; pv_cap_sl += c/(1+r)**k
        last=k; k+=n
    rest = last+n-N
    pv_cap -= c*crf(r,n)*AF(r,rest)/(1+r)**N
    pv_cap_sl -= c*rest/n/(1+r)**N   # straight-line residual
pv_e = sum(mwh/(1+r)**t for t in range(1,N+1))
print('DCF LCOE (annuity residual)', (pv_cap+pv_cost)*1e6/pv_e, ' DCF LCOE (straight-line residual)', (pv_cap_sl+pv_cost)*1e6/pv_e)
# no residual and no replacement (simplest 30-year DCF: capex at t=0 only, 25-yr items treated as lasting 30)
pv_simple = capex + pv_cost
print('DCF LCOE, capex once, no replacement', pv_simple*1e6/pv_e)
# --- 3. independent investor model
case, ref = I['case'], I['ref']
i = 0.02
heat_gwh = y.heat_delivered_gwh; cold_gwh = y.cool_delivered_gwh
rev = heat_gwh*ref.economics.lcoh_eur_per_mwh/1e3 + cold_gwh*ref.economics.lcoc_eur_per_mwh/1e3
cap_mw = 300*1030*3.99e3/3600*36.89/1e6  # approx brine MW at cap (check below)
print('approx capacity MW', cap_mw, 'code', case.sde['capacity_mw'])
elig = brine
sub = min(elig, case.sde['installation_mw']*6000/1e3)
def sde_kwh(t):
    corr = max(0.7*0.028, 0.0131) + (0.0114 if 2027+t-1 >= 2028 else 0)
    return max(0.0696-corr,0)
buys=[]
for _,c,n in items:
    k=0
    while k<N: buys.append((k,c)); k+=n
wo=[0.0]*(N+1)
for k,c in buys:
    for t in range(k+1, min(k+15,N)+1): wo[t]+= c*(1+i)**k/15
def tax(p):
    if p<=0: return 0
    lo=min(p,0.2); return lo*0.19+(p-lo)*0.258
net=[]; losses=0
left = sum(c*crf(r,n)*AF(r, (max(k for k,cc in buys if cc==c)+n-N)) for _,c,n in items)
for t in range(N+1):
    if t==0:
        net.append(-sum(c for k,c in buys if k==0)); continue
    sde = sub*sde_kwh(t) if t<=15 else 0
    prof = (rev-opex)*(1+i)**t + sde - wo[t]
    if prof<0: losses-=prof; tx=0
    else:
        u=min(losses,prof); losses-=u; tx=tax(prof-u)
    f = rev-opex + sde/(1+i)**t - tx/(1+i)**t - sum(c for k,c in buys if k==t) + (left if t==N else 0)
    net.append(f)
npv = sum(f/(1+r)**t for t,f in enumerate(net))
def npvr(rate): return sum(f/(1+rate)**t for t,f in enumerate(net))
lo,hi=0.0,1.0
for _ in range(100):
    m=(lo+hi)/2
    if npvr(m)>0: lo=m
    else: hi=m
cum=0; pb=None
for t,f in enumerate(net):
    d=f/(1+r)**t
    if cum<0 and cum+d>=0 and pb is None: pb=t-1+(-cum)/d
    cum+=d
print('indep NPV', npv, 'code', case.npv_meur, '| IRR', lo, 'code', case.irr, '| payback', pb, 'code', case.payback_years)
print('first-year SDE today', sub*sde_kwh(1)/(1+i), 'code', case.sde['meur_first_year'])
