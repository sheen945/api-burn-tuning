# -*- coding: utf-8 -*-
"""
三种烧法横向实测 + 压力阶梯找上限
================================================================
两件事一起做：

  上半场「压力阶梯」：用填充式，把间隔一点点压短，看什么时候开始撞 429，
      从而找出这个平台真正的速度上限（旧结论说 3-5 万 token/分钟，本次要核实）

  下半场「三法对比」：三种烧法各用尽量好的参数跑一段，比出又快又稳的那个

结果写入 _烧法对比结果.json
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
GUI = os.path.join(BASE_DIR, "Token燃烧器-GUI.py")
OUT = os.path.join(BASE_DIR, "_烧法对比结果.json")

KEY = os.environ.get("SENSENOVA_API_KEY", "sk-YOUR_API_KEY_HERE")
BASE_URL = "https://token.sensenova.cn/v1"
MODEL = "sensenova-6.8-flash-lite"

spec = importlib.util.spec_from_file_location("gui", GUI)
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)

# 强制长输出的提示词（原版那几条模型会提前收尾，白白浪费 max_tokens）
FORCE_LONG = [
    "请从 1 开始依次输出整数，每个数字单独占一行，一直输出到 5000 为止，"
    "每一个数字都要写出来，绝对不要用省略号、不要跳过、不要总结、不要收尾。",
    "请把 26 个英文字母中的每一个，分别造出 60 个不同的英文单词，并给出中文释义，"
    "格式为一行一个，全部写完，不要省略任何一项。",
    "请依次列出 1 月 1 日到 12 月 31 日的每一天，每一天后面跟一句不少于 40 字的描述，"
    "全部写完，不要用省略号代替中间的日子。",
]

SNOWBALL_BIG = (
    "请把你上一条回复的内容，从头到尾完整重复一遍，一个字都不要省略、不要改写、不要总结。"
    "重复完之后，再在末尾追加一段不少于 3000 字的全新内容。"
)

results = {"开始时间": time.strftime("%Y-%m-%d %H:%M:%S"), "压力阶梯": [], "三法对比": []}


def save():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def base_cfg(mode, **over):
    cfg = {
        "接口地址": BASE_URL, "密钥": KEY, "模型": MODEL, "烧法": mode,
        "目标用量": 10_000_000_000,     # 大到跑不完，靠时间停
        "并发数": 1, "间隔最小": 3.0, "间隔最大": 6.0,
        "单次最大输出": 8000, "填充字符数": 60_000, "限流等待秒数": 15,
    }
    cfg.update(over)
    return cfg


def run_one(名, mode, seconds, **over):
    cfg = base_cfg(mode, **over)
    stop = threading.Event()
    b = gui.Burner(cfg, lambda k, m: None, stop)
    timer = threading.Timer(seconds, stop.set)
    timer.daemon = True
    timer.start()
    t0 = time.time()
    b.run()
    el = max(time.time() - t0, 0.1)
    snap = b.snapshot()
    total = snap["p"] + snap["c"]
    rec = {
        "名称": 名, "烧法": mode,
        "间隔": "%s~%s" % (cfg["间隔最小"], cfg["间隔最大"]),
        "并发": cfg["并发数"],
        "单次最大输出": cfg["单次最大输出"],
        "填充字符数": cfg["填充字符数"],
        "时长秒": round(el, 1),
        "总token": total, "输入token": snap["p"], "输出token": snap["c"],
        "调用次数": snap["calls"], "失败次数": snap["fails"], "限流次数": snap["rate_limits"],
        "平均单次token": int(total / snap["calls"]) if snap["calls"] else 0,
        "速度_每分钟": round(total / el * 60),
        "折算每小时": round(total / el * 3600),
        "成功率": round(snap["calls"] / max(snap["calls"] + snap["rate_limits"], 1) * 100, 1),
    }
    print("  %-24s %10s token | %8s/分 | 调用%3d 限流%3d 失败%3d | 单次均值%8s"
          % (名, f"{total:,}", f"{rec['速度_每分钟']:,}", snap["calls"],
             snap["rate_limits"], snap["fails"], f"{rec['平均单次token']:,}"))
    return rec


def main():
    print("=" * 96)
    print("实测开始")
    print("=" * 96)
    t0 = time.time()
    gui.LONG_OUTPUT_PROMPTS = list(FORCE_LONG)
    gui.SNOWBALL_PROMPT = SNOWBALL_BIG

    # ---------------- 上半场：压力阶梯 ----------------
    print("\n【上半场】压力阶梯：填充式 6 万字符，间隔从宽到窄，看什么时候撞限流")
    ladder = [
        ("间隔8~10秒", 45, {"间隔最小": 8, "间隔最大": 10}),
        ("间隔2~3秒", 45, {"间隔最小": 2, "间隔最大": 3}),
        ("间隔0.2~0.5秒", 45, {"间隔最小": 0.2, "间隔最大": 0.5}),
        ("零间隔连打", 45, {"间隔最小": 0, "间隔最大": 0}),
    ]
    for i, (名, secs, over) in enumerate(ladder):
        if i:
            time.sleep(20)
        rec = run_one(名, "填充式", secs, **over)
        results["压力阶梯"].append(rec)
        save()

    # ---------------- 下半场：三法对比 ----------------
    print("\n【下半场】三种烧法各跑 60 秒（参数都用各自能跑的最优值）")
    time.sleep(30)
    compare = [
        ("填充式", "填充式", 60, {"间隔最小": 0.5, "间隔最大": 1.5, "填充字符数": 90_000}),
        ("长输出式", "长输出式", 60, {"间隔最小": 0.2, "间隔最大": 0.5,
                                 "单次最大输出": 8192}),
        ("雪球式", "雪球式", 60, {"间隔最小": 0.2, "间隔最大": 0.5,
                               "单次最大输出": 8192}),
    ]
    for i, (名, mode, secs, over) in enumerate(compare):
        if i:
            time.sleep(25)
        rec = run_one(名, mode, secs, **over)
        results["三法对比"].append(rec)
        save()

    results["总耗时秒"] = round(time.time() - t0, 1)
    save()

    print("\n" + "=" * 96)
    print("压力阶梯")
    for r in results["压力阶梯"]:
        print("  %-16s %10s/分  限流%3d  成功%5s%%" % (
            r["名称"], f"{r['速度_每分钟']:,}", r["限流次数"], r["成功率"]))
    print("\n三法对比")
    for r in results["三法对比"]:
        print("  %-10s %10s/分  限流%3d  单次均值%9s  每小时%12s" % (
            r["名称"], f"{r['速度_每分钟']:,}", r["限流次数"],
            f"{r['平均单次token']:,}", f"{r['折算每小时']:,}"))
    print("\n总耗时 %.1f 秒" % results["总耗时秒"])
    print("=" * 96)


if __name__ == "__main__":
    main()
