from common import *
srch = S['searches'][-1]
print(srch.keys())
sw = srch.get('sweep') or (srch.get('card') or {}).get('sweep')
if sw is None:
    for k,v in srch.items():
        if isinstance(v, dict) and 'front' in v: sw=v; print('found in', k)
print(type(sw))
if sw:
    cols = sw['columns']; rows = sw['rows']; front = sw['front']
    print('n', len(rows), 'feasible', sw['feasible'], 'front len', len(front), 'failures', sw['failures'])
    L=len(front); refine_top=6
    pick = sorted(set(front[:: max(1, L // max(1, refine_top - 1))] + front[-1:]))
    print('front (lcoe order):', front)
    print('pick (by index):', pick, '-> refined:', pick[:refine_top])
    print('cheapest front point', front[0], 'kept?', front[0] in pick[:refine_top], 'lowest-CO2', front[-1], 'kept?', front[-1] in pick[:refine_top])
    li = cols.index('lcoe'); ci = cols.index('co2_t')
    for i in front: print(i, rows[i])
