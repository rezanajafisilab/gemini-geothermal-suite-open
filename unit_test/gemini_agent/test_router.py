"""Which reasoning model runs where, by the GPU memory there is (3 Nov, an RTX 4080 Laptop)."""

import unittest

from gemini_agent.router import GPU_4B_MB, GPU_9B_MB, Hardware, Router


def where(hw: Hardware, device=None):
    """Return the reasoning model, its device and the reason, for this hardware."""
    r = Router(hardware=hw)
    m = r.reasoning(device)
    return m.model, r.device_of(m, device), r.why(device)


class TestTiers(unittest.TestCase):
    """The 9B on the GPU, else the 4B on the GPU, else the 4B on the CPU."""

    def test_9b_on_a_big_gpu(self):
        """A 48 GB card runs the 9B."""
        self.assertEqual(where(Hardware("A6000", 46000, 0, 48000))[:2], ("qwen3.5:9b", "gpu"))

    def test_what_ollama_holds_counts(self):
        """A 12 GB laptop GPU with the reader loaded: 7.2 GB free plus 1.7 GB Ollama frees."""
        hw = Hardware("RTX 4080 Laptop", 7200, 1700, 12282)
        self.assertGreaterEqual(hw.usable_mb, GPU_9B_MB)
        self.assertEqual(where(hw)[:2], ("qwen3.5:9b", "gpu"))

    def test_4b_on_the_gpu_when_the_9b_does_not_fit(self):
        """An 8 GB card runs the 4B on the GPU, not on the CPU."""
        model, dev, why = where(Hardware("RTX 3060", 6000, 0, 8192))
        self.assertEqual((model, dev), ("qwen3.5:4b", "gpu"))
        self.assertIn("instead", why)

    def test_cpu_when_neither_fits(self):
        """Too little GPU memory for the 4B: the CPU."""
        model, dev, why = where(Hardware("MX450", GPU_4B_MB - 1, 0, 6000))
        self.assertEqual((model, dev), ("qwen3.5:4b", "cpu"))
        self.assertIn("CPU", why)

    def test_no_gpu(self):
        """No GPU: the CPU."""
        self.assertEqual(where(Hardware())[:2], ("qwen3.5:4b", "cpu"))

    def test_cpu_switch_wins(self):
        """The header's CPU switch puts the 4B on the CPU whatever the GPU."""
        self.assertEqual(where(Hardware("A6000", 46000), "cpu")[:2], ("qwen3.5:4b", "cpu"))

    def test_usable_never_above_the_card(self):
        """Free plus held memory is capped at the card's total."""
        self.assertEqual(Hardware("x", 7000, 9000, 12000).usable_mb, 12000)

    def test_info_says_why(self):
        """The health check carries the reason for the header."""
        r = Router(hardware=Hardware("RTX 3060", 6000, 0, 8192))
        self.assertIn("why", r.info())


class TestTwoModels(unittest.TestCase):
    """One model a device makes every call (4 Nov): no third model, one window each."""

    def test_the_devices_model_reads_answers_and_writes_code(self):
        """The reader, the answerer and the code writer are the reasoning client itself."""
        for hw, device in ((Hardware("A6000", 46000, 0, 48000), None), (Hardware(), "cpu")):
            r = Router(hardware=hw)
            deep = r.reasoning(device)
            self.assertIs(r.reader(device), deep)
            self.assertIs(r.answerer(device), deep)
            self.assertIs(r.generator(device), deep)
            models = {c.model for c in (r.reader(device), r.answerer(device), deep)}
            self.assertEqual(len(models), 1)

    def test_one_window_a_model(self):
        """The reader's calls use the reasoning model's window: no reload between calls."""
        r = Router(hardware=Hardware("A6000", 46000, 0, 48000))
        self.assertEqual(r.reader().options["num_ctx"], r.reasoning().options["num_ctx"])
        self.assertIs(r.fast, r.reasoning())

    def test_a_reader_given_is_kept(self):
        """A benchmark may still give a separate reader."""
        from gemini_agent.llm import OllamaLLM

        reader = OllamaLLM(model="qwen3:1.7b")
        r = Router(reader, hardware=Hardware("A6000", 46000, 0, 48000))
        self.assertIs(r.reader(), reader)
        self.assertEqual(r.reasoning().model, "qwen3.5:9b")

    def test_a_12_gb_laptop_runs_the_9b(self):
        """About 8 GB free on an RTX 4080 Laptop: the 9B, now that no reader sits beside it."""
        self.assertEqual(
            where(Hardware("RTX 4080 Laptop", 8000, 0, 12282))[:2], ("qwen3.5:9b", "gpu")
        )


if __name__ == "__main__":
    unittest.main()


