from dioscuri_plant.explore import Point, front_of
def P(lcoe, co2): return Point(1, 2500, 300, 0,0,0,0,0,'buy', lcoe, lcoe, co2, 0.5, 10.0, '')
pts = [P(50.0, 100.0), P(50.0, 90.0), P(60.0, 80.0)]
print('front', front_of(pts), '(point 0 is dominated by point 1: same cost, more CO2)')
# refine selection with 8 front points whose cheapest has the largest index
front = [7, 0, 1, 2, 3, 4, 5, 6]  # lcoe order; cheapest is point 7
L=len(front); refine_top=6
pick = sorted(set(front[:: max(1, L // max(1, refine_top - 1))] + front[-1:]))
print('refined', pick[:refine_top], 'cheapest kept?', 7 in pick[:refine_top], 'lowest-CO2 kept?', 6 in pick[:refine_top])
