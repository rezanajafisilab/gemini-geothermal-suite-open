"""The amounts a message gives: number formats and units read by code, never which key."""

import unittest

from gemini_agent import parameters
from gemini_agent import quantities as Q


def one(message, dimension=None):
    """Return the message's only clear amount (of a dimension, when given)."""
    found = [q for q in Q.extract(message) if q.clear and dimension in (None, q.dimension)]
    assert len(found) == 1, (message, found)
    return found[0]


def means(message, key, now=None):
    """Return the values a message supports for a key, rounded."""
    return [round(v, 4) for v in Q.supported(message, key, now)]


class TestNumbers(unittest.TestCase):
    """Decimal commas, thousands separators and numbers in words."""

    def test_decimal_commas(self):
        """4,5 is 4.5; 0,05 is 0.05; a decimal point reads as written."""
        self.assertEqual(Q.read_number("4,5"), (4.5, None))
        self.assertEqual(Q.read_number("0,05"), (0.05, None))
        self.assertEqual(Q.read_number("12.25"), (12.25, None))
        self.assertEqual(one("En met gas op 4,5 ct/kWh?").value, 4.5)

    def test_thousands_separators_by_context(self):
        """1,500 in English and 1.500 in Dutch are 1500; the other reading is kept beside."""
        self.assertEqual(Q.read_number("1,500"), (1500.0, 1.5))
        self.assertEqual(Q.read_number("1.500", decimal_comma=True), (1500.0, 1.5))
        self.assertEqual(Q.read_number("1,500", decimal_comma=True), (1.5, 1500.0))
        self.assertEqual(Q.read_number("2.500.000"), (2500000.0, None))
        self.assertEqual(Q.read_number("1.500,5"), (1500.5, None))
        self.assertEqual(Q.read_number("1,500.5"), (1500.5, None))
        self.assertEqual(Q.read_number("1.2.3"), (None, None))  # not a number
        q = one("Boor de putten tot 1.500 m diep, met een tweede aquifer", "length")
        self.assertEqual((q.value, q.alt), (1500.0, 1.5))
        self.assertIn(
            1500.0, means("wells at 1,500 m for the second aquifer", "second_aquifer_depth_m")
        )
        # A Dutch message: the comma is a decimal ("2,5 km"), and the dot a thousands separator.
        self.assertEqual(means("tweede aquifer op 2,5 km", "second_aquifer_depth_m"), [2500.0])

    def test_numbers_in_words(self):
        """English and Dutch small numbers, also compounds."""
        self.assertEqual(one("five degrees colder").value, 5)
        self.assertEqual(one("twenty-five percent more").value, 25)
        self.assertEqual(one("vijf graden warmer").value, 5)
        self.assertEqual(one("vijfentwintig procent duurder").value, 25)
        self.assertEqual(one("twintig procent minder").change, "-")
        self.assertEqual(means("a reservoir five degrees colder", "reservoir_change_k"), [-5.0])
        self.assertEqual(means("drie graden warmer reservoir", "reservoir_change_k"), [3.0])


class TestShares(unittest.TestCase):
    """Fractions and multipliers become a multiplier; percentages a fraction or a change."""

    def test_fractions_more_and_less(self):
        """A fifth more is x1.2, a quarter less x0.75, een vijfde meer x1.2."""
        self.assertEqual(means("And with a fifth more heat demand?", "heat_demand_scale"), [1.2])
        self.assertEqual(means("a quarter less cooling", "cool_demand_scale"), [0.75])
        self.assertEqual(means("een vijfde meer warmtevraag", "heat_demand_scale"), [1.2])
        self.assertEqual(means("een kwart minder koudevraag", "cool_demand_scale"), [0.75])
        # From the value now, for a key that is not a multiplier.
        self.assertEqual(means("a fifth more on gas", "gas_eur_per_mwh", 50.0), [60.0])
        # "The third doublet" is an ordinal, not an amount.
        self.assertEqual([q for q in Q.extract("fail the third doublet") if q.clear], [])

    def test_percentages(self):
        """20 percent more is x1.2; 20 procent is 0.2 as a fraction; by 20 % from a verb."""
        self.assertEqual(means("20 percent more heat demand", "heat_demand_scale"), [1.2])
        self.assertEqual(means("20 % less cooling", "cool_demand_scale"), [0.8])
        self.assertEqual(means("een discontovoet van 4 procent", "discount_rate"), [0.04])
        self.assertEqual(means("20 procent meer warmte", "heat_demand_scale"), [1.2])
        self.assertEqual(means("increase the gas price by 20 %", "gas_eur_per_mwh", 50.0), [60.0])
        self.assertEqual(one("cut the electricity price by 10 %").change, "-")

    def test_multipliers(self):
        """Twice, double, half, halve, verdubbelen, 1,5 keer, x1.2."""
        self.assertEqual(means("twice the heat demand", "heat_demand_scale"), [2.0])
        self.assertEqual(means("double the gas price", "gas_eur_per_mwh", 69.4), [138.8])
        self.assertEqual(means("half the cooling demand", "cool_demand_scale"), [0.5])
        self.assertEqual(means("halve the capital costs", "capex_scale"), [0.5])
        self.assertEqual(means("de gasprijs verdubbelen", "gas_eur_per_mwh", 50.0), [100.0])
        self.assertEqual(means("1,5 keer de warmtevraag", "heat_demand_scale"), [1.5])
        self.assertEqual(means("capex ×1.2", "capex_scale"), [1.2])


