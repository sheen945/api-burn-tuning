# -*- coding: utf-8 -*-
"""
推荐参数实测（最后一轮）
================================================================
前面已经测出真正的瓶颈是「每分钟约 40 次请求」，不是 token 总量。
所以最优解一定是：把请求次数顶到接近 40 次/分钟，同时让每一次请求塞得尽可能大。

这一轮把几组候选参数摆在一起跑，选出又快又稳的那一组，
跑完就直接填进程序默认值。

结果写入 _推荐参数结果.json
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
OUT = os.path.join(BASE_DIR, "_推荐参数结果.json")
KEY = os.environ.get("SENSENOVA_API_KEY", "sk-YOUR_API_KEY_HERE")

spec = importlib.util.spec_from_file_location("gui", os.path.join(BASE_DIR, "Token燃烧器-GUI.py"))
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)

results = {"开始时间": time.strftime("%Y-%m-%d %H:%M:%S"), "记录": []}


def save():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def run(名, seconds, 字符数, 并发, lo=0.2, hi=0.6):
    cfg = {
        "接口地址": "https://token.sensenova.cn/v1", "密钥": KEY,
        "模型": "sensenova-6.8-flash-lite", "烧法": "填充式",
        "目标用量": 10_000_000_000,
        "并发数": 并发, "间隔最小": lo, "间隔最大": hi,
        "单次最大输出": 64, "填充字符数": 字符数, "限流等待秒数": 15,
    }
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
    rpm = (s["calls"] + s["rate_limits"]) / el * 60
    rec = {
        "名称": 名, "填充字符数": 字符数, "并发": 并发,
        "时长秒": round(el, 1), "总token": total,
        "调用次数": s["calls"], "限流次数": s["rate_limits"], "失败次数": s["fails"],
        "平均单次token": int(total / s["calls"]) if s["calls"] else 0,
        "速度_每分钟": round(total / el * 60),
        "折算每小时": round(total / el * 3600),
        "请求次数每分钟": round(rpm, 1),
        "单次耗时秒": round(el / s["calls"], 2) if s["calls"] else 0,
        "429原文": list(dict.fromkeys(warns))[:3],
    }
    print("  %-22s %11s/分 | 请求%5.1f次/分 | 调用%3d 限流%3d | 单次%8s | 单次耗时%4.2fs | 每小时%11s"
          % (名, f"{rec['速度_每分钟']:,}", rpm, s["calls"], s["rate_limits"],
             f"{rec['平均单次token']:,}", rec["单次耗时秒"], f"{rec['折算每小时']:,}"))
    if rec["429原文"]:
        print("     429：%s" % rec["429原文"][0][:120])
    return rec


def main():
    print("=" * 118)
    print("推荐参数实测")
    print("=" * 118)
    plan = [
        ("6万字符·并发3", 45, 60_000, 3),
        ("10万字符·并发2", 45, 100_000, 2),
        ("10万字符·并发3", 45, 100_000, 3),
        ("15万字符·并发2", 45, 150_000, 2),
    ]
    for i, (名, secs, chars, conc) in enumerate(plan):
        if i:
            time.sleep(20)
        rec = run(名, secs, chars, conc)
        results["记录"].append(rec)
        save()

    print("\n" + "=" * 118)
    print("排名（按每分钟烧掉多少 token）")
    for r in sorted(results["记录"], key=lambda x: -x["速度_每分钟"]):
        print("  %-22s %11s/分 | 请求%5.1f次/分 | 限流%3d | 单次耗时%4.2fs"
              % (r["名称"], f"{r['速度_每分钟']:,}", r["请求次数每分钟"],
                 r["限流次数"], r["单次耗时秒"]))
    print("=" * 118)


if __name__ == "__main__":
    main()
