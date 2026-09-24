#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_abstracts.py — 用本机 Chrome 无头模式抓取 PATENTSCOPE 详情页摘要，
写入 <目录>/abstracts.json 缓存（doc_id -> 英文摘要文本）。

背景：PATENTSCOPE 详情页 JS 动态渲染，requests/静态抓取只能拿到空壳或 403；
已验证 chrome --headless=new + 反检测参数可拿到含摘要的完整 DOM。

用法：
    python fetch_abstracts.py wipo_reports/wipo_2026-09-24
    python fetch_abstracts.py <目录> --category 化学药小分子 --workers 2
    python fetch_abstracts.py <目录> --force          # 忽略缓存重抓
    python fetch_abstracts.py <目录> --doc WO2026194970   # 只抓单件（调试用）

默认范围：化学药小分子 且 标题未识别到靶点 的条目（analyze_weekly.py 已运行）。
抓完后需重新运行 analyze_weekly.py，摘要级靶点才会进入 analysis.json/listing.md。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import io
import tempfile
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

# 摘要容器：<div class="patent-abstract">...<b ...>(EN)</b> <span ...>TEXT</span>
_ABS_BLOCK_RE = re.compile(r'<div class="patent-abstract">(.*?)</div>\s*</span>',
                           re.S)
_ABS_LANG_RE = re.compile(
    r'<b class="notranslate">\(([A-Z]{2})\)</b>\s*'
    r'<span class="[^"]*">(.*?)</span>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def parse_abstract(dom):
    """从详情页 DOM 提取摘要，优先英文，其次任意语种。返回 (text, lang) 或 ('', '')。"""
    m = _ABS_BLOCK_RE.search(dom)
    if not m:
        return "", ""
    block = m.group(1)
    candidates = []
    for lang, text in _ABS_LANG_RE.findall(block):
        text = _TAG_RE.sub("", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 30:
            candidates.append((lang, text))
    if not candidates:
        return "", ""
    for lang, text in candidates:
        if lang == "EN":
            return text, lang
    return candidates[0][1], candidates[0][0]


def fetch_one(doc_id, link, timeout=90):
    """抓单件摘要。返回 (abstract, lang, error)。"""
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
        out = tf.name
    try:
        cmd = [CHROME, "--headless=new",
               "--disable-blink-features=AutomationControlled",
               f"--user-agent={UA}",
               "--virtual-time-budget=25000",
               "--dump-dom", link]
        with open(out, "w", encoding="utf-8", errors="replace") as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.DEVNULL,
                           timeout=timeout)
        dom = open(out, encoding="utf-8", errors="replace").read()
        if len(dom) < 20000:
            return "", "", f"DOM 过小({len(dom)}B)，可能被拦截"
        ab, lang = parse_abstract(dom)
        if not ab:
            return "", "", "DOM 中未找到摘要段"
        return ab, lang, ""
    except subprocess.TimeoutExpired:
        return "", "", "超时"
    except Exception as e:  # noqa: BLE001
        return "", "", str(e)
    finally:
        try:
            os.unlink(out)
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--category", default="化学药小分子",
                    help="抓取的药物类别（默认仅小分子）")
    ap.add_argument("--all-titles", action="store_true",
                    help="类别内全部条目（默认仅标题未命中靶点的）")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--doc", help="只抓指定 doc_id（调试用）")
    args = ap.parse_args()

    analysis_path = f"{args.folder}/analysis.json"
    if not os.path.exists(analysis_path):
        sys.exit("未找到 analysis.json，请先运行 analyze_weekly.py")
    analysis = json.load(open(analysis_path, encoding="utf-8"))
    recs = analysis["records"]

    cache_path = f"{args.folder}/abstracts.json"
    cache = {} if args.force else (
        json.load(open(cache_path, encoding="utf-8"))
        if os.path.exists(cache_path) else {})

    if args.doc:
        todo = [r for r in recs if r["doc_id"] == args.doc]
    else:
        todo = [r for r in recs
                if r["category"] == args.category
                and (args.all_titles or not r["targets"])
                and r["doc_id"] not in cache]
    print(f"待抓 {len(todo)} 件（缓存已有 {len(cache)} 件）")

    ok, fail = 0, []
    def job(r):
        # 失败重试一次
        ab, lang, err = fetch_one(r["doc_id"], r["link"])
        if err:
            time.sleep(3 + random.random() * 2)
            ab, lang, err = fetch_one(r["doc_id"], r["link"])
        return r, ab, lang, err

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(job, r): r for r in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            r, ab, lang, err = fut.result()
            if ab:
                cache[r["doc_id"]] = ab
                ok += 1
                mark = ""
            else:
                fail.append((r["publication_number"], err))
                mark = f"  ✗ {err}"
            if i % 10 == 0 or i == len(todo) or mark:
                print(f"  [{i}/{len(todo)}] {r['publication_number']}{mark}")
            # 每 10 件落盘一次，中断不丢
            if i % 10 == 0:
                json.dump(cache, open(cache_path, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
            time.sleep(0.8 + random.random() * 0.8)

    json.dump(cache, open(cache_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"完成：成功 {ok}，失败 {len(fail)}，缓存累计 {len(cache)} 件")
    if fail:
        print("失败清单：")
        for pn, err in fail:
            print(f"  {pn}: {err}")
    print("下一步：重新运行 analyze_weekly.py 使摘要级靶点生效")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    main()
