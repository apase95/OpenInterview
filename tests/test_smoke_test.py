import asyncio
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch


class SmokeTests(unittest.TestCase):
    def test_main_offline(self):
        loader = Mock()
        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = loader
        spec = importlib.util.spec_from_file_location(
            "provider_smoke", Path(__file__).resolve().parents[1] / "smoke_test.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"dotenv": dotenv}):
            spec.loader.exec_module(module)
            loader.assert_not_called()
            for failure in (None, False, RuntimeError("PRIVATE_SENTINEL"), asyncio.TimeoutError("PRIVATE_SENTINEL")):
                with self.subTest(failure=type(failure).__name__):
                    output = io.StringIO()
                    with contextlib.ExitStack() as stack:
                        for name in ("test_livekit", "test_gemini", "test_deepgram", "test_elevenlabs"):
                            mock = AsyncMock(return_value=True)
                            if name == "test_livekit" and failure is not None:
                                if isinstance(failure, Exception):
                                    mock.side_effect = failure
                                else:
                                    mock.return_value = failure
                            stack.enter_context(patch.object(module, name, mock))
                        stack.enter_context(contextlib.redirect_stdout(output))
                        result = asyncio.run(module.main())
                    self.assertEqual(result, 0 if failure is None else 1)
                    self.assertIn("Not validated: full pipeline, browser/WebRTC, STT, report, or Sprint 1 exit gate", output.getvalue())
                    self.assertNotIn("PRIVATE_SENTINEL", output.getvalue())


if __name__ == "__main__":
    unittest.main()
