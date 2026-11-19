from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from provider import chat, ProviderError, validate_model


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        mode = 'ok'
        received = None
        def log_message(self, *args):
            pass
        def do_POST(self):
            Handler.received = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.mode == 'redirect':
                self.send_response(307); self.send_header('Location', 'https://example.com/secret'); self.end_headers(); return
            if self.mode == 'error':
                self.send_response(401); self.end_headers(); self.wfile.write(b'secret token here'); return
            self.send_response(200); self.end_headers()
            if self.mode == 'malformed':
                self.wfile.write(b'not json'); return
            body = {'choices':[{'message':{'content':'你好'}, 'finish_reason':'length' if self.mode=='truncated' else 'stop'}]}
            self.wfile.write(json.dumps(body).encode())
    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
    yield {'name':'fixture','model':'fixture','base_url':f'http://127.0.0.1:{http.server_port}/v1'}, Handler
    http.shutdown(); http.server_close(); thread.join()


def test_local_http_protocol_and_thinking_option(server):
    spec, handler = server
    spec['request_options'] = {'chat_template_kwargs':{'enable_thinking':False}}
    result = chat(spec, [{'role':'user','content':'你好'}])
    assert result['text'] == '你好'
    assert handler.received['stream'] is False
    assert handler.received['chat_template_kwargs']['enable_thinking'] is False


@pytest.mark.parametrize('mode', ['redirect', 'error', 'malformed', 'truncated'])
def test_protocol_failures_are_explicit_and_redacted(server, mode):
    spec, handler = server; handler.mode = mode
    with pytest.raises(ProviderError) as error:
        chat(spec, [{'role':'user','content':'hello'}])
    assert 'secret' not in str(error.value)


def test_configuration_prevents_key_embedding_and_payload_override():
    base = {'name':'x','model':'x','base_url':'http://127.0.0.1:8080/v1'}
    for change in ({'api_key':'secret'}, {'base_url':'http://example.com/v1'},
                   {'base_url':'https://user:pass@example.com/v1'},
                   {'request_options':{'messages':[]}},
                   {'request_options':{'chat_template_kwargs':{'enable_thinking':'false'}}}):
        with pytest.raises(ValueError):
            validate_model(dict(base, **change))
