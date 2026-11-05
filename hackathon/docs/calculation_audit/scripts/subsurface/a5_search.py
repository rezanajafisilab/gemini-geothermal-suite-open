"""The default search: the chosen design's GEMINI check rows and its subsurface summary."""
import json
import time

from gemini_agent import engine
from gemini_agent.contract import DesignBrief

t = time.time()
out = engine.search(DesignBrief())
print("search s", round(time.time() - t, 1))
c = out.chosen
print("chosen", c.alternative.code if hasattr(c.alternative, "code") else c.alternative)
y = c.year
print("heat split", y.heat_split_gwh, "pumps", y.electricity_gwh["pumps"], "co2", y.co2_t)
print("lcoe", c.economics.lcoe_eur_per_mwh)
print("year fields", list(type(y).model_fields)[:80])
print("doublets", c.alternative.doublets)
g = engine.gemini_check(c)
for r in g["rows"]:
    print(r)
print("agree", g["agree"], "/", g["total"])
# picks and their injectors
for name, code in out.picks.items():
    e = next((x for x in out.candidates if getattr(x.alternative, "code", None) == code), None)
    if e is None:
        continue
    inj = [d.get("injectors", 1) for d in (e.alternative.doublets or [])]
    print("pick", name, code, "injectors", inj, "depths", [d.get("depth_m") for d in (e.alternative.doublets or [])])
two = [x for x in out.candidates if any(int(d.get("injectors") or 1) == 2 for d in (x.alternative.doublets or []))]
print("candidates with two injectors:", len(two), "of", len(out.candidates))
if two:
    e = two[0]
    g2 = engine.gemini_check(e)
    print("two-injector candidate", e.alternative.code)
    for r in g2["rows"]:
        if "njection" in r["quantity"]:
            print("  ", r)
