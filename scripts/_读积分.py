# -*- coding: utf-8 -*-
"""
读商汤后台的积分余额
================================================================
从控制台页面精确读两个积分池的数字（精确到小数点后 4 位）：

  · Flash-Lite 专属积分池 —— 本周余额、5h 窗口可用/上限
  · 通用积分池           —— 本周余额、5h 窗口可用/上限

用法：
    python _读积分.py            读一次并打印
    python _读积分.py --json     只输出一行 JSON，方便别的脚本调用

依赖：Edge 已经用 9222 调试口开着，并且已登录
================================================================
"""
import json
import os
import re
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CDP = "http://127.0.0.1:9222"
CONSOLE = "https://platform.sensenova.cn/console"
HERE = os.path.dirname(os.path.abspath(__file__))


def cdp_alive():
    try:
        with urllib.request.urlopen(CDP + "/json/version", timeout=3) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def num(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def parse(text):
    """从页面文字里把两个积分池的数字抠出来"""
    out = {}

    def grab(title, key):
        i = text.find(title)
        if i < 0:
            return
        seg = text[i:i + 700]
        sec = {}
        # 本周余额：标题后面紧跟一个大数字
        m = re.search(r"余额\s*\n?\s*([\d,]+\.\d+|[\d,]+)", seg)
        if m:
            sec["本周余额"] = num(m.group(1))
        # 5h 窗口可用 40,327.9512 / 60,000
        m = re.search(r"5h\s*窗口可用[\s\S]{0,120}?([\d,]+\.\d+|[\d,]+)\s*/\s*([\d,]+\.?\d*)", seg)
        if m:
            sec["窗口可用"] = num(m.group(1))
            sec["窗口上限"] = num(m.group(2))
        # 周额度
        m = re.search(r"周额度\s*\n?\s*([\d,]+\.?\d*)", seg)
        if m:
            sec["周额度"] = num(m.group(1))
        out[key] = sec

    grab("Flash-Lite专属积分池", "flash_lite")
    grab("通用积分池", "general")
    return out


def read_once(reload=True):
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    try:
        b = pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0] if b.contexts else b.new_context()
        pages = [p for p in ctx.pages if p.url and not p.url.startswith("devtools")]
        pg = pages[-1] if pages else ctx.new_page()
        if "platform.sensenova.cn" not in (pg.url or ""):
            pg.goto(CONSOLE, wait_until="domcontentloaded", timeout=60000)
            time.sleep(4)
        if reload:
            pg.reload(wait_until="domcontentloaded", timeout=60000)
            time.sleep(6)
        txt = pg.inner_text("body")
        data = parse(txt)
        data["_页面"] = pg.url
        data["_读取时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return data, txt
    finally:
        pw.stop()


def main():
    if not cdp_alive():
        print("调试口不通：先把 Edge 用 9222 调起来")
        return 2
    data, txt = read_once(reload=("--noreload" not in sys.argv))
    if "--json" in sys.argv:
        print(json.dumps(data, ensure_ascii=False))
        return 0

    if not data.get("flash_lite"):
        print("没在页面上找到「Flash-Lite专属积分池」，可能没登录或页面结构变了。")
        print("页面文字片段：%s" % txt[:400].replace("\n", " | "))
        out = os.path.join(HERE, "_积分页面原文.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(txt)
        print("页面原文已存到：%s" % out)
        return 1

    fl = data["flash_lite"]
    gn = data.get("general") or {}
    print("读取时间：%s" % data["_读取时间"])
    print("=" * 56)
    print("Flash-Lite 专属积分池")
    print("  本周余额    ：%s" % fl.get("本周余额"))
    print("  5h窗口可用  ：%s / %s" % (fl.get("窗口可用"), fl.get("窗口上限")))
    print("  周额度      ：%s" % fl.get("周额度"))
    print("-" * 56)
    print("通用积分池")
    print("  本周余额    ：%s" % gn.get("本周余额"))
    print("  5h窗口可用  ：%s / %s" % (gn.get("窗口可用"), gn.get("窗口上限")))
    print("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
