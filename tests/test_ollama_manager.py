import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from nixlms_core.ollama_manager import OllamaManager


class FakeLanguage:
    def __init__(self, reachable=True, models=None, local_host=True):
        self.host = "http://127.0.0.1:11434"
        self.local_host = local_host
        self.reachable = reachable
        self.model = "qwen2.5:0.5b"
        self.installed_models = list(models or [])
        self.last_error = None
        self.last_used_model = None
        self.last_generation = None

    def refresh_models(self):
        return list(self.installed_models)



class FakeProcess:
    def __init__(
        self, wait_outcomes=None, returncode=None,
        terminate_error=None, kill_error=None,
    ):
        self.wait_outcomes = list(wait_outcomes or [])
        self.returncode = returncode
        self.terminate_error = terminate_error
        self.kill_error = kill_error
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_timeouts = []

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminate_calls += 1
        if self.terminate_error is not None:
            raise self.terminate_error

    def kill(self):
        self.kill_calls += 1
        if self.kill_error is not None:
            raise self.kill_error
        self.returncode = -9

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        if self.wait_outcomes:
            outcome = self.wait_outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            self.returncode = outcome
            return outcome
        if self.returncode is not None:
            return self.returncode
        raise subprocess.TimeoutExpired("ollama serve", timeout)