class TestUnits(unittest.TestCase):
    """Each unit to the catalogue's: prices, temperatures, flows, power, energy, lengths."""

    def test_prices(self):
        """ct/kWh, €/MWh, €/GJ and €/kWh to EUR/MWh; €/t for CO2."""
        key = "gas_eur_per_mwh"
        self.assertEqual(means("gas op 4,5 ct/kWh", key), [45.0])
        self.assertEqual(means("gas at €45/MWh", key), [45.0])
        self.assertEqual(means("gas at 45 EUR per MWh", key), [45.0])
        self.assertEqual(means("gas at 12 €/GJ", key), [43.2])
        self.assertEqual(means("electricity at 0.12 €/kWh", "electricity_eur_per_mwh"), [120.0])
        self.assertEqual(means("CO2 at 90 €/t", "carbon_eur_per_t"), [90.0])
        self.assertEqual(parameters.per_mwh("4,5 ct/kWh"), 45.0)
        self.assertEqual(parameters.per_mwh("€0.04 per kWh"), 40.0)

    def test_temperatures(self):
        """°C as written, °F to °C, K as a difference; a change from the value now."""
        self.assertEqual(means("a return of 50 °C", "heat_return_c")[0], 50.0)
        self.assertEqual(means("Return temperature 50 C", "heat_return_c")[0], 50.0)
        self.assertEqual(means("graden: 50 graden", "heat_return_c")[0], 50.0)
        self.assertEqual(round(means("a 140 °F return", "heat_return_c")[0], 4), 60.0)
        self.assertEqual(means("a 10 K lower return", "heat_return_c", 60.0), [50.0])
        self.assertEqual(means("reservoir 9 °F colder", "reservoir_change_k"), [-5.0])
        self.assertEqual(
            means("brine cooled by at most 35 K", "max_brine_cooling_k"), [35.0, -35.0]
        )
        self.assertEqual(means("80 °C instead of 87 °C", "reservoir_change_k")[-2:], [-7.0, 7.0])
        q = Q.extract("70/40 °C heating")
        self.assertEqual([(x.value, x.unit) for x in q], [(70.0, "°C"), (40.0, "°C")])

    def test_flows(self):
        """m3/h as written, l/s x3.6, m3/s x3600."""
        self.assertEqual(means("a flow cap of 250 m³/h", "flow_max_m3h"), [250.0])
        self.assertEqual(means("a flow cap of 250 m3/h", "flow_max_m3h"), [250.0])
        self.assertEqual(means("a flow cap of 80 l/s", "flow_max_m3h"), [288.0])
        self.assertEqual(means("a flow cap of 0.1 m³/s", "flow_max_m3h"), [360.0])

    def test_power_energy_and_length(self):
        """kW, MW, GW, kWp, MWp to MW; MWh, GWh to MWh; m, km both ways."""
        self.assertEqual(means("a 12,000 kW heat pump", "heat_pump_mw")[0], 12.0)
        self.assertEqual(means("a 12 MW heat pump", "heat_pump_mw"), [12.0])
        self.assertEqual(means("0.02 GW boiler", "boiler_mw"), [20.0])
        self.assertEqual(means("500 kWp of solar panels", "solar_mwp"), [0.5])
        self.assertEqual(means("5 MWp of solar panels", "solar_mwp"), [5.0])
        self.assertEqual(means("a 2 GWh heat store", "storage_mwh"), [2000.0])
        self.assertEqual(means("a 500 MWh tank", "storage_mwh"), [500.0])
        self.assertEqual(means("wells 1.5 km apart", "well_spacing_m"), [1500.0])
        self.assertEqual(means("a 2500 m long trunk", "network_length_km"), [2.5])
        self.assertEqual(means("a 3 km trunk", "network_length_km"), [3.0])
        # A yearly energy is no parameter's unit: not a candidate.
        self.assertEqual(Q.candidates("We need 111.67 GWh/yr of heat"), [])


class TestNoKeyChosen(unittest.TestCase):
    """Code says which values a unit allows, for every key of that unit alike."""

    def test_same_values_for_every_key_of_a_unit(self):
        """50 °C fits the supply and the return alike; it fits no price or flow."""
        message = "Return temperature 50 C, what happens?"
        self.assertEqual(means(message, "heat_supply_c"), means(message, "heat_return_c"))
        q = one(message)
        self.assertTrue(Q.compatible(q, "heat_supply_c"))
        self.assertFalse(Q.compatible(q, "gas_eur_per_mwh"))
        self.assertFalse(Q.compatible(q, "flow_max_m3h"))
        self.assertEqual(means(message, "gas_eur_per_mwh"), [])

    def test_bare_numbers_are_not_clear(self):
        """Design names, N-1 and counts give no clear amount."""
        self.assertEqual(Q.candidates("Compare A1 and A3 with N-1, two doublets"), [])
        self.assertEqual(one("gas op 4,5 ct/kWh").as_dict()["means"], "45 EUR/MWh")


if __name__ == "__main__":
    unittest.main()
