import tempfile,unittest
from pathlib import Path
from nixlms_core import NixLMsNeuralCore
from nixlms_core.eeg import EEGInspiredEngine
from nixlms_core.mental_map import MentalMap
from nixlms_core.neural import LIFNetwork

class CoreTests(unittest.TestCase):
    def test_eeg_bands(self):
        engine=EEGInspiredEngine(); bands=engine.band_energy(engine.synthesize(1.0))
        self.assertEqual(set(bands),{"delta","theta","alpha","beta","gamma"})
        self.assertAlmostEqual(sum(bands.values()),1.0,places=5)
    def test_learn_and_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai=NixLMsNeuralCore(Path(tmp)); ai.learn("qual é a capital do Brasil","Brasília")
            self.assertEqual(ai.respond("qual é a capital do Brasil",use_language=False),"Brasília")
            self.assertGreater(ai.status()["semantic_items"],0)
    def test_empty_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("Digite",NixLMsNeuralCore(Path(tmp)).respond("  "))
    def test_recurrent_weights_persist(self):
        net=LIFNetwork(); clone=LIFNetwork()
        self.assertTrue(clone.load_state_dict(net.state_dict()))
        self.assertEqual(len(clone.w_rec),clone.hidden_size)
    def test_mental_map_association(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph=MentalMap(Path(tmp)/"map.json"); graph.observe("python programa linguagem")
            self.assertTrue(graph.associate("python"))
    def test_dataset_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            ai=NixLMsNeuralCore(Path(tmp)); ai.learning.dataset.add("capital do Brasil","Brasília","test")
            metrics=ai.learning.evaluate()
            self.assertEqual(metrics["samples"],1)
            self.assertGreaterEqual(metrics["accuracy"],0.0)

if __name__=="__main__": unittest.main()
