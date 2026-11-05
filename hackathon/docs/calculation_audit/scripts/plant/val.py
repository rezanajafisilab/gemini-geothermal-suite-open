import sys, json
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import validation as v
# Sharqawy check values: seawater S=35 g/kg, 25 C: cp ~ 3.99 kJ/kgK (table: 3993); density ~1023.3
print('cp(35,25)', v.brine_cp(35, 25), 'rho(35,25)', v.brine_density(35, 25))
print('cp(0,25)', v.brine_cp(0, 25), 'rho(0,25)', v.brine_density(0, 25))
print('cp(41,73)', v.brine_cp(41, 73), 'rho(41,73)', v.brine_density(41, 73))
for r in v.all_projects():
    print(r['key'], r['inputs'])
    for row in r['rows']: print('   ', row)
