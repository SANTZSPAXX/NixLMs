import contextlib
import io
import unittest
from unittest.mock import Mock

from neural_core import _huggingface_command


class HuggingFaceCliTests(unittest.TestCase):
    def test_search_preserves_multiword_query(self):
        ai = Mock()
        ai.huggingface.search.return_value = []
        with contextlib.redirect_stdout(io.StringIO()):
            _huggingface_command(ai, "/hf buscar model multilingual Portuguese")
        ai.huggingface.search.assert_called_once_with(
            "model", "multilingual Portuguese", limit=12
        )

    def test_details_preserves_repository_id(self):
        ai = Mock()
        ai.huggingface.details.return_value = {"id": "org/model"}
        with contextlib.redirect_stdout(io.StringIO()):
            _huggingface_command(ai, "/hf detalhes model org/model")
        ai.huggingface.details.assert_called_once_with("model", "org/model")

    def test_status_never_requests_credentials(self):
        ai = Mock()
        ai.huggingface.status.return_value = {
            "anonymous_public_access": True, "token_required": False
        }
        with contextlib.redirect_stdout(io.StringIO()):
            _huggingface_command(ai, "/hf status")
        ai.huggingface.status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
