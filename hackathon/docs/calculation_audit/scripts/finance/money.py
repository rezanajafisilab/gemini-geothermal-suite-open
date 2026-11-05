from common import *
from gemini_agent import answer, workbench
d, s = lead_session()
for l in answer.money_lines(s.chosen, None): print('-', l)
v = workbench.economics_view(s.chosen, {})
print({k: v[k] for k in ('co2_t_per_year','reference_co2_t_per_year','co2_saving_pct','vs_gas_pct','lcoe')})
