# -*- coding: utf-8 -*-
"""
雪球式 / 长输出式 参数细调（第二轮）
================================================================
第一轮已经测出：长输出式「并发8 + 输出2048」最好，雪球式「并发4」最好。
这一轮接着往下压：
  · 单次输出还能不能再小（1024 / 512）
  · 并发还能不能再高（16）
  · 雪球式每轮多追加一点是不是更好（6000 字）

每组 60 秒。结果写入 _烧法参数结果2.json
================================================================
"""
import importlib.util
import json
import os
import sys
import threading
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_烧法参数结果2.json")
KEY = os.environ.get("SENSENOVA_API_KEY", "sk-YOUR_API_KEY_HERE")

spec = importlib.util.spec_from_file_location("gui", os.path.join(HERE, "Token燃烧器-GUI.py"))
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)

SNOWBALL_6000 = (
    "请把你上一条回复的内容，从头到尾完整重复一遍，一个字都不要省略、不要改写、不要总结。"
    "重复完之后，再在末尾追加一段不少于 6000 字的全新内容。"
)
_saved_snowball = gui.SNOWBALL_PROMPT

results = {"记录": []}


def run(名, mode, seconds, **over):
    cfg = {"接口地址": "https://token.sensenova.cn/v1", "密钥": KEY,
           "模型": "sensenova-6.8-flash-lite", "烧法": mode, "目标用量": 10_000_000_000,
           "并发数": 8, "间隔最小": 0.2, "间隔最大": 0.6,
           "单次最大输出": 2048, "填充字符数": 100_000, "限流等待秒数": 15}
    cfg.update(over)
    stop = threading.Event()
    b = gui.Burner(cfg, lambda k, m: None, stop)
    t = threading.Timer(seconds, stop.set)
    t.daemon = True
    t.start()
    t0 = time.time()
    b.run()
    el = max(time.time() - t0, 0.1)
    s = b.snapshot()
    total = s["p"] + s["c"]
    rec = {"名称": 名, "烧法": mode, "并发": cfg["并发数"],
           "单次最大输出": cfg["单次最大输出"], "时长秒": round(el, 1),
           "总token": total, "输入token": s["p"], "输出token": s["c"],
           "调用次数": s["calls"], "限流次数": s["rate_limits"], "失败次数": s["fails"],
           "平均单次token": int(total / s["calls"]) if s["calls"] else 0,
           "速度_每分钟": round(total / el * 60),
           "输出速度_每分钟": round(s["c"] / el * 60)}
    print("  %-26s %9s/分 | 输出%8s/分 | 调用%3d 限流%3d | 单次均值%8s"
          % (名, f"{rec['速度_每分钟']:,}", f"{rec['输出速度_每分钟']:,}", s["calls"],
             s["rate_limits"], f"{rec['平均单次token']:,}"), flush=True)
    return rec


def main():
    plan = [
        ("长输出·并发8·输出1024", "长输出式", 60, {"并发数": 8, "单次最大输出": 1024}),
        ("长输出·并发8·输出512", "长输出式", 60, {"并发数": 8, "单次最大输出": 512}),
        ("长输出·并发16·输出1024", "长输出式", 60, {"并发数": 16, "单次最大输出": 1024}),
        ("雪球·并发4·追6000字", "雪球式", 60, {"并发数": 4, "单次最大输出": 8192,
                                          "_雪球追加": 6000}),
    ]
    for i, (名, mode, secs, over) in enumerate(plan):
        if i:
            time.sleep(12)
        if over.pop("_雪球追加", None):
            gui.SNOWBALL_PROMPT = SNOWBALL_6000
        else:
            gui.SNOWBALL_PROMPT = _saved_snowball
        results["记录"].append(run(名, mode, secs, **over))
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    print("完成", flush=True)


if __name__ == "__main__":
    main()
