#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wipo_weekly_fetch_cdp.py — 通过本机 Chrome（CDP 远程调试）抓取 WIPO PATENTSCOPE
指定周四公开日中 IPC 分类为 C07 的 PCT 新公开清单。

为什么有这个脚本（2026-10-01）：
    PATENTSCOPE 升级反爬后，Python urllib/curl 的 TLS 指纹被封（全站 403），
    result.jsf?query= 深链失效且结果页带图片验证码；只有真实 Chrome 能正常访问。
    本脚本驱动无头 Chrome 完成：高级检索表单提交 → 图片验证码（Claude 看图接力）
    → 逐页翻页 → 解析行数据，输出与 wipo_weekly_fetch.py 相同的文件。

用法：
    python wipo_weekly_fetch_cdp.py                      # 最近一个周四
    python wipo_weekly_fetch_cdp.py --date 2026-10-01    # 指定公开日（周四）

验证码接力：脚本遇到验证码时把题目与 6 张图存到 <输出目录>/_captcha/，
    然后每 5 秒轮询该目录下 answer.txt（最长 15 分钟）。Claude 看图后执行：
        echo N > wipo_reports/wipo_<日期>/_captcha/answer.txt   # N=1..6
    脚本自动继续；答错会刷新图片继续等。

依赖：websocket-client（pip install websocket-client）+ 本机 Chrome。
输出：publications.json / publications.csv / summary.txt（同 legacy 脚本）。
"""

import argparse
import base64
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

import websocket  # websocket-client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wipo_weekly_fetch import (  # noqa: E402
    QUERY_TMPL, ipc_group, most_recent_thursday, parse_rows)

CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
BASE = "https://patentscope.wipo.int"
PAGE_SIZE = 10
CDP_PORT = 9223
CAPTCHA_DIR = "_captcha"
CAPTCHA_WAIT_S = 15 * 60


def log(msg):
    print(msg, flush=True)


# ---------------- CDP 基础 ----------------

class ChromeCDP:
    def __init__(self, port=CDP_PORT):
        self.port = port
        self.profile = tempfile.mkdtemp(prefix="wipo_chrome_")
        self.proc = subprocess.Popen(
            [CHROME, "--headless=new", f"--remote-debugging-port={port}",
             "--remote-allow-origins=*",
             f"--user-data-dir={self.profile}",
             "--disable-blink-features=AutomationControlled",
             f"--user-agent={UA}", "--no-first-run", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.ws = None
        self._id = 0
        self._connect()

    def _connect(self):
        url = None
        for _ in range(60):
            try:
                data = json.load(urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json/list", timeout=2))
                pages = [t for t in data if t.get("type") == "page"]
                if pages:
                    url = pages[0]["webSocketDebuggerUrl"]
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        if not url:
            raise RuntimeError("无法连接 Chrome 远程调试端口")
        self.ws = websocket.create_connection(url, timeout=120,
                                              suppress_origin=True)
        self.cmd("Page.enable")
        self.cmd("Runtime.enable")

    def cmd(self, method, params=None, timeout=120):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method,
                                 "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.ws.settimeout(max(1, deadline - time.time()))
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method} 错误：{msg['error']}")
                return msg.get("result", {})
        raise TimeoutError(f"CDP {method} 超时")

    def js(self, expr, timeout=120):
        """执行 JS，返回 returnByValue 的值。"""
        r = self.cmd("Runtime.evaluate", {
            "expression": expr, "returnByValue": True,
            "awaitPromise": True}, timeout=timeout)
        if r.get("exceptionDetails"):
            raise RuntimeError(f"JS 执行异常：{r['exceptionDetails']}")
        return r.get("result", {}).get("value")

    def navigate(self, url, timeout=180):
        self.cmd("Page.navigate", {"url": url})
        host = urllib.parse.urlparse(url).netloc
        self.wait_js(
            f"location.href.includes('{host}') && "
            "document.readyState === 'complete'",
            timeout=timeout, desc=f"导航到 {url}")

    def wait_js(self, expr, timeout=120, interval=1.0, desc=""):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.js(f"!!({expr})", timeout=30):
                    return True
            except Exception:  # noqa: BLE001
                pass  # 导航期间 evaluate 可能失败
            time.sleep(interval)
        raise TimeoutError(f"等待超时：{desc or expr}")

    def close(self):
        try:
            self.proc.terminate()
        except Exception:  # noqa: BLE001
            pass


STATE_JS = r"""
(function(){
  var rc = document.querySelector('.results-count');
  var cap = document.getElementById('psCaptchaPanel');
  var cur = document.querySelector('.ui-paginator-current');
  var body = document.body ? document.body.innerText : '';
  return JSON.stringify({
    url: location.href,
    results: rc ? rc.textContent.trim() : null,
    captcha: !!cap,
    noresult: /No result/i.test(body),
    current: cur ? cur.textContent.trim() : null
  });
})()
"""

CAPTCHA_JS = r"""
(function(){
  var q = document.querySelector('#psCaptchaPanel .b-view-panel__section');
  var imgs = Array.from(document.querySelectorAll('#psCaptchaPanel img[id^=image]'));
  return JSON.stringify({
    question: q ? q.textContent.trim() : '',
    images: imgs.map(function(i){ return {id: i.id, src: i.src}; })
  });
})()
"""

GOTO_JS = r"""
(function(n){
  var input = document.querySelector('.ps-paginator-modal--input');
  if(!input) return 'no-input';
  var form = input.closest('form');
  var btn = form.querySelector('.ps-paginator-modal--button');
  input.value = String(n);
  btn.removeAttribute('disabled');
  btn.click();
  return 'ok';
})(%d)
"""

ROWS_JS = r"""
Array.from(document.querySelectorAll('tr[data-ri]'))
  .map(function(t){ return t.outerHTML; }).join('')
