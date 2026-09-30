# -*- coding: utf-8 -*-
"""
本地假接口
================================================================
冒充一个 OpenAI 兼容的 /v1/chat/completions 接口，用来在不花额度、
不碰真实平台的前提下验证程序本身。

用法：
    python _假接口.py 8912

参数：
    --429 秒数     每隔一段时间回一次 429，用来测限流重试
================================================================
"""
import json
import random
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

inflight = 0
max_inflight = 0
lock = threading.Lock()
force_429 = [0.0]        # 设成时间戳后到那个时刻为止一直回 429


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        global inflight, max_inflight
        with lock:
            inflight += 1
            max_inflight = max(max_inflight, inflight)
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n).decode("utf-8"))
            if force_429[0] > time.time():
                body = json.dumps({"error": {"message": "inference exceeds tpm limit",
                                             "code": "429"}}).encode()
                self.send_response(429)
            else:
                chars = sum(len(m.get("content", "")) for m in req.get("messages", []))
                pt = max(int(chars / 1.87), 1)
                ct = 120
                body = json.dumps({
                    "choices": [{"message": {"role": "assistant",
                                             "content": "假回复内容。" * 20}}],
                    "usage": {"prompt_tokens": pt, "completion_tokens": ct},
                }, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass
        finally:
            with lock:
                inflight -= 1

    def log_message(self, *a):
        pass


def main():
    port = 8912
    args = [a for a in sys.argv[1:]]
    if args and args[0].isdigit():
        port = int(args[0])
    if "--429" in args:
        force_429[0] = time.time() + float(args[args.index("--429") + 1])
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("假接口启动在 http://127.0.0.1:%d/v1" % port, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
