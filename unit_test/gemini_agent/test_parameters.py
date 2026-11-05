"""What a message sets or changes: the model reads it, code keeps only what the message backs."""

import unittest

from gemini_agent import parameters
from gemini_agent.contract import Alternative, DesignBrief


def change(key, value, quote):
    """Return one change as the model gives it."""
    return {"key": key, "value": value, "quote": quote}


class TestCheck(unittest.TestCase):
    """Every change must quote the message, fit its range and show its number."""

    def test_a_return_temperature_is_kept(self):
        """The screenshot's what-if: 50 °C, quoted from the message."""
        msg = "What happens to the design if we lower the heating return temperature to 50 °C?"
        r = parameters.check(
            {"changes": [change("heat_return_c", 50, "heating return temperature to 50 °C")]}, msg
        )
        self.assertEqual(r.changes, {"heat_return_c": 50.0})

    def test_a_quote_not_in_the_message_is_dropped(self):
        """The model may not put words in the user's mouth."""
        r = parameters.check(
            {"changes": [change("gas_eur_per_mwh", 45, "gas at 45 €/MWh")]}, "Design it, please."
        )
        self.assertEqual(r.changes, {})
        self.assertIn("quote", r.dropped[0])

    def test_a_number_not_in_the_quote_is_dropped(self):
        """A value the message never wrote is not kept; a change without an amount is vague."""
        msg = "What if gas got cheaper?"
        r = parameters.check({"changes": [change("gas_eur_per_mwh", 45, "gas got cheaper")]}, msg)
        self.assertEqual(r.changes, {})
        self.assertEqual(r.vague, {"gas_eur_per_mwh": (45.0, "gas got cheaper")})  # asked, not used
        self.assertEqual(
            parameters.amount_options("gas_eur_per_mwh", 69.4, 69.4, "gas got cheaper")[0], 59.0
        )
        r = parameters.check({"changes": [change("gas_eur_per_mwh", 45, "gas")]}, "What about gas?")
        self.assertEqual((r.changes, r.vague), ({}, {}))

    def test_relative_changes_follow_from_the_number(self):
        """10 K lower from 60, 20 % more demand, double the gas price."""
        now = {"heat_return_c": 60.0, "heat_demand_scale": 1.0, "gas_eur_per_mwh": 69.4}
        msg = "a return 10 K lower, 20 % more heat demand and double the gas price"
        r = parameters.check(
            {
                "changes": [
                    change("heat_return_c", 50, "a return 10 K lower"),
                    change("heat_demand_scale", 1.2, "20 % more heat demand"),
                    change("gas_eur_per_mwh", 138.8, "double the gas price"),
                ]
            },
            msg,
            now,
        )
        self.assertEqual(
            r.changes,
            {"heat_return_c": 50.0, "heat_demand_scale": 1.2, "gas_eur_per_mwh": 138.8},
        )

    def test_out_of_range_and_unknown_keys_are_dropped(self):
        """A 500 °C return and a made-up key never pass."""
        msg = "heating return 500 °C and a solar field"
        r = parameters.check(
            {
                "changes": [
                    change("heat_return_c", 500, "heating return 500 °C"),
                    change("solar_mw", 5, "a solar field"),
                ]
            },
            msg,
        )
        self.assertEqual(r.changes, {})
        self.assertEqual(len(r.dropped), 2)

    def test_km_and_percent_are_converted(self):
        """3 km is 3,000 m; 4 % is 0.04."""
        msg = "Try wells at 3 km with a 4 % discount rate."
        r = parameters.check(
            {
                "changes": [
                    change("aquifer_depths_m", [3000], "wells at 3 km"),
                    change("discount_rate", 0.04, "a 4 % discount rate"),
                ]
            },
            msg,
        )
        self.assertEqual(r.changes, {"aquifer_depths_m": [3000.0], "discount_rate": 0.04})

    def test_choices_must_be_known(self):
        """Two injectors and a separate train; a "triple" train is not a choice."""
        msg = "two injectors and a separate separator for each doublet"
        r = parameters.check(
            {
                "changes": [
                    change("injectors", 2, "two injectors"),
                    change("trains", "separate", "a separate separator for each doublet"),
                    change("dispatch", "triple", "each doublet"),
                ]
            },
            msg,
        )
        self.assertEqual(r.changes, {"injectors": 2, "trains": "separate"})

    def test_the_same_value_is_no_change(self):
        """Asking for what is already so changes nothing."""
        r = parameters.check(
            {"changes": [change("heat_return_c", 60, "a 60 °C return")]},
            "with a 60 °C return",
            {"heat_return_c": 60.0},
        )
        self.assertEqual(r.changes, {})

    def test_doublets_described_one_by_one(self):
        """One with two injectors, one with its own separator."""
        msg = "Two doublets: one with two injectors, the other with its own separator."
        r = parameters.check(
            {
                "changes": [],
                "doublets": [{"injectors": 2, "train": 0}, {"injectors": 1, "train": 1}],
            },
            msg,
        )
        self.assertEqual([d.injectors for d in r.doublets], [2, 1])
        self.assertEqual([d.train for d in r.doublets], [0, 1])

    def test_unsupported_is_kept_when_quoted(self):
        """A solar field is said to be outside the model."""
        msg = "Add a solar field to the design."
        r = parameters.check(
            {"unsupported": [{"what": "a solar field", "quote": "solar field"}]}, msg
        )
        self.assertEqual(r.unsupported, ["a solar field"])

    def test_no_number_is_vague(self):
        """A change read with no value asks how much ("gas got cheaper"); a mention does not."""
        now = {"gas_eur_per_mwh": 69.4}
        raw = {"changes": [{"key": "gas_eur_per_mwh", "value": None, "quote": "gas got cheaper"}]}
        r = parameters.check(raw, "what if gas got cheaper?", now)
        self.assertEqual(r.vague, {"gas_eur_per_mwh": (69.4, "gas got cheaper")})
        self.assertEqual(r.changes, {})
        raw = {"changes": [{"key": "gas_eur_per_mwh", "value": None, "quote": "gas"}]}
        self.assertEqual(parameters.check(raw, "tell me about gas", now).vague, {})


