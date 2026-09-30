# -*- coding: utf-8 -*-
"""
并发实测 + 429 原始报错抓取
================================================================
上一轮已经测出：单条连接、零间隔、每次 3.2 万 token 的填充式，能跑到
每分钟 72 万 token 而且不撞限流。这一轮回答两个后续问题：

  1. 开并发（2/3 条连接同时跑）能不能更快？
  2. 万一撞了限流，接口原文到底说了什么？（上一轮没抓下来）

结果写入 _并发实测结果.json
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE_DIR, "_并发实测结果.json")
KEY = os.environ.get("SENSENOVA_API_KEY", "sk-YOUR_API_KEY_HERE")

spec = importlib.util.spec_from_file_location("gui", os.path.join(BASE_DIR, "Token燃烧器-GUI.py"))
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)

results = {"开始时间": time.strftime("%Y-%m-%d %H:%M:%S"), "记录": []}


def save():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def run(名, seconds, **over):
    cfg = {
        "接口地址": "https://token.sensenova.cn/v1", "密钥": KEY,
        "模型": "sensenova-6.8-flash-lite", "烧法": "填充式",
        "目标用量": 10_000_000_000,
        "并发数": 1, "间隔最小": 0, "间隔最大": 0,
        "单次最大输出": 64, "填充字符数": 60_000, "限流等待秒数": 15,
    }
    cfg.update(over)
    stop = threading.Event()
    warns = []
    b = gui.Burner(cfg, lambda k, m: warns.append(str(m)) if k == "warn" else None, stop)
    t = threading.Timer(seconds, stop.set)
    t.daemon = True
    t.start()
    t0 = time.time()
    b.run()
    el = max(time.time() - t0, 0.1)
    s = b.snapshot()
    total = s["p"] + s["c"]
    rec = {
        "名称": 名, "时长秒": round(el, 1), "并发": cfg["并发数"],
        "间隔": "%s~%s" % (cfg["间隔最小"], cfg["间隔最大"]),
        "填充字符数": cfg["填充字符数"],
        "总token": total, "调用次数": s["calls"], "限流次数": s["rate_limits"],
        "失败次数": s["fails"],
        "平均单次token": int(total / s["calls"]) if s["calls"] else 0,
        "速度_每分钟": round(total / el * 60),
        "折算每小时": round(total / el * 3600),
        "单次最快秒": round(min([t for t, _ in s["timeline"]] or [0]), 2),
        "限流原文": list(dict.fromkeys(warns))[:5],
    }
    print("  %-18s %10s/分 | 调用%3d 限流%3d 失败%3d | 单次均值%8s | 每小时%12s"
          % (名, f"{rec['速度_每分钟']:,}", s["calls"], s["rate_limits"], s["fails"],
             f"{rec['平均单次token']:,}", f"{rec['折算每小时']:,}"))
    if rec["限流原文"]:
        print("     限流原文：%s" % rec["限流原文"][0][:160])
    return rec


def main():
    print("=" * 100)
    print("并发实测开始")
    print("=" * 100)
    plan = [
        ("1并发·零间隔", 40, {"并发数": 1}),
        ("2并发·零间隔", 40, {"并发数": 2}),
        ("3并发·零间隔", 40, {"并发数": 3}),
        ("1并发·10万字符", 40, {"并发数": 1, "填充字符数": 100_000}),
        ("1并发·3万字符", 40, {"并发数": 1, "填充字符数": 30_000}),
    ]
    for i, (名, secs, over) in enumerate(plan):
        if i:
            time.sleep(12)
        rec = run(名, secs, **over)
        results["记录"].append(rec)
        save()

    print("\n" + "=" * 100)
    for r in results["记录"]:
        print("  %-18s %10s/分 | 限流%3d | 单次均值%9s" % (
            r["名称"], f"{r['速度_每分钟']:,}", r["限流次数"], f"{r['平均单次token']:,}"))
    print("=" * 100)


if __name__ == "__main__":
    main()
