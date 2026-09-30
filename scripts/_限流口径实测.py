# -*- coding: utf-8 -*-
"""
限流口径实测
================================================================
目的：搞清楚三件事，这决定了哪种烧法最快最稳
  1. 输出 token 算不算进限流配额？（关键：如果不算，长输出式就是王者）
  2. 输入 token 每分钟的上限大概是多少？
  3. 被限流之后，多久能恢复？
  4. 单次填充最大能塞多大？

结果会边跑边写进 _限流实测结果.json，中途挂了也不丢数据。
================================================================
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY = os.environ.get("SENSENOVA_API_KEY", "sk-YOUR_API_KEY_HERE")
BASE = "https://token.sensenova.cn/v1"
MODEL = "sensenova-6.8-flash-lite"
OUT_JSON = os.path.join(BASE_DIR, "_限流实测结果.json")

FILL_BLOCK = (
    "本段文字仅用于填充上下文长度，不具备实际含义。在实际业务场景中，"
    "同类文本通常出现在产品说明书、服务条款、行业规范、操作手册或历史档案当中。"
    "这些材料的特点是篇幅长、信息密度低、结构重复度高，适合用来测试模型的长文本处理能力。"
    "需要注意的是，长上下文任务的主要成本并不产生于模型的思考过程，而在于上下文的载入与重复传递。"
    "当输入长度达到一定规模后，单次请求的输入部分就会成为账单的主要构成。"
    "此外，长文本的切分方式、检索策略与缓存命中率，都会显著影响实际开销。"
    "在实际测试中应当关注单位有效输出的成本，而不是单纯比较每次调用的绝对消耗。"
)

results = {"开始时间": time.strftime("%Y-%m-%d %H:%M:%S"), "步骤": []}


def save():
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def call(messages, max_tokens, tag=""):
    """发一次请求，返回字典记录。"""
    url = BASE.rstrip("/") + "/chat/completions"
    payload = {"model": MODEL, "messages": messages, "max_tokens": max_tokens,
               "temperature": 0.9}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY},
        method="POST")
    rec = {"标签": tag, "时刻": time.strftime("%H:%M:%S"), "最大输出设置": max_tokens,
           "请求字符数": sum(len(m["content"]) for m in messages)}
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        u = body.get("usage") or {}
        rec["状态"] = "成功"
        rec["输入token"] = int(u.get("prompt_tokens") or 0)
        rec["输出token"] = int(u.get("completion_tokens") or 0)
        rec["耗时秒"] = round(time.time() - t0, 2)
        print("  [OK ] %-22s 输入%-8s 输出%-7s 耗时%6.2fs"
              % (tag, f"{rec['输入token']:,}", f"{rec['输出token']:,}", rec["耗时秒"]))
    except urllib.error.HTTPError as e:
        rec["状态"] = "HTTP%d" % e.code
        rec["耗时秒"] = round(time.time() - t0, 2)
        try:
            rec["错误详情"] = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            rec["错误详情"] = ""
        print("  [%s] %-22s 耗时%6.2fs  %s"
              % (rec["状态"], tag, rec["耗时秒"], rec.get("错误详情", "")[:90]))
    except Exception as e:
        rec["状态"] = "异常"
        rec["错误详情"] = str(e)[:200]
        rec["耗时秒"] = round(time.time() - t0, 2)
        print("  [异常] %-22s %s" % (tag, str(e)[:90]))
    return rec


def step1_输出是否限流():
    """短输入 + 大输出，连打 5 次。若全成功，说明输出 token 不占限流配额。"""
    print("\n=== 第1步：探测输出 token 是否计入限流（短输入+8000输出，连打5次）===")
    step = {"步骤": "1_输出是否限流", "记录": []}
    results["步骤"].append(step)          # 只挂一次，后面原地改，避免重复条目
    for i in range(5):
        r = call([{"role": "user", "content": "请详细说明一下日常生活中的观察，不少于三千字。"}],
                 max_tokens=8000, tag="输出探测#%d" % (i + 1))
        step["记录"].append(r)
        save()
        if i < 4:
            time.sleep(2)
    ok = sum(1 for r in step["记录"] if r["状态"] == "成功")
    out = sum(r.get("输出token", 0) for r in step["记录"])
    inp = sum(r.get("输入token", 0) for r in step["记录"])
    step["小结"] = "5次中成功%d次，共烧 %s token（输入%s + 输出%s）" % (ok, f"{inp+out:,}", f"{inp:,}", f"{out:,}")
    print("  → " + step["小结"])
    save()
    return step


def step2_输入上限():
    """6万字符填充，连打 4 次，找出第几次开始被限流。"""
    print("\n=== 第2步：探测输入 token 限流上限（6万字符填充，连打4次，间隔3秒）===")
    reps = max(int(60000 / len(FILL_BLOCK)), 1)
    text = FILL_BLOCK * reps
    step = {"步骤": "2_输入限流上限", "记录": []}
    results["步骤"].append(step)
    for i in range(4):
        r = call([{"role": "user", "content": "请通读后回答：这段文字出现了多少次“的”字？只回答数字。\n\n【参考资料】\n" + text}],
                 max_tokens=64, tag="填充探测#%d" % (i + 1))
        step["记录"].append(r)
        save()
        if i < 3:
            time.sleep(3)
    ok = sum(1 for r in step["记录"] if r["状态"] == "成功")
    step["小结"] = "4次中成功%d次" % ok
    print("  → " + step["小结"])
    save()
    return step


def step3_恢复时间(被限流了=False):
    """被限流后每 5 秒试一次小请求，测多久恢复。"""
    print("\n=== 第3步：探测限流恢复时间（每5秒试一次小请求）===")
    step = {"步骤": "3_限流恢复", "记录": []}
    results["步骤"].append(step)
    t0 = time.time()
    for i in range(12):          # 最多等 60 秒
        r = call([{"role": "user", "content": "只回答两个字：收到"}], max_tokens=16,
                 tag="恢复探测+%ds" % int(time.time() - t0))
        step["记录"].append(r)
        save()
        if r["状态"] == "成功":
            step["小结"] = "等待 %d 秒后恢复正常" % int(time.time() - t0)
            print("  → " + step["小结"])
            break
        time.sleep(5)
    else:
        step["小结"] = "60 秒内仍未恢复"
    save()
    return step


def step4_单次上限():
    """测试单次能塞多大的填充文本（20万 / 40万字符）。"""
    print("\n=== 第4步：探测单次填充上限（20万、40万字符各试一次）===")
    step = {"步骤": "4_单次填充上限", "记录": []}
    results["步骤"].append(step)
    for chars in (200_000, 400_000):
        reps = max(int(chars / len(FILL_BLOCK)), 1)
        text = FILL_BLOCK * reps
        r = call([{"role": "user", "content": "请通读后回答：这段文字出现了多少次“的”字？只回答数字。\n\n【参考资料】\n" + text}],
                 max_tokens=64, tag="填充%s万字符" % (chars // 10000))
        step["记录"].append(r)
        save()
        time.sleep(5)
    step["小结"] = "；".join("%s → %s" % (r["标签"], r["状态"]) for r in step["记录"])
    print("  → " + step["小结"])
    save()
    return step


def main():
    print("=" * 66)
    print("限流口径实测开始")
    print("=" * 66)
    t0 = time.time()
    s1 = step1_输出是否限流()
    time.sleep(5)
    s2 = step2_输入上限()
    time.sleep(5)
    s3 = step3_恢复时间()
    time.sleep(10)
    step4_单次上限()

    results["总耗时秒"] = round(time.time() - t0, 1)
    save()
    print("\n" + "=" * 66)
    print("实测结束，总耗时 %.1f 秒，结果已写入 _限流实测结果.json" % results["总耗时秒"])
    print("=" * 66)


if __name__ == "__main__":
    main()
