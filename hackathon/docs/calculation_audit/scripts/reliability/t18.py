from common import *
from collections import Counter
sw = S['searches'][-1]['sweep']; cols=sw['columns']; rows=sw['rows']
d = Counter(r[cols.index('depth_m')] for r in rows); f = Counter(r[cols.index('flow_cap_m3h')] for r in rows)
print('depth counts', sorted(d.items()))
print('flow counts (ends and two interior)', f[100.0], f[110.0], f[200.0], f[290.0], f[300.0])
print('ranges', sw['ranges'])
