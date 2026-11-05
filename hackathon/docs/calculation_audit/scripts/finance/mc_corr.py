from common import *
import random, time, statistics, math
import numpy as np
from gemini_agent import workbench
d, s = lead_session()
c = s.chosen
known = {p["key"]: dict(p) for p in workbench.sensitivity_parameters()["parameters"]}
keys = ["gas_price","electricity_price","carbon_price","capex","discount_rate","reservoir_temp","heat_return","permeability"]
modes = {k: workbench.base_value(c, {}, k) for k in keys}
print({k:(known[k]['low'], modes[k], known[k]['high']) for k in keys})
t=time.time(); base = workbench._evaluate(c, {}, {}, ['lcoe','npv_meur']); print('base', base, time.time()-t)
def tri_inv(u, lo, hi, m):
    fc = (m-lo)/(hi-lo)
    return lo+math.sqrt(u*(hi-lo)*(m-lo)) if u<fc else hi-math.sqrt((1-u)*(hi-lo)*(hi-m))
N=800
rng = np.random.default_rng(3)
from statistics import NormalDist
nd = NormalDist()
res = {'indep':{'lcoe':[], 'npv_meur':[]}, 'corr':{'lcoe':[], 'npv_meur':[]}}
# gaussian copula: gas, electricity, carbon correlated 0.7
R = np.eye(3); R[0,1]=R[1,0]=0.7; R[0,2]=R[2,0]=0.5; R[1,2]=R[2,1]=0.5
Lc = np.linalg.cholesky(R)
t=time.time()
for mode in ('indep','corr'):
    for i in range(N):
        u = rng.random(len(keys))
        if mode=='corr':
            z = Lc @ np.array([nd.inv_cdf(x) for x in u[:3]])
            u[:3] = [nd.cdf(x) for x in z]
        vals = {k: tri_inv(u[j], known[k]['low'], known[k]['high'], modes[k]) for j,k in enumerate(keys)}
        r = workbench._evaluate(c, {}, vals, ['lcoe','npv_meur'])
        for o in r: res[mode][o].append(r[o])
print('secs', time.time()-t)
for mode in res:
    for o,v in res[mode].items():
        v=np.array(v); print(mode, o, 'p10', round(np.percentile(v,10),2), 'p50', round(np.percentile(v,50),2), 'p90', round(np.percentile(v,90),2), 'base pct', round(np.mean(v<base[o]),2))
