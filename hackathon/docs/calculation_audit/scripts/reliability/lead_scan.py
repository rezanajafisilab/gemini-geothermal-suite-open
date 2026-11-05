import json
d=json.load(open('hackathon/evals/runs/lead/challenge.json'))
s=d['session']
c=s['candidates']
rel=[e for e in c if e['alternative']['reliable'] and e['alternative']['role'] in ('chosen','candidate')]
print('reliable valid entries', len(rel))
bad=0
for e in rel:
    f=e.get('firm') or {}
    outs=f.get('outages') or []
    short=[o['unit'] for o in outs if o['heat']['days_short'] or o['cool']['days_short']]
    a=e['alternative']
    tag = ','.join(a['picks'])
    if short or tag:
        print(a['uid'], a['code'], a['economics'] if 'economics' in a else '', round(e['economics']['lcoe_eur_per_mwh'],2), 'short:', short, 'picks:', tag, 'n_out', len(outs))
    if short: bad+=1
print('reliable plans with N-1 cases short:', bad)
# all picks
for e in c:
    a=e['alternative']
    if a['picks']:
        print(a['uid'], a['code'], a['picks'], a['role'], a['reliable'], round(e['economics']['lcoe_eur_per_mwh'],2), e['economics']['co2_t_per_year'], a['sizes_mw'], a['boiler_units'], a['chiller_units'], a['electric_boiler_units'])
