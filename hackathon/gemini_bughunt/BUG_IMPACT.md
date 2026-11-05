# What GEMINI as released would have given for our designs

GEMINI 1.0.3 (`development`, released 29 Oct 2026), as released and with our 11 patches in `patches/`. The challenge's reservoir and brine (87 °C at 2,500 m, 1,030 kg/m³, 0.40 mPa·s), doublets at 300 m³/h, network 100/60 °C. Written by `scripts/14_bug_impact_on_designs.py`.

## 2D-BO-EC@3000: 2 doublets at 3,000 m, gas boiler top-up, electric chillers

| Quantity | Released | Fixed | Released is off by | Cause |
|---|---|---|---|---|
| ESP head at 300 m3/h (bar) | 41.7 | 31.1 | +34% | water instead of brine (11), 10 mm roughness (F10) |
| ESP electricity (MW) | 0.497 | 0.37 | +34% | the same |
| Injection pressure (bar) | 4.59 | 26.1 | -82% | friction sign (F3), roughness (F10) |
| Injection pump electricity (MW) | 0.007 | 0.263 | -97% | the same |

## 1D-HP-EC@3000: 1 doublet at 3,000 m, heat pump top-up with a backup boiler, electric chillers

| Quantity | Released | Fixed | Released is off by | Cause |
|---|---|---|---|---|
| ESP head at 300 m3/h (bar) | 41.7 | 31.1 | +34% | water instead of brine (11), 10 mm roughness (F10) |
| ESP electricity (MW) | 0.497 | 0.37 | +34% | the same |
| Injection pressure (bar) | 4.59 | 26.1 | -82% | friction sign (F3), roughness (F10) |
| Injection pump electricity (MW) | 0.007 | 0.263 | -97% | the same |
| Heat pump COP | 5.33 | 4.88 | +9% | spurious root (F2); Carnot at the source outlet (10) |
| Brine after the heat pump (°C) | 61.7 | 61.8 | -0% | spurious root (F2) |
| Heat pump CO₂ (kg/h) | 0 | 86 | -100% | electricity not counted (08) |