class TestModelChoice(unittest.TestCase):
    """The model choice (5 Nov).

    By default the first that fits of the 9B on the GPU, the 4B on the GPU, the 9B on the CPU
    and the 4B on the CPU; the header's model switch picks a size on the device picked.
    """

    def pick(self, hw, device=None, size=None):
        """Return the model and the device of this choice."""
        r = Router(hardware=hw)
        m = r.reasoning(device, size)
        return m.model, r.device_of(m, device)

    def test_the_default_order(self):
        """Each step of the default, from a big GPU down to a small computer."""
        from gemini_agent.router import CPU_9B_MB

        big, ram = 46000, CPU_9B_MB + 4000
        self.assertEqual(self.pick(Hardware("A6000", big, 0, 48000, ram)), ("qwen3.5:9b", "gpu"))
        self.assertEqual(self.pick(Hardware("RTX 3060", 6000, 0, 8192, ram)), ("qwen3.5:4b", "gpu"))
        self.assertEqual(self.pick(Hardware(ram_mb=ram)), ("qwen3.5:9b", "cpu"))
        self.assertEqual(self.pick(Hardware(ram_mb=CPU_9B_MB - 1)), ("qwen3.5:4b", "cpu"))
        # A GPU too small for the 4B counts as none: the 9B on the CPU when the memory holds it.
        tiny = Hardware("MX450", GPU_4B_MB - 1, 0, 6000, ram)
        self.assertEqual(self.pick(tiny), ("qwen3.5:9b", "cpu"))

    def test_the_cpu_switch_takes_the_9b_when_it_fits(self):
        """The CPU picked on a GPU machine: the 9B when the memory holds it, else the 4B."""
        from gemini_agent.router import CPU_9B_MB

        self.assertEqual(
            self.pick(Hardware("A6000", 46000, 0, 48000, CPU_9B_MB), "cpu"), ("qwen3.5:9b", "cpu")
        )
        self.assertEqual(
            self.pick(Hardware("A6000", 46000, 0, 48000, 4000), "cpu"), ("qwen3.5:4b", "cpu")
        )

    def test_a_size_picked_is_used_on_the_device_picked(self):
        """9B or 4B from the header, on the GPU or the CPU, whether it fits or not."""
        hw = Hardware("RTX 3060", 6000, 0, 8192, 4000)
        self.assertEqual(self.pick(hw, None, "9b"), ("qwen3.5:9b", "gpu"))
        self.assertEqual(self.pick(hw, None, "4b"), ("qwen3.5:4b", "gpu"))
        self.assertEqual(self.pick(hw, "cpu", "9b"), ("qwen3.5:9b", "cpu"))
        self.assertEqual(
            self.pick(Hardware("A6000", 46000, 0, 48000), "cpu", "4b"), ("qwen3.5:4b", "cpu")
        )
        self.assertEqual(self.pick(Hardware(ram_mb=99000), None, "4b"), ("qwen3.5:4b", "cpu"))

    def test_every_role_follows_the_choice(self):
        """The reader, the answerer and the code writer are the chosen model too."""
        r = Router(hardware=Hardware("A6000", 46000, 0, 48000, 16000))
        for device, size in (("auto", "4b"), ("cpu", "9b"), ("cpu", "4b")):
            deep = r.reasoning(device, size)
            self.assertIs(r.reader(device, size), deep)
            self.assertIs(r.answerer(device, size=size), deep)
            self.assertIs(r.answerer(device, reasoning=True, size=size), deep)
            self.assertIs(r.generator(device, size), deep)

    def test_profiles_for_every_choice(self):
        """The header gets each device and size: its models and why."""
        r = Router(hardware=Hardware("A6000", 46000, 0, 48000, 16000))
        p = r.profiles()
        self.assertEqual(set(p), {"auto", "cpu", "auto:9b", "auto:4b", "cpu:9b", "cpu:4b"})
        self.assertEqual(
            (p["cpu"]["answer"]["model"], p["cpu"]["answer"]["device"]), ("qwen3.5:9b", "cpu")
        )
        self.assertEqual(p["auto:4b"]["answer"]["model"], "qwen3.5:4b")
        self.assertIn("picked in the header", p["cpu:4b"]["why"])
        self.assertIn("fits", r.why("cpu"))

    def test_memory_from_the_environment(self):
        """``DIOSCURI_RAM_MB`` sets the memory (for a test, or a computer that cannot say)."""
        import os
        from unittest import mock

        from gemini_agent.router import available_ram_mb

        with mock.patch.dict(os.environ, {"DIOSCURI_RAM_MB": "12345"}):
            self.assertEqual(available_ram_mb(), 12345)
        self.assertGreaterEqual(available_ram_mb(), 0)
