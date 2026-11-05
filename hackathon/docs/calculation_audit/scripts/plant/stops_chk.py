import sys, datetime
import numpy as np
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent import stops
from dioscuri_plant.year import dispatch, _day
bad = [i for i in range(365) if stops.day_name(i) != f"{(datetime.date(2027,1,1)+datetime.timedelta(i)).day} {(datetime.date(2027,1,1)+datetime.timedelta(i)).strftime('%b')}"]
bad2 = [i for i in range(365) if _day(i) != stops.day_name(i)]
print('day_name mismatches', bad[:5], 'year._day mismatches', bad2[:5])
print(stops.check([[[0, 20], [100, 113]]], 330), '|', stops.check([[[0, 20], [20, 40]]], 330), '|', stops.check([[[0, 33]]], 330), '|', stops.check([[[300, 365]]], 330))
print(stops.parse('[[[1,35]],[],[[200,234]]]'), stops.parse('[[[1,35]],[]]'))
# dispatch ordering with a halved day-cap
q = dispatch(np.array([400.0]), np.ones((2,1), bool), np.array([[150.0],[250.0]]), [0,1], 50.0, 'equal')
print('equal, caps day [150,250], want 400 ->', q.ravel(), 'sum', q.sum())
caps = np.array([[300.0]*1, [250.0]]).reshape(2,1)
# day cap of doublet 0 halved to 150 but its max cap is 300: build per-day caps with 2 days
caps2 = np.array([[300.0, 150.0], [250.0, 250.0]])
q2 = dispatch(np.array([400.0, 400.0]), np.ones((2,2), bool), caps2, [0,1], 50.0, 'equal')
print('equal, caps per day d0=[300,150] d1=[250,250], want 400 ->', q2, 'sums', q2.sum(axis=0))
