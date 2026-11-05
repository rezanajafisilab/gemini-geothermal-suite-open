import json, time, sys
sys.path.insert(0, 'src')
from gemini_agent import engine, lead
from gemini_agent.contract import Alternative, DesignBrief
import dioscuri_plant as dp

D = json.load(open('hackathon/evals/runs/lead/challenge.json'))
S = D['session']
CANDS = S['candidates']

def alt(uid):
    for e in CANDS:
        if e['alternative']['uid'] == uid:
            return Alternative(**e['alternative']), e
    raise KeyError(uid)

BRIEF = DesignBrief(**S['brief']) if S.get('brief') else DesignBrief()
RULES = engine.rules_for(BRIEF)
DEMAND = engine.demand_of(BRIEF)
MODEL = engine.doublet_model(RULES)
PRICES = engine.prices_for(None, BRIEF)

def plant(uid):
    a, e = alt(uid)
    return engine.plant_of(a)
