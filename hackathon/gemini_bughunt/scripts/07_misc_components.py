"""Boiler / CHP / injector pump / compressor / mixer / two-phase well checks.

  PYTHONPATH=<tree>/src python 07_misc_components.py
"""

import math
import warnings

import numpy as np

from gemini_model.boiler.boiler import Boiler
from gemini_model.chp.chp import CHP
from gemini_model.compressor.compressor import Compressor
from gemini_model.fluid.pvt_water_stp import PVTConstantSTP
from gemini_model.injector_pump.injector_pump import InjectorPump
from gemini_model.mixer.mixer import Mixer
from gemini_model.well.pressure_drop import DPDT

warnings.filterwarnings("ignore")

print("=== Boiler: 1 kg/s gas (caloric 50 MJ/kg), eta 0.9, water 100 m3/h @ 60 C")
b = Boiler()
b.update_parameters({"caloric_value": 50e6, "efficiency_factor": 0.9, "gas_emission_factor": 56.6})
b.calculate_output({"temperature_in": 60.0, "water_flow_rate": 100 / 3600, "gas_flow_rate": 1.0})
y = b.get_output()
q_water = 100 / 3600 * 1050 * 4200 * (y["temperature_out"] - 60)
print(f"  power_th={y['power_th']/1e6:.3f} MW (expect 45.000), water-side heat={q_water/1e6:.3f} MW,"
      f" T_out={y['temperature_out']:.2f} C, CO2={y['emission']*3600:.1f} kg/h (expect 56.6 kg/GJ*180 GJ/h=10188)")
b.calculate_output({"temperature_in": 60.0, "water_flow_rate": 10 / 3600, "gas_flow_rate": 1.0})
print(f"  same gas, only 10 m3/h water: T_out={b.get_output()['temperature_out']:.1f} C (no boiling/limit check)")

print()
print("=== CHP: 1 kg/s gas, eta 0.8 (fixed el. fraction 1/3 of eta*fuel)")
c = CHP()
c.update_parameters({"caloric_value": 50e6, "efficiency_factor": 0.8, "gas_emission_factor": 56.6})
c.calculate_output({"temperature_in": 60.0, "water_flow_rate": 100 / 3600, "gas_flow_rate": 1.0})
y = c.get_output()
print(f"  fuel=50 MW -> power_el={y['power_el']/1e6:.2f} MW (el. eff {y['power_el']/50e6:.1%}),"
      f" power_th={y['power_th']/1e6:.2f} MW (th. eff {y['power_th']/50e6:.1%}), total {(y['power_el']+y['power_th'])/50e6:.0%}")

print()
print("=== InjectorPump: 150 m3/h, 2 -> 52 bar, eta 0.8")
ip = InjectorPump()
ip.update_parameters({"efficiency_factor": 0.8, "electricity_emission_factor": 0.3})
ip.calculate_output({"pressure_in": 2e5, "pressure_out": 52e5, "flow_rate": 150 / 3600})
print(f"  power_el={ip.get_output()['power_el']/1e3:.1f} kW (hand: 150/3600*50e5/0.8 = {150/3600*50e5/0.8/1e3:.1f} kW)")
ip.calculate_output({"pressure_in": 2, "pressure_out": 52, "flow_rate": 150 / 3600})
print(f"  same in bar (as the surface chain uses bar!): power_el={ip.get_output()['power_el']:.2f} W  <- unit trap;"
      " InjectorPump expects Pa, Separator/Filter/BoosterPump emit bar")

print()
print("=== Compressor: 1 kg/s natural gas-ish (R=518 J/kgK, k=1.3), 1 -> 10 bar, 1 stage, 20 C, eff 1")
cmp_ = Compressor()
cmp_.update_parameters({"mechanical_efficiency": 1.0, "compressor_efficiency": 1.0, "specific_heat_ratio": 1.3,
                        "gas_constant": 518.0, "number_of_stages": 1})
cmp_.calculate_output({"mass_flow": 1.0, "pressure_in": 1.0, "pressure_out": 10.0, "temperature_in": 20.0})
w_model = cmp_.get_output()["compressor_power"]
k, R, T1 = 1.3, 518.0, 293.15
w_isen = k / (k - 1) * R * T1 * (10 ** ((k - 1) / k) - 1)
print(f"  model={w_model/1e3:.1f} kW, isentropic hand calc k/(k-1)*R*T1*(r^((k-1)/k)-1) = {w_isen/1e3:.1f} kW,"
      f" ratio model/hand = {w_model/w_isen:.3f} (= 1/k = {1/k:.3f})")
for n in (2, 3):
    cmp_.update_parameters({"number_of_stages": n})
    cmp_.calculate_output({"mass_flow": 1.0, "pressure_in": 1.0, "pressure_out": 10.0, "temperature_in": 20.0})
    w_hand = n * k / (k - 1) * R * T1 * (10 ** ((k - 1) / (k * n)) - 1)
    print(f"  {n} stages: model={cmp_.get_output()['compressor_power']/1e3:.1f} kW, hand={w_hand/1e3:.1f} kW")

print()
print("=== Mixer energy balance (3 streams)")
m = Mixer()
m.update_parameters({"num_inputs": 3})
m.calculate_output({"input_0_flow": 0.01, "input_0_temperature": 80, "input_1_flow": 0.02,
                    "input_1_temperature": 40, "input_2_flow": 0.0, "input_2_temperature": 1000})
print(f"  flow={m.get_output()['flow']}, T={m.get_output()['temperature']:.3f} (expect 53.333)")

print()
print("=== Two-phase path in DPDT (PVT GMF>0): us_g uses gmf instead of mg (pressure_drop.py:105)")


def well(gmf, q_m3h, direction="up", p0=250e5):
    w = DPDT()
    w.update_parameters({"diameter": np.array([0.2]), "length": np.array([2500.0]),
                         "angle": np.array([np.pi / 2]), "roughness": np.array([4.5e-5]),
                         "friction_correlation": "darcy_weisbach", "friction_correlation_2p": "BeggsBrill",
                         "correction_factors": [1, 0]})
    w.PVT = PVTConstantSTP()
    w.PVT.update_parameters({"GMF": gmf})
    w.calculate_output({"pressure": p0, "temperature": 353.15, "temperature_ambient": 293.15,
                        "flowrate": q_m3h / 3600, "direction": direction}, None)
    return w.get_output()


for gmf in (0.0, 1e-4, 1e-3):
    for q in (50, 150, 300):
        try:
            y = well(gmf, q)
            rho_mix = 1 / (gmf / 1.976 + (1 - gmf) / 1000)
            mg = gmf * q / 3600 * rho_mix
            usg_correct = mg / 1.976 / (math.pi / 4 * 0.2 ** 2)
            usg_code = gmf / 1.976 / (math.pi / 4 * 0.2 ** 2)
            print(f"  GMF={gmf:g} Q={q:3d} m3/h: p_wh={y['pressure_output']/1e5:7.2f} bar fric={y['pressuredrop_fric_output']/1e5:6.2f}"
                  f" grav={y['pressuredrop_grav_output']/1e5:7.2f}; us_g code={usg_code:.4f} m/s vs mg-based={usg_correct:.4f} m/s")
        except Exception as e:  # noqa
            print(f"  GMF={gmf:g} Q={q:3d} m3/h: EXCEPTION {type(e).__name__}: {e}")