"""


def state(cdp):
    return json.loads(cdp.js(STATE_JS))


def solve_captcha(cdp, capdir):
    """验证码接力：存图 → 等 answer.txt → 点击 → 必要时循环。"""
    os.makedirs(capdir, exist_ok=True)
    answer_file = os.path.join(capdir, "answer.txt")
    if os.path.exists(answer_file):
        os.remove(answer_file)
    round_no = 0
    while True:
        round_no += 1
        data = json.loads(cdp.js(CAPTCHA_JS))
        n_saved = 0
        for im in data["images"]:
            m = re.match(r"data:image/png;base64,(.+)", im["src"])
            if not m:
                continue
            idx = re.sub(r"\D", "", im["id"])
            with open(os.path.join(capdir, f"img{idx}.png"), "wb") as f:
                f.write(base64.b64decode(m.group(1)))
            n_saved += 1
        with open(os.path.join(capdir, "question.txt"), "w", encoding="utf-8") as f:
            f.write(data["question"] + "\n")
        log("")
        log("=" * 60)
        log(f"出现图片验证码（第 {round_no} 轮）：{data['question']}")
        log(f"  {n_saved} 张图片已存至 {capdir}")
        log(f"  请查看图片后执行： echo N > {os.path.join(capdir, 'answer.txt')}")
        log("=" * 60)
        # 等答案
        deadline = time.time() + CAPTCHA_WAIT_S
        answer = None
        while time.time() < deadline:
            if os.path.exists(answer_file):
                try:
                    answer = int(open(answer_file).read().strip())
                    break
                except ValueError:
                    time.sleep(2)
                    continue
            time.sleep(5)
        if answer is None:
            raise TimeoutError("等待验证码答案超时（15 分钟）")
        os.remove(answer_file)
        log(f"提交验证码答案：第 {answer} 张图…")
        cdp.js(f"document.getElementById('click{answer}').click()")
        time.sleep(5)
        # 等状态变化：验证码消失或刷新
        try:
            cdp.wait_js(
                f"!document.getElementById('psCaptchaPanel') || "
                f"document.querySelector('.results-count')",
                timeout=60, desc="验证码提交后页面更新")
        except TimeoutError:
            pass
        st = state(cdp)
        if not st["captcha"]:
            log("验证码通过！")
            return st
        log("验证码未通过/进入新一轮，重新取图…")
        time.sleep(3)


def wait_results(cdp, timeout=240):
    """等检索结果或验证码出现。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            st = state(cdp)
        except Exception:  # noqa: BLE001
            time.sleep(2)
            continue
        if st["results"] or st["captcha"] or st["noresult"]:
            return st
        time.sleep(2)
    raise TimeoutError("等待检索结果超时")


def goto_page_and_get_rows(cdp, page, seen_ids, retries=4):
    """翻到指定页并返回该行 HTML；带整页重复检测。"""
    expect_start = (page - 1) * PAGE_SIZE + 1
    for attempt in range(retries):
        r = cdp.js(GOTO_JS % page)
        if r != "ok":
            raise RuntimeError("未找到翻页控件")
        try:
            cdp.wait_js(
                f"(document.querySelector('.ui-paginator-current')||{{}})"
                f".textContent.includes('Results {expect_start} -')",
                timeout=90, desc=f"第 {page} 页加载")
        except TimeoutError:
            log(f"  第 {page} 页加载超时，重试 ({attempt + 1}/{retries})…")
            time.sleep(5)
            continue
        rows_html = cdp.js(ROWS_JS)
        ids = set(re.findall(r'data-rk="([^"]+)"', rows_html))
        if not ids or not ids.issubset(seen_ids):
            return rows_html
        log(f"  第 {page} 页整页重复，重试 ({attempt + 1}/{retries})…")
        time.sleep(5)
    raise RuntimeError(f"第 {page} 页连续返回重复/超时")