class OllamaManagerTests(unittest.TestCase):
    def test_status_reports_binary_and_exact_model(self):
        language = FakeLanguage(models=["qwen2.5:0.5b"])
        manager = OllamaManager(language)
        with patch.object(manager, "executable", return_value="/usr/bin/ollama"):
            status = manager.status()
        self.assertTrue(status["installed"])
        self.assertTrue(status["model_installed"])
        self.assertEqual(status["executable"], "/usr/bin/ollama")
        self.assertEqual(status["bind_scope"], "unverified_preexisting")

    def test_start_does_not_spawn_duplicate_service(self):
        language = FakeLanguage(reachable=True)
        manager = OllamaManager(language)
        with patch.object(manager, "executable") as executable, \
             patch("nixlms_core.ollama_manager.subprocess.Popen") as popen:
            result = manager.start_service()
        self.assertTrue(result["ok"])
        self.assertTrue(result["already_running"])
        self.assertEqual(result["bind_scope"], "unverified_preexisting")
        executable.assert_not_called()
        popen.assert_not_called()

    def test_managed_service_overrides_inherited_wildcard_bind(self):
        language = FakeLanguage(reachable=False)
        manager = OllamaManager(language)
        process = Mock()
        process.poll.return_value = None

        def spawn(*args, **kwargs):
            language.reachable = True
            return process

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"OLLAMA_HOST": "0.0.0.0:11434"}):
                with patch.object(Path, "home", return_value=Path(tmp)):
                    with patch.object(manager, "executable", return_value="/usr/bin/ollama"):
                        with patch(
                            "nixlms_core.ollama_manager.subprocess.Popen",
                            side_effect=spawn,
                        ) as popen:
                            result = manager.start_service()
                            child_env = popen.call_args.kwargs["env"]
                            self.assertEqual(os.environ["OLLAMA_HOST"], "0.0.0.0:11434")

        self.assertTrue(result["ok"])
        self.assertEqual(child_env["OLLAMA_HOST"], "127.0.0.1:11434")
        self.assertEqual(result["bind_scope"], "configured_loopback")
        self.assertEqual(result["bind_address"], "127.0.0.1:11434")
        self.assertIsNone(manager.last_cleanup)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    def test_loopback_bind_preserves_port_and_formats_ipv6(self):
        language = FakeLanguage()
        manager = OllamaManager(language)

        language.host = "http://localhost:12345"
        self.assertEqual(manager._loopback_bind_address(), "127.0.0.1:12345")

        language.host = "http://[::1]:12346"
        self.assertEqual(manager._loopback_bind_address(), "[::1]:12346")

        language.host = "http://127.0.0.1:0"
        with self.assertRaises(RuntimeError):
            manager._loopback_bind_address()

    def test_start_refuses_non_loopback_endpoint(self):
        language = FakeLanguage(reachable=False, local_host=False)
        manager = OllamaManager(language)
        result = manager.start_service()
        self.assertFalse(result["ok"])
        self.assertIn("loopback", result["error"])


    def _run_start_until_readiness_timeout(self, manager, process):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(Path, "home", return_value=Path(tmp)):
                with patch.object(manager, "executable", return_value="/usr/bin/ollama"):
                    with patch(
                        "nixlms_core.ollama_manager.subprocess.Popen",
                        return_value=process,
                    ) as popen:
                        with patch(
                            "nixlms_core.ollama_manager.time.monotonic",
                            side_effect=[0.0, 0.0, 2.0],
                        ):
                            with patch("nixlms_core.ollama_manager.time.sleep"):
                                result = manager.start_service()
        return result, popen

    def test_start_timeout_terminates_only_managed_process(self):
        language = FakeLanguage(reachable=False)
        manager = OllamaManager(language, readiness_timeout=1)
        process = FakeProcess(wait_outcomes=[-15])

        result, popen = self._run_start_until_readiness_timeout(manager, process)

        self.assertFalse(result["ok"])
        self.assertIn("não ficou pronto", result["startup_error"])
        self.assertEqual(result["cleanup"]["status"], "terminated")
        self.assertTrue(result["cleanup"]["confirmed"])
        self.assertEqual(process.terminate_calls, 1)
        self.assertEqual(process.kill_calls, 0)
        self.assertEqual(process.wait_timeouts, [manager.CLEANUP_TERMINATE_TIMEOUT])
        self.assertIsNone(manager.process)
        popen.assert_called_once()

    def test_start_timeout_kills_process_when_terminate_wait_expires(self):
        language = FakeLanguage(reachable=False)
        manager = OllamaManager(language, readiness_timeout=1)
        process = FakeProcess(wait_outcomes=[
            subprocess.TimeoutExpired("ollama serve", 2.0),
            -9,
        ])

        result, _ = self._run_start_until_readiness_timeout(manager, process)

        self.assertFalse(result["ok"])
        self.assertEqual(result["cleanup"]["status"], "killed")
        self.assertTrue(result["cleanup"]["confirmed"])
        self.assertEqual(process.terminate_calls, 1)
        self.assertEqual(process.kill_calls, 1)
        self.assertEqual(
            process.wait_timeouts,
            [manager.CLEANUP_TERMINATE_TIMEOUT, manager.CLEANUP_KILL_TIMEOUT],
        )
        self.assertIsNone(manager.process)

    def test_cleanup_skips_process_that_already_exited(self):
        manager = OllamaManager(FakeLanguage(reachable=False))
        process = FakeProcess(returncode=0)
        manager.process = process

        result = manager._cleanup_managed_process()

        self.assertEqual(result["status"], "already_exited")
        self.assertTrue(result["confirmed"])
        self.assertEqual(process.terminate_calls, 0)
        self.assertEqual(process.kill_calls, 0)
        self.assertEqual(process.wait_timeouts, [])
        self.assertIsNone(manager.process)

    def test_preexisting_service_is_never_cleaned_up(self):
        language = FakeLanguage(reachable=True)
        manager = OllamaManager(language)
        with patch.object(manager, "executable") as executable, \\
             patch("nixlms_core.ollama_manager.subprocess.Popen") as popen:
            result = manager.start_service()

        self.assertTrue(result["ok"])
        self.assertTrue(result["already_running"])
        self.assertEqual(result["bind_scope"], "unverified_preexisting")
        self.assertIsNone(result.get("cleanup"))
        self.assertIsNone(manager.last_cleanup)
        executable.assert_not_called()
        popen.assert_not_called()

    def test_cleanup_failure_preserves_startup_error_and_process_reference(self):
        language = FakeLanguage(reachable=False)
        manager = OllamaManager(language, readiness_timeout=1)
        process = FakeProcess(
            wait_outcomes=[
                subprocess.TimeoutExpired("ollama serve", 2.0),
                subprocess.TimeoutExpired("ollama serve", 2.0),
            ],
            terminate_error=PermissionError("terminate denied"),
            kill_error=PermissionError("kill denied"),
        )

        result, popen = self._run_start_until_readiness_timeout(manager, process)

        self.assertFalse(result["ok"])
        self.assertIn("não ficou pronto", result["startup_error"])
        self.assertIn(result["startup_error"], result["error"])
        self.assertEqual(result["cleanup"]["status"], "unconfirmed")
        self.assertFalse(result["cleanup"]["confirmed"])
        self.assertTrue(any("terminate denied" in error for error in result["cleanup"]["errors"]))
        self.assertTrue(any("kill denied" in error for error in result["cleanup"]["errors"]))
        self.assertIs(manager.process, process)

        retry = manager.start_service()
        self.assertFalse(retry["ok"])
        self.assertTrue(retry["managed_process_alive"])
        self.assertIn("evitar duplicação", retry["error"])
        popen.assert_called_once()
        self.assertEqual(process.terminate_calls, 1)
        self.assertEqual(process.kill_calls, 1)

    def test_cleanup_handles_process_exit_race_between_poll_and_terminate(self):
        manager = OllamaManager(FakeLanguage(reachable=False))
        process = FakeProcess(
            wait_outcomes=[-15],
            terminate_error=ProcessLookupError("process already exited"),
        )
        manager.process = process

        result = manager._cleanup_managed_process()

        self.assertEqual(result["status"], "already_exited")
        self.assertTrue(result["confirmed"])
        self.assertEqual(process.terminate_calls, 1)
        self.assertEqual(process.kill_calls, 0)
        self.assertIsNone(manager.process)

    def test_cleanup_is_idempotent_after_confirmed_exit(self):
        manager = OllamaManager(FakeLanguage(reachable=False))
        process = FakeProcess(wait_outcomes=[0])
        manager.process = process

        first = manager._cleanup_managed_process()
        second = manager._cleanup_managed_process()

        self.assertEqual(first["status"], "terminated")
        self.assertEqual(second["status"], "not_managed")
        self.assertEqual(process.terminate_calls, 1)
        self.assertEqual(process.kill_calls, 0)
        self.assertEqual(process.wait_timeouts, [manager.CLEANUP_TERMINATE_TIMEOUT])

    def test_pull_does_not_download_model_already_installed(self):
        language = FakeLanguage(models=["qwen2.5:0.5b"])
        manager = OllamaManager(language)
        with patch.object(manager, "executable") as executable, \
             patch("nixlms_core.ollama_manager.subprocess.run") as run:
            result = manager.pull_model()
        self.assertTrue(result["ok"])
        self.assertTrue(result["already_installed"])
        executable.assert_not_called()
        run.assert_not_called()

    def test_pull_requires_reachable_local_service(self):
        language = FakeLanguage(reachable=False)
        language.last_error = "connection refused"
        manager = OllamaManager(language)
        with patch.object(manager, "executable") as executable, \
             patch("nixlms_core.ollama_manager.subprocess.run") as run:
            result = manager.pull_model()
        self.assertFalse(result["ok"])
        self.assertIn("não está acessível", result["error"])
        executable.assert_not_called()
        run.assert_not_called()

    def test_pull_rejects_invalid_model_name(self):
        language = FakeLanguage()
        manager = OllamaManager(language)
        result = manager.pull_model("nome de modelo")
        self.assertFalse(result["ok"])
        self.assertIn("inválido", result["error"])


if __name__ == "__main__":
    unittest.main()
