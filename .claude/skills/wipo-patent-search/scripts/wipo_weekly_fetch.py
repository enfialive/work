#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wipo_weekly_fetch.py — 抓取 WIPO PATENTSCOPE 某周四（PCT 每周公开日）新公开的
IPC 分类为 A61 / C07（医药、化学领域）的 PCT 申请清单。

用法：
    python wipo_weekly_fetch.py                      # 默认取“最近一个周四”
    python wipo_weekly_fetch.py --date 2026-08-27    # 指定公开日（周四）
    python wipo_weekly_fetch.py --out ./reports      # 指定输出目录
    python wipo_weekly_fetch.py --delay 2.0          # 翻页间隔秒数（默认 1.5）

输出（写入 <out>/wipo_YYYY-MM-DD/）：
    publications.json   全量结构化数据
    publications.csv    便于 Excel 打开
    summary.txt         抓取摘要（总数、按 IPC 大组分布）

依赖：仅标准库。平台：Windows / Python 3.12。
"""

import argparse
import csv
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import date, datetime, timedelta

BASE = "https://patentscope.wipo.int"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
QUERY_TMPL = "(IC:A61 OR IC:C07) AND DP:{day:02d}.{month:02d}.{year}"
PAGE_SIZE = 10  # PATENTSCOPE 结果页固定每页 10 条


def log(msg):
    print(msg, flush=True)


def strip_tags(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def most_recent_thursday(today=None):
    """返回最近一个周四（含今天，若今天即周四）。"""
    today = today or date.today()
    delta = (today.weekday() - 3) % 7  # 3 = 周四
    return today - timedelta(days=delta)


class PatentscopeSession:
    def __init__(self, delay=1.5, retries=3):
        self.delay = delay
        self.retries = retries
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj))
        self.jsess = None
        self.viewstate = None
        self.page_form = None  # “Go to page”翻页表单 id

    def _get(self, url):
        last = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(url, headers=UA)
                return self.opener.open(req, timeout=90).read().decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                last = e
                wait = self.delay * (attempt + 2)
                log(f"  [重试 {attempt + 1}/{self.retries}] {e}；{wait:.0f}s 后重试")
                time.sleep(wait)
        raise RuntimeError(f"请求失败：{url}\n原因：{last}")

    def _post_ajax_goto(self, page):
        """PrimeFaces AJAX：跳转到指定页。返回重定向后的页面 HTML。"""
        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": self.page_form + ":button",
            "javax.faces.partial.execute": self.page_form,
            "javax.faces.partial.render": "results-container @(.js-ps-global-messages)",
            self.page_form + ":button": self.page_form + ":button",
            self.page_form: self.page_form,
            self.page_form + ":input": str(page),
            "javax.faces.ViewState": self.viewstate,
        }
        url = f"{BASE}/search/en/result.jsf;{self.jsess}"
        last = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(
                    url, data=urllib.parse.urlencode(data).encode(),
                    headers={**UA, "Faces-Request": "partial/ajax",
                             "Content-Type": "application/x-www-form-urlencoded"})
                resp = self.opener.open(req, timeout=90).read().decode("utf-8", "replace")
                m = re.search(r'<redirect url="([^"]+)"', resp)
                if not m:
                    raise RuntimeError(f"AJAX 响应中无 redirect：{resp[:200]}")
                redir = urllib.parse.urljoin(BASE, m.group(1).replace("&amp;", "&"))
                return self._get(redir)
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(self.delay * (attempt + 2))
        raise RuntimeError(f"第 {page} 页获取失败：{last}")

    def init_search(self, query):
        """发起检索，返回 (总条数, 第一页 HTML)。"""
        url = (BASE + "/search/en/result.jsf?query=" + urllib.parse.quote(query)
               + "&office=&sortOption=Pub+Date+Desc&prevFilter=&maxRec=10")
        html = self._get(url)
        m = re.search(r'class="results-count">([\d,]+)\s+results', html)
        if not m:
            if "No result" in html or "no result" in html:
                return 0, html
            raise RuntimeError("未能从结果页解析总条数，页面结构可能已变化")
        total = int(m.group(1).replace(",", ""))
        if total > 0:
            self.jsess = re.search(r"result\.jsf;(jsessionid=[^?&\"]+)", html).group(1)
            self.viewstate = re.search(
                r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html).group(1)
            # 定位“Go to page”翻页表单（组件 id 每次会话随机）
            self.page_form = None
            for fid, body in re.findall(
                    r'<form id="(j_idt\d+:j_idt\d+)"[^>]*>(.*?)</form>', html, re.S):
                if "ps-paginator-modal--input" in body:
                    self.page_form = fid
                    break
            if not self.page_form and total > PAGE_SIZE:
                raise RuntimeError("未找到翻页表单，页面结构可能已变化")
        return total, html

    def fetch_page(self, page):
        """page 从 1 开始；第 1 页由 init_search 返回。"""
        html = self._post_ajax_goto(page)
        time.sleep(self.delay)
        return html


FIELD_RE = re.compile(
    r'ps-field--label[^>]*>\s*(.*?)\s*</span>\s*'
    r'<span[^>]*class="[^"]*ps-field--value[^"]*"[^>]*>(.*?)</span>', re.S)


def parse_rows(html):
    """解析结果列表页，返回记录列表。"""
    records = []
    for block in html.split("<tr data-ri=")[1:]:
        rec = {}
        m = re.search(r'data-rk="([^"]+)"', block)
        if not m:
            continue
        rec["doc_id"] = m.group(1)                       # 如 WO2026177342
        m = re.search(r'data-mt-ipc="([^"]*)"', block)
        rec["ipc_main"] = m.group(1).strip() if m else ""  # 如 A61K 47/00
        m = re.search(r'ps-patent-result--title--patent-number">([^<]+)<', block)
        rec["publication_number"] = m.group(1).strip() if m else ""  # WO/2026/177342
        m = re.search(r'needTranslation-title[^>]*>(.*?)</span>\s*</span>', block, re.S)
        rec["title"] = strip_tags(m.group(1)) if m else ""
        m = re.search(r'resultListTableColumnPubDate[^>]*>([^<]+)<', block)
        rec["publication_date"] = m.group(1).strip() if m else ""    # DD.MM.YYYY
        for label, value in FIELD_RE.findall(block):
            label = strip_tags(label).rstrip(".")
            value = strip_tags(value)
            if label == "Int.Class":
                rec["ipc_all"] = value
            elif label == "Appl.No":
                rec["application_number"] = value
            elif label == "Applicant":
                rec["applicant"] = value
            elif label == "Inventor":
                rec["inventor"] = value
        rec["link"] = f"{BASE}/search/en/detail.jsf?docId={rec['doc_id']}"
        records.append(rec)
    return records


def ipc_group(ipc):
    """取 IPC 大组前缀，如 'A61K 47/00' -> 'A61K'。"""
    m = re.match(r"([A-HY]\d{2}[A-Z])", ipc.strip())
    return m.group(1) if m else "其他"


def main():
    ap = argparse.ArgumentParser(description="抓取 WIPO 每周四新公开的 A61/C07 类 PCT 申请")
    ap.add_argument("--date", help="公开日（周四），格式 YYYY-MM-DD；默认取最近一个周四")
    ap.add_argument("--out", default="wipo_reports", help="输出根目录（默认 ./wipo_reports）")
    ap.add_argument("--delay", type=float, default=1.5, help="请求间隔秒数（默认 1.5）")
    args = ap.parse_args()

    if args.date:
        pub_day = datetime.strptime(args.date, "%Y-%m-%d").date()
        if pub_day.weekday() != 3:
            log(f"警告：{pub_day} 不是周四，PCT 一般在周四公开，请确认日期。")
    else:
        pub_day = most_recent_thursday()

    query = QUERY_TMPL.format(day=pub_day.day, month=pub_day.month, year=pub_day.year)
    log(f"目标公开日：{pub_day}（周四）")
    log(f"检索式：{query}")

    sess = PatentscopeSession(delay=args.delay)
    total, html = sess.init_search(query)
    log(f"命中总数：{total}")

    out_dir = f"{args.out}/wipo_{pub_day.isoformat()}"
    import os
    os.makedirs(out_dir, exist_ok=True)

    if total == 0:
        log("本周该公开日无 A61/C07 类新公开（或公开日遇节假日顺延，可换日期重试）。")
        with open(f"{out_dir}/publications.json", "w", encoding="utf-8") as f:
            json.dump({"publication_day": pub_day.isoformat(), "query": query,
                       "total": 0, "records": []}, f, ensure_ascii=False, indent=2)
        return

    records = parse_rows(html)
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    log(f"共 {pages} 页，开始翻页抓取（约 {pages * (args.delay + 1) / 60:.0f} 分钟）…")
    for p in range(2, pages + 1):
        try:
            html = sess.fetch_page(p)
        except RuntimeError as e:
            log(f"  {e}；重建会话后从第 {p} 页继续")
            sess = PatentscopeSession(delay=args.delay)
            sess.init_search(query)
            html = sess.fetch_page(p)
        rows = parse_rows(html)
        records.extend(rows)
        if p % 10 == 0 or p == pages:
            log(f"  进度：第 {p}/{pages} 页，累计 {len(records)} 条")

    # 去重（同一 docId 可能因翻页边界重复）
    seen, uniq = set(), []
    for r in records:
        if r["doc_id"] not in seen:
            seen.add(r["doc_id"])
            uniq.append(r)
    records = uniq
    log(f"抓取完成，去重后 {len(records)} 条（官方计数 {total}）")

    # 按 IPC 大组统计
    from collections import Counter
    dist = Counter(ipc_group(r.get("ipc_main", "")) for r in records)

    with open(f"{out_dir}/publications.json", "w", encoding="utf-8") as f:
        json.dump({"publication_day": pub_day.isoformat(), "query": query,
                   "total_official": total, "total_fetched": len(records),
                   "records": records}, f, ensure_ascii=False, indent=2)

    with open(f"{out_dir}/publications.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "publication_number", "title", "applicant", "inventor",
            "ipc_main", "ipc_all", "application_number",
            "publication_date", "doc_id", "link"])
        w.writeheader()
        w.writerows(records)

    with open(f"{out_dir}/summary.txt", "w", encoding="utf-8") as f:
        f.write(f"WIPO PCT 新公开（A61/C07）抓取摘要\n")
        f.write(f"公开日：{pub_day}（周四）\n检索式：{query}\n")
        f.write(f"官方计数：{total}；实抓：{len(records)}\n\nIPC 大组分布：\n")
        for g, n in dist.most_common():
            f.write(f"  {g}: {n}\n")

    log(f"输出目录：{out_dir}")
    log("IPC 大组分布：" + ", ".join(f"{g}:{n}" for g, n in dist.most_common(10)))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
