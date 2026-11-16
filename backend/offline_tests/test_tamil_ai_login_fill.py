import importlib.util
from pathlib import Path
from unittest.mock import Mock
import json
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("login_fill", ROOT / "backend/scripts/fill_tamil_ai_owner_login.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def page():
    return {"type": "page", "url": gate.LOGIN,
            "webSocketDebuggerUrl": "ws://127.0.0.1:9238/devtools/page/synthetic"}


def test_exact_fill_rpc_without_submission():
    socket = Mock()
    socket.recv.return_value = json.dumps({"id": 1, "result": {"result": {"value": True}}})
    connect = Mock()
    connect.return_value.__enter__ = Mock(return_value=socket)
    connect.return_value.__exit__ = Mock(return_value=False)
    gate.fill("A+/" * 21 + "Z", [page()], connect)
    request = json.loads(socket.send.call_args.args[0])
    code = request["params"]["expression"]
    assert request["method"] == "Runtime.evaluate"
    assert gate.LOGIN in code and gate.API in code
    assert "login-password" in code and "password.type!=='password'" in code
    assert "HTMLInputElement.prototype" in code and "dispatchEvent" in code
    assert ".submit(" not in code and ".click(" not in code and "fetch(" not in code
    assert "sessionStorage" not in code and "clipboard" not in code
    socket.send.assert_called_once()


@pytest.mark.parametrize("pages", [[], [page(), page()],
    [dict(page(), url="http://127.0.0.1:5174/login")],
    [dict(page(), webSocketDebuggerUrl="ws://example.com:9238/devtools/page/x")]])
def test_wrong_or_ambiguous_target_stops_before_connection(pages):
    connect = Mock()
    with pytest.raises(ValueError):
        gate.fill("A" * 64, pages, connect)
    connect.assert_not_called()


def test_preparation_no_browser_or_stdin(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", Mock(read=Mock(side_effect=AssertionError())))
    gate.main([])
    assert "no credential read or browser connection" in capsys.readouterr().out


def test_bad_confirmation_before_stdin(monkeypatch):
    stream = Mock()
    monkeypatch.setattr(gate.sys, "stdin", stream)
    with pytest.raises(ValueError):
        gate.main(["--execute", "--confirm-run-id", "wrong"])
    stream.read.assert_not_called()


def test_sanitized_errors_and_wrapper_guards():
    source = (ROOT / "backend/scripts/fill_tamil_ai_owner_login.py").read_text()
    wrapper = (ROOT / "backend/scripts/fill_tamil_ai_owner_login.ps1").read_text()
    assert 'except Exception:' in source and 'from None' in source
    assert 'print(payload' not in source and 'print(password' not in source
    assert wrapper.index('if(-not $Execute)') < wrapper.index('ConvertTo-SecureString')
    assert 'Assert-TamilAiPrivateFileAcl' in wrapper and 'ZeroFreeBSTR' in wrapper
    assert 'SendKeys' not in wrapper and 'Set-Clipboard' not in wrapper