def main():
    ap = argparse.ArgumentParser(description="经 Chrome CDP 抓取 WIPO 每周四 C07 类 PCT 新公开")
    ap.add_argument("--date", help="公开日（周四）YYYY-MM-DD；默认最近周四")
    ap.add_argument("--out", default="wipo_reports", help="输出根目录")
    ap.add_argument("--delay", type=float, default=1.5, help="翻页间隔秒数")
    args = ap.parse_args()

    pub_day = (datetime.strptime(args.date, "%Y-%m-%d").date() if args.date
               else most_recent_thursday())
    query = QUERY_TMPL.format(day=pub_day.day, month=pub_day.month, year=pub_day.year)
    out_dir = f"{args.out}/wipo_{pub_day.isoformat()}"
    capdir = os.path.join(out_dir, CAPTCHA_DIR)
    os.makedirs(out_dir, exist_ok=True)
    json_path = f"{out_dir}/publications.json"
    log(f"目标公开日：{pub_day}（周四）")
    log(f"检索式：{query}")

    cdp = ChromeCDP()
    try:
        log("启动 Chrome，打开高级检索页…")
        cdp.navigate(f"{BASE}/search/en/advancedSearch.jsf")
        st = wait_results(cdp, timeout=30) if False else None  # 占位，直接提交检索
        # 提交检索
        log("提交检索…")
        cdp.wait_js(
            "document.querySelector("
            "'textarea[id=\"advancedSearchForm:advancedSearchInput:input\"]')",
            timeout=120, desc="检索输入框出现")
        cdp.js(
            "var ta = document.querySelector("
            "'textarea[id=\"advancedSearchForm:advancedSearchInput:input\"]');"
            f"ta.value = {json.dumps(query)}; doSearch(); 'submitted'")
        st = wait_results(cdp, timeout=300)
        if st["captcha"]:
            st = solve_captcha(cdp, capdir)
        if st["noresult"]:
            log("该公开日无 C07 类新公开（或公开日顺延）。")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({"publication_day": pub_day.isoformat(), "query": query,
                           "total": 0, "records": []}, f, ensure_ascii=False, indent=2)
            return
        m = re.search(r"([\d,]+)\s+results", st["results"])
        total = int(m.group(1).replace(",", ""))
        log(f"命中总数：{total}")

        # 第 1 页
        rows_html = cdp.js(ROWS_JS)
        records = parse_rows(rows_html)
        seen_ids = {r["doc_id"] for r in records}
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        bad_pages = []
        log(f"共 {pages} 页，开始翻页（约 {pages * (args.delay + 2) / 60:.0f} 分钟）…")
        for p in range(2, pages + 1):
            try:
                rows_html = goto_page_and_get_rows(cdp, p, seen_ids)
            except RuntimeError as e:
                log(f"  {e}；该页缺失，稍后需补抓")
                bad_pages.append(p)
                continue
            rows = parse_rows(rows_html)
            records.extend(rows)
            seen_ids.update(r["doc_id"] for r in rows)
            time.sleep(args.delay)
            if p % 10 == 0 or p == pages:
                log(f"  进度：第 {p}/{pages} 页，累计 {len(records)} 条")
                _write_json(json_path, pub_day, query, total, records, partial=True)
            # 翻页中途也可能弹验证码
            if state(cdp)["captcha"]:
                solve_captcha(cdp, capdir)

        # 去重
        seen, uniq = set(), []
        for r in records:
            if r["doc_id"] not in seen:
                seen.add(r["doc_id"])
                uniq.append(r)
        records = uniq
        log(f"抓取完成，去重后 {len(records)} 条（官方计数 {total}）")
        if len(records) < total or bad_pages:
            log(f"⚠️ 缺 {total - len(records)} 条；失败页：{bad_pages or '无'}")

        _write_json(json_path, pub_day, query, total, records)

        with open(f"{out_dir}/publications.csv", "w", encoding="utf-8-sig",
                  newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "publication_number", "title", "applicant", "inventor",
                "ipc_main", "ipc_all", "application_number",
                "publication_date", "doc_id", "link"])
            w.writeheader()
            w.writerows(records)

        from collections import Counter
        dist = Counter(ipc_group(r.get("ipc_main", "")) for r in records)
        with open(f"{out_dir}/summary.txt", "w", encoding="utf-8") as f:
            f.write("WIPO PCT 新公开（C07）抓取摘要（Chrome CDP 通道）\n")
            f.write(f"公开日：{pub_day}（周四）\n检索式：{query}\n")
            f.write(f"官方计数：{total}；实抓：{len(records)}\n")
            if bad_pages:
                f.write(f"⚠️ 失败页：{bad_pages}\n")
            f.write("\nIPC 大组分布：\n")
            for g, n in dist.most_common():
                f.write(f"  {g}: {n}\n")
        log(f"输出目录：{out_dir}")
        log("IPC 大组分布：" + ", ".join(f"{g}:{n}" for g, n in dist.most_common(10)))
        # 清理验证码目录
        if os.path.isdir(capdir) and not bad_pages:
            for fn in os.listdir(capdir):
                os.remove(os.path.join(capdir, fn))
            os.rmdir(capdir)
    finally:
        cdp.close()


def _write_json(path, pub_day, query, total, records, partial=False):
    payload = {"publication_day": pub_day.isoformat(), "query": query,
               "total_official": total, "total_fetched": len(records),
               "records": records}
    if partial:
        payload["partial"] = True
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
