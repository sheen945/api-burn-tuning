# -*- coding: utf-8 -*-
"""
积分兑换比例实测
================================================================
做法：先读后台积分 → 烧掉一个已知的 token 量 → 再读一次积分，
      两次之差就是烧掉这些 token 花掉多少积分，从而算出
      「1 积分 ≈ 多少 token」。

为什么要分两种烧法各测一遍：输入 token 和输出 token 的计价可能不同，
所以填充式（几乎全是输入）和长输出式（几乎全是输出）要分开测。

用法：
    python _积分换算实测.py 填充式 2000000
    python _积分换算实测.py 长输出式 300000

结果追加到 _积分换算结果.json
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
OUT = os.path.join(HERE, "_积分换算结果.json")
KEY = os.environ.get("SENSENOVA_API_KEY", "sk-YOUR_API_KEY_HERE")
BASE_URL = "https://token.sensenova.cn/v1"
MODEL = "sensenova-6.8-flash-lite"

# 各烧法用的参数（和程序里的最优参数保持一致，2026-09-12 实测选出来的）
MODE_PARAMS = {
    "填充式": {"并发数": 2, "间隔最小": 0.2, "间隔最大": 0.6,
              "单次最大输出": 64, "填充字符数": 100_000},
    "长输出式": {"并发数": 8, "间隔最小": 0.2, "间隔最大": 0.6,
               "单次最大输出": 2048, "填充字符数": 100_000},
    "雪球式": {"并发数": 4, "间隔最小": 0.2, "间隔最大": 0.6,
              "单次最大输出": 8192, "填充字符数": 100_000},
}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


读积分 = load_mod("readpoints", os.path.join(HERE, "_读积分.py"))
gui = load_mod("gui", os.path.join(HERE, "Token燃烧器-GUI.py"))


def points(reload=True):
    """读一次 Flash-Lite 积分池"""
    data, _ = 读积分.read_once(reload=reload)
    fl = data.get("flash_lite") or {}
    return fl


def burn(mode, target_tokens, seconds_cap=900, over=None):
    """用真实接口烧到目标 token 数，返回统计"""
    p = dict(MODE_PARAMS[mode])
    if over:
        p.update(over)
    cfg = {
        "接口地址": BASE_URL, "密钥": KEY, "模型": MODEL, "烧法": mode,
        "目标用量": target_tokens, "限流等待秒数": 15,
    }
    cfg.update(p)
    stop = threading.Event()
    b = gui.Burner(cfg, lambda k, m: None, stop)
    cap = threading.Timer(seconds_cap, stop.set)
    cap.daemon = True
    cap.start()
    t0 = time.time()
    b.run()
    el = max(time.time() - t0, 0.1)
    s = b.snapshot()
    return {
        "烧法": mode, "参数": p, "目标token": target_tokens,
        "耗时秒": round(el, 1),
        "总token": s["p"] + s["c"], "输入token": s["p"], "输出token": s["c"],
        "调用次数": s["calls"], "限流次数": s["rate_limits"], "失败次数": s["fails"],
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    mode = sys.argv[1]
    target = int(float(sys.argv[2]))
    over = {}
    if len(sys.argv) > 3:                 # 第三个可选参数：填充字符数
        over["填充字符数"] = int(float(sys.argv[3]))
    if mode not in MODE_PARAMS:
        print("烧法只能是：%s" % " / ".join(MODE_PARAMS))
        return 1

    print("=" * 60)
    print("积分换算实测：%s，目标 %s token" % (mode, f"{target:,}"))
    print("=" * 60)

    print("\n[1/3] 烧之前，读一次积分……")
    before = points()
    print("  本周余额 %s ｜ 5h窗口可用 %s"
          % (before.get("本周余额"), before.get("窗口可用")))

    print("\n[2/3] 开始烧……")
    stat = burn(mode, target, over=over)
    print("  烧完：%s token（输入 %s + 输出 %s），调用 %d 次，限流 %d 次，耗时 %.0f 秒"
          % (f"{stat['总token']:,}", f"{stat['输入token']:,}",
             f"{stat['输出token']:,}", stat["调用次数"], stat["限流次数"], stat["耗时秒"]))

    print("\n[3/3] 等后台记账，再读两次积分……")
    time.sleep(15)
    mid = points()
    print("  第1次读数：窗口可用 %s（比之前少 %s）"
          % (mid.get("窗口可用"),
             round((before.get("窗口可用") or 0) - (mid.get("窗口可用") or 0), 4)))
    time.sleep(20)
    after = points()
    print("  第2次读数：窗口可用 %s（比之前少 %s）"
          % (after.get("窗口可用"),
             round((before.get("窗口可用") or 0) - (after.get("窗口可用") or 0), 4)))

    used = (before.get("窗口可用") or 0) - (after.get("窗口可用") or 0)
    used_bal = (before.get("本周余额") or 0) - (after.get("本周余额") or 0)

    rec = {
        "时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "烧法": mode,
        "参数": stat["参数"],
        "总token": stat["总token"],
        "输入token": stat["输入token"],
        "输出token": stat["输出token"],
        "耗时秒": stat["耗时秒"],
        "调用次数": stat["调用次数"],
        "限流次数": stat["限流次数"],
        "烧前_窗口可用": before.get("窗口可用"),
        "烧后_窗口可用": after.get("窗口可用"),
        "烧前_本周余额": before.get("本周余额"),
        "烧后_本周余额": after.get("本周余额"),
        "花掉积分_按窗口": round(used, 4),
        "花掉积分_按余额": round(used_bal, 4),
        "每积分多少token_按窗口": round(stat["总token"] / used, 1) if used > 0 else None,
        "每积分多少token_按余额": round(stat["总token"] / used_bal, 1) if used_bal > 0 else None,
        "输入型单向折算": round(stat["总token"] / used, 1) if used > 0 else None,
    }

    all_recs = []
    if os.path.exists(OUT):
        try:
            all_recs = load_json(OUT)
        except Exception:
            all_recs = []
    all_recs.append(rec)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(all_recs, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("结论")
    print("  烧掉 %s token，用掉 %s 积分" % (f"{stat['总token']:,}", used))
    if used > 0:
        print("  → 1 积分 ≈ %.0f token" % (stat["总token"] / used))
    print("  结果已写入：%s" % OUT)
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
