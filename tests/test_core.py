import tempfile, unittest
from pathlib import Path
from nixlms_core import NixLMsNeuralCore
from nixlms_core.eeg import EEGInspiredEngine

class CoreTests(unittest.TestCase):
    def test_eeg_bands(self):
        bands=EEGInspiredEngine().band_energy(EEGInspiredEngine().synthesize(1.0))
        self.assertEqual(set(bands),{"delta","theta","alpha","beta","gamma"})
        self.assertAlmostEqual(sum(bands.values()),1.0,places=5)
    def test_learn_and_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai=NixLMsNeuralCore(Path(tmp)); ai.learn("qual é a capital do Brasil","Brasília")
            self.assertEqual(ai.respond("qual é a capital do Brasil"),"Brasília")
            self.assertGreater(ai.status()["semantic_items"],0)
    def test_empty_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("Digite",NixLMsNeuralCore(Path(tmp)).respond("  "))

if __name__=="__main__": unittest.main()
