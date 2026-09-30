# -*- coding: utf-8 -*-
"""
雪球式 / 长输出式 的最优参数实测
================================================================
这两种烧法的瓶颈是「模型吐字速度」（约 100 token/秒），跟填充式的
「读入速度」完全不是一回事，所以参数不能照搬。

要回答的问题：
  · 长输出式：并发开几个最划算？单次最大输出设多少？
  · 雪球式：并发开几个？追加多少字？单次最大输出设多少？

每组跑 60 秒，比每分钟能烧多少 token。结果写入 _烧法参数结果.json
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
OUT = os.path.join(HERE, "_烧法参数结果.json")
KEY = os.environ.get("SENSENOVA_API_KEY", "sk-YOUR_API_KEY_HERE")
BASE_URL = "https://token.sensenova.cn/v1"
MODEL = "sensenova-6.8-flash-lite"

spec = importlib.util.spec_from_file_location("gui", os.path.join(HERE, "Token燃烧器-GUI.py"))
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)

results = {"开始时间": time.strftime("%Y-%m-%d %H:%M:%S"), "记录": []}


def save():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def run(名, mode, seconds, **over):
    cfg = {
        "接口地址": BASE_URL, "密钥": KEY, "模型": MODEL, "烧法": mode,
        "目标用量": 10_000_000_000,
        "并发数": 2, "间隔最小": 0.2, "间隔最大": 0.6,
        "单次最大输出": 8192, "填充字符数": 100_000, "限流等待秒数": 15,
    }
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
    rec = {
        "名称": 名, "烧法": mode, "并发": cfg["并发数"],
        "单次最大输出": cfg["单次最大输出"], "间隔": "%s~%s" % (cfg["间隔最小"], cfg["间隔最大"]),
        "时长秒": round(el, 1), "总token": total,
        "输入token": s["p"], "输出token": s["c"],
        "调用次数": s["calls"], "限流次数": s["rate_limits"], "失败次数": s["fails"],
        "平均单次token": int(total / s["calls"]) if s["calls"] else 0,
        "速度_每分钟": round(total / el * 60),
        "输出速度_每分钟": round(s["c"] / el * 60),
    }
    print("  %-26s %9s/分 | 输出%9s/分 | 调用%3d 限流%3d | 单次均值%8s"
          % (名, f"{rec['速度_每分钟']:,}", f"{rec['输出速度_每分钟']:,}",
             s["calls"], s["rate_limits"], f"{rec['平均单次token']:,}"), flush=True)
    return rec


def main():
    print("=" * 118, flush=True)
    print("雪球式 / 长输出式 最优参数实测", flush=True)
    print("=" * 118, flush=True)

    plan = [
        ("长输出·并发2·输出8192", "长输出式", 60, {"并发数": 2, "单次最大输出": 8192}),
        ("长输出·并发4·输出8192", "长输出式", 60, {"并发数": 4, "单次最大输出": 8192}),
        ("长输出·并发8·输出8192", "长输出式", 60, {"并发数": 8, "单次最大输出": 8192}),
        ("长输出·并发8·输出2048", "长输出式", 60, {"并发数": 8, "单次最大输出": 2048}),
        ("雪球·并发2·追3000字", "雪球式", 60, {"并发数": 2, "单次最大输出": 8192}),
        ("雪球·并发4·追3000字", "雪球式", 60, {"并发数": 4, "单次最大输出": 8192}),
    ]
    for i, (名, mode, secs, over) in enumerate(plan):
        if i:
            time.sleep(12)
        rec = run(名, mode, secs, **over)
        results["记录"].append(rec)
        save()

    print("\n" + "=" * 118, flush=True)
    print("排名（按每分钟烧掉多少 token）", flush=True)
    for r in sorted(results["记录"], key=lambda x: -x["速度_每分钟"]):
        print("  %-26s %9s/分 | 调用%3d | 单次均值%9s"
              % (r["名称"], f"{r['速度_每分钟']:,}", r["调用次数"],
                 f"{r['平均单次token']:,}"), flush=True)
    print("=" * 118, flush=True)


if __name__ == "__main__":
    main()
