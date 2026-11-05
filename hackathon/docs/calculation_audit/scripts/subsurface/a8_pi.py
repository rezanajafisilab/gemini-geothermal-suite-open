import math
import numpy as np
import dioscuri_plant as dp
from gemini_agent import engine
from gemini_agent.contract import DesignBrief
R = engine.rules_for(DesignBrief()); demand = engine.demand_of(DesignBrief()); model = engine.doublet_model(R)
y = dp.simulate_year(dp.Plant(1, depth_m=3000.0, heat_pump_mw=2.0, boiler_mw=30.0, chiller_mw=12.0), demand, model, R)
q = np.array(y.doublets[0]["flow_m3h"])
kh = 200 * 9.869233e-16 * 100; mu = 0.4e-3
pi_code = 2*math.pi*kh/(mu*(math.log(500/0.10795)-0.75))*3.6e8
pi_dip = 2*math.pi*kh/(mu*math.log(1500/0.10795))*3.6e8
dd = (1/pi_dip - 1/pi_code)
extra = np.sum(2 * q * (q * dd) * 1e5 / 3600 / 0.7 / 1e6) * 24 / 1000
print("PI code", pi_code, "dipole", pi_dip, "extra drawdown at 300", 300*dd, "bar; pumps", y.electricity_gwh["pumps"], "extra GWh", round(extra, 3),
      "total el", round(sum(y.electricity_gwh.values()), 3), "heat+cold GWh", y.heat_demand_gwh + y.cool_demand_gwh)
