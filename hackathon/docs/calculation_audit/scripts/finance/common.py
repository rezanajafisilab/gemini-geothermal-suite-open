import json, sys, pickle, os
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/src')
from gemini_agent.agent import Session
from gemini_agent import engine
import dioscuri_plant as dp
HERE = os.path.dirname(os.path.abspath(__file__))

def lead_session():
    d = json.load(open(str(__import__('pathlib').Path(__file__).resolve().parents[5]) + '/hackathon/evals/runs/lead/challenge.json'))
    return d, Session.from_dict(d['session'])

def rebuild(entry, prices=None):
    brief = entry.brief
    rules = engine.rules_for(brief)
    prices = prices or engine.prices_for(None, brief)
    plant = engine.plant_of(entry.alternative)
    demand = engine.demand_of(brief)
    model = engine.doublet_model(rules)
    year = dp.simulate_year(plant, demand, model, rules)
    return plant, year, rules, prices, demand, model
