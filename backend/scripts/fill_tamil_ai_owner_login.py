"""Fill the normal React login form through loopback CDP; never submit."""
import argparse
import json
import sys
from urllib.request import build_opener, ProxyHandler
from urllib.parse import urlsplit

RUN_ID = "14405b71b0504036a35ff55c7a9da132"
LOGIN = "http://127.0.0.1:5175/login"
API = "http://127.0.0.1:8014/api/v1"
EMAIL = f"tamil-ai-owner-{RUN_ID}@lankapex-test.example.com"


def target(pages):
    matches = [p for p in pages if p.get("type") == "page" and p.get("url") == LOGIN]
    if len(matches) != 1:
        raise ValueError("target")
    url = matches[0].get("webSocketDebuggerUrl", "")
    parsed = urlsplit(url)
    if (parsed.scheme != "ws" or parsed.hostname != "127.0.0.1" or parsed.port != 9238
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not parsed.path.startswith("/devtools/page/")):
        raise ValueError("target")
    return url


def expression(password):
    if not isinstance(password, str) or len(password) != 64 or any(
            c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/" for c in password):
        raise ValueError("credential_format")
    return """(async()=>{
      if(location.href!==LOGIN)throw Error('target');
      const {default:api}=await import('/src/services/api.js');
      if(api.defaults.baseURL!==API)throw Error('api_target');
      const email=document.getElementById('login-email');
      const password=document.getElementById('login-password');
      if(!email||!password||email.disabled||password.disabled||password.type!=='password'
         ||!email.form||email.form!==password.form||email.form.querySelectorAll('input[type=password]').length!==1)
        throw Error('form');
      const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
      set.call(email,EMAIL);email.dispatchEvent(new Event('input',{bubbles:true}));
      set.call(password,PASSWORD);password.dispatchEvent(new Event('input',{bubbles:true}));
      password.blur();
      return email.value===EMAIL&&password.value===PASSWORD;
    })()""".replace("LOGIN", json.dumps(LOGIN)).replace("API", json.dumps(API)).replace(
        "EMAIL", json.dumps(EMAIL)).replace("PASSWORD", json.dumps(password))


def fill(password, pages, connect):
    url = target(pages)
    code = expression(password)
    with connect(url, open_timeout=5, close_timeout=2, max_size=65536, proxy=None) as socket:
        socket.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": code, "awaitPromise": True, "returnByValue": True}}))
        reply = json.loads(socket.recv(timeout=10))
        if (reply.get("id") != 1 or reply.get("error") or reply.get("result", {}).get("exceptionDetails")
                or reply.get("result", {}).get("result", {}).get("value") is not True):
            raise ValueError("fill")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-run-id", default="")
    args = parser.parse_args(argv)
    if not args.execute:
        print("PASS: fill-only preparation; no credential read or browser connection")
        return
    if args.confirm_run_id != RUN_ID:
        raise ValueError("confirmation")
    # Bounded stdin only: never credentials in command-line arguments or files.
    payload = json.loads(sys.stdin.read(4096))
    if set(payload) != {"password"}:
        raise ValueError("input")
    import logging
    logging.getLogger("websockets").disabled = True
    from websockets.sync.client import connect
    opener = build_opener(ProxyHandler({}))
    with opener.open("http://127.0.0.1:9238/json/list", timeout=5) as response:
        pages = json.loads(response.read(65536))
    fill(payload["password"], pages, connect)
    print("PASS: exact isolated Owner login form filled; no login submitted")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("STOP: isolated login fill failed; no automatic retry or submission") from None