class TestCrossed(unittest.TestCase):
    """A return across its supply is not run: it is said, with the value it crosses."""

    NOW = {"cool_supply_c": 20.0, "cool_return_c": 25.0, "heat_supply_c": 100.0}

    def test_a_cooling_return_below_its_supply_is_not_run(self):
        """3 Nov: "what if the cooling return is 16 °C?" ran a year that cannot exist."""
        msg = "What if the cooling return is 16 °C?"
        r = parameters.check(
            {"changes": [change("cool_return_c", 16, "cooling return is 16 °C")]},
            msg,
            self.NOW,
            designed=True,
            pairs=True,
        )
        self.assertEqual(r.changes, {})
        self.assertEqual(r.steps, [])
        quote, why = r.unread[0]
        self.assertEqual(quote, "cooling return is 16 °C")
        self.assertIn("warmer than its supply (cooling supply temperature 20 °C)", why)

    def test_one_that_stays_above_is_kept(self):
        """22 °C over a 20 °C supply is a what-if like any other."""
        r = parameters.check(
            {"changes": [change("cool_return_c", 22, "cooling return is 22 °C")]},
            "What if the cooling return is 22 °C?",
            self.NOW,
            pairs=True,
        )
        self.assertEqual((r.changes, r.unread), ({"cool_return_c": 22.0}, []))

    def test_both_said_and_crossed(self):
        """A heating return over the supply the same message sets is refused too."""
        msg = "Run the heating at 70 °C supply and 75 °C return"
        r = parameters.check(
            {
                "changes": [
                    change("heat_supply_c", 70, "70 °C supply"),
                    change("heat_return_c", 75, "75 °C return"),
                ]
            },
            msg,
            self.NOW,
            pairs=True,
        )
        self.assertEqual(r.changes, {})
        self.assertEqual(len(r.unread), 2)


class TestApply(unittest.TestCase):
    """Changes become a brief (conditions, prices, options) and a what-if's design changes."""

    def test_conditions_prices_and_options(self):
        """A return, a gas price, a demand scale, two injectors."""
        b = parameters.apply(
            DesignBrief(),
            {
                "heat_return_c": 50.0,
                "gas_eur_per_mwh": 45.0,
                "heat_demand_scale": 1.2,
                "injectors": 2,
                "operating_days": 300,
            },
        )
        self.assertEqual(b.heating.return_c, 50.0)
        self.assertEqual(b.prices, {"gas_eur_per_mwh": 45.0})
        self.assertEqual(b.demand_scale, [1.2, 1.0])
        self.assertEqual(b.injectors, 2)
        self.assertEqual(b.rules, {"operating_days": 300})

    def test_a_design_change(self):
        """Two injectors and a smaller boiler on the current design."""
        alt = Alternative(
            code="2D-HP-AB",
            name="x",
            depth_m=2500.0,
            n_doublets=2,
            sizes_mw={"boiler": 12.0, "heat_pump": 4.0},
        )
        new = parameters.change_design(alt, {"injectors": 2, "boiler_mw": 8.0}, 2500.0)
        self.assertEqual([d["injectors"] for d in new.doublets], [2, 2])
        self.assertEqual(new.sizes_mw["boiler"], 8.0)

    def test_labels(self):
        """A what-if's name in words."""
        self.assertEqual(
            parameters.label({"heat_return_c": 50.0}), "heating return temperature 50 °C"
        )


if __name__ == "__main__":
    unittest.main()


class TestAquiferStoreLabel(unittest.TestCase):
    """A what-if's name for an aquifer store."""

    def test_an_ates_store_is_one_store_with_its_size(self):
        """5 Nov: "HT-ATES switched on, heat store at the plant 28000 MWh" read as two stores."""
        said = parameters.label({"storage_ates": 1.0, "storage_mwh": 28000.0})
        self.assertEqual(said, "a heat store in an aquifer (HT-ATES) of 28,000 MWh")
        self.assertEqual(
            parameters.label({"storage_mwh": 2000.0}), "heat store at the plant 2000 MWh"
        )
        self.assertIn("switched on", parameters.label({"storage_ates": 1.0}))
