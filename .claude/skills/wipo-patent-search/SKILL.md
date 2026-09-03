---
name: wipo-patent-search
description: 每周五（或按需）抓取 WIPO PATENTSCOPE 本周四新公开的 PCT 国际申请中 IPC 分类为 A61/C07（医药、化学领域）的专利，输出结构化清单与分类统计周报。当用户提到"抓取本周 WIPO 新公开""WIPO 周报""本周 PCT 新公开 医药"等时触发。
---

# WIPO 每周新公开监控（A61 / C07 医药化学领域）

## 用途

WIPO 每周四公开本周的 PCT 国际申请。本 skill 抓取指定周四公开日中 IPC 分类号属于 **A61 或 C07**（含全部子类，如 A61K、A61P、C07D、C07K 等）的新公开，生成结构化数据与中文周报，供专利工作人员快速筛查本公司关注的内容。

## 抓取脚本

脚本位置：`scripts/wipo_weekly_fetch.py`（相对本 SKILL.md 所在目录），仅依赖 Python 标准库。

```bash
# 最常用：不带参数，自动取“最近一个周四”（周五运行即抓取前一天）
C:/Users/admin/AppData/Local/Programs/Python/Python312/python.exe \
  .claude/skills/wipo-patent-search/scripts/wipo_weekly_fetch.py

# 指定公开日（必须是周四，WIPO 遇节假日可能顺延，需人工确认）
... wipo_weekly_fetch.py --date 2026-08-27
```

- 全程约 3–6 分钟（每周约 500–900 条，每页 10 条自动翻页，请求间隔 1.5 秒）。
- 输出目录：`wipo_reports/wipo_<公开日>/`，含：
  - `publications.json` — 全量结构化数据（公开号、标题、申请人、发明人、IPC、PCT 申请号、链接）
  - `publications.csv` — 同内容，可直接用 Excel 打开
  - `summary.txt` — 官方计数与 IPC 大组分布
- 网络中断会自动重试并重建会话续抓；若官方计数与实抓数不一致，以 JSON 中 `total_official` 与 `total_fetched` 为准并在报告中说明。

## 数据说明（重要，避免误读）

- 筛选口径：PATENTSCOPE 检索式 `(IC:A61 OR IC:C07) AND DP:<公开日>`，即**任意一个 IPC 分类**属于 A61/C07 即命中。因此结果中主分类可能是 C12N、G01N 等其他类（该申请同时挂了 A61/C07 副分类），这属于正常现象，不是误抓。
- 标题为公开原文语言（英文/中文/日文/韩文/德文等），申请人为原文大写形式。
- `link` 字段为 PATENTSCOPE 详情页地址，点击可看摘要、权利要求与全文。

## 二级分析脚本

抓取完成后运行 `scripts/analyze_weekly.py <输出目录>`（如 `wipo_reports/wipo_2026-08-27`），生成 `analysis.json`（每条附加类别与靶点标注）与 `listing.md`（分组全量清单）。

**药物类型分类口径（用户指定，10 类）**：化学药小分子 / 抗体 / 抗体偶联物（ADC）/ 小核酸 / CAR-T / 抗体平台 / 多肽/短肽 / 偶联单元（毒素/连接子）/ 其他偶联类（PDC、AOC、APC 等）/ 其他。分类基于标题关键词 + 第一 IPC 分类自动初筛，规则在脚本中可维护；器械、制剂、材料等归入"其他"。

**靶点识别**：从标题提取明确出现的靶点（词表在脚本 TARGETS 中）。仅对**化学药小分子、抗体、ADC、多肽/短肽、CAR-T** 五类提取；小核酸、偶联单元、其他偶联类、抗体平台及其他类不做靶点标注。**"其他"类（器械/诊断/制剂/材料等非药品）在清单和周报中一律折叠，只给计数不展开。**

## 周报撰写流程（Claude 执行）

1. 运行抓取脚本（若用户未指定日期则默认最近周四）。脚本耗时数分钟，告知用户正在抓取。
2. 运行二级分析脚本。
3. 读取 `analysis.json`，生成周报写入 `wipo_reports/wipo_<公开日>/weekly_report.md`，结构：
   - **头部**：公开日、检索式、总条数、方法与局限说明
   - **药物类型分布表**（上述 10 类 + 占比）
   - **靶点识别**：**第一段直接罗列本周识别到的全部靶点及件数**（一个不漏，含仅 1 件的），随后再给重复出现靶点统计表 + 重点条目表（靶点/公开号/申请人/要点）
   - **MNC 药企条目专表**：全球综合性大药企（辉瑞、诺华、罗氏、默沙东、阿斯利康、赛诺菲、GSK、强生、礼来、BMS、安进、吉利德、艾伯维、拜耳、勃林格、武田、诺和诺德、再生元、第一三共、卫材等，名单在 analyze_weekly.py 的 COMPANY_GROUPS["MNC"] 中维护）本周**全部条目逐条罗列**（不限药物类别，含"其他"类并标注类别），不得只举例；0 条也要写明
   - **国内龙头条目专表**：国内龙头（恒瑞、百济神州、信达、康方、正大天晴、石药、翰森、科伦、再鼎、和黄、百利天恒/SystImmune、荣昌、复宏汉霖、君实、先声、齐鲁、东阳光等，名单在 COMPANY_GROUPS["国内龙头"] 中维护）本周**全部条目逐条罗列**，口径同上
   - **重点申请人动态**：申请量榜、其他活跃申请人（申请人归属不确定时不要猜测公司背景）
   - **本周值得关注**：编辑精选约 10 条，每条一句话理由
   - **数据文件说明**
4. **周报定稿后必须转成 Word**：将 `weekly_report.md` 转换为 `weekly_report.docx`，放在同一输出目录（`wipo_reports/wipo_<公开日>/`）交付给用户。转换方式按可用工具优先级：
   - 系统有 pandoc：`pandoc weekly_report.md -o weekly_report.docx`（可用 `--reference-doc` 套公司模板）；
   - 无 pandoc 但有 python-docx：用 python-docx 逐段重建（标题层级、表格、加粗），表格务必还原为 Word 原生表格而非纯文本；
   - 转换后确认中文字体显示正常（建议正文宋体/等线、标题黑体类），表格不溢出页宽（列多时用横向页面或收窄字号）。
   md 与 docx 都保留：md 供归档与后续检索，docx 供分发阅读。
5. 在对话中只输出周报摘要（分布表 + 靶点/申请人要点 + 精选），**不要把 700+ 条全量清单贴进对话**（全量在 listing.md）。主动询问用户想深入哪个类别、哪个申请人或哪几件。
6. 用户挑选具体公开号后需要摘要时：摘要在 PATENTSCOPE 详情页（records 中的 `link`）。**注意：PATENTSCOPE 详情页是 JS 动态渲染的，WebFetch/静态抓取只能拿到"Processing Please wait"空壳，直接 403 或抓不到摘要**；Espacenet 同样封爬虫。可行路径：① 用 wipo_weekly_fetch.py 同款 requests 会话手动请求详情接口调试；② 公开 1–2 周后 Google Patents（patents.google.com/patent/WO<号>A1/en）收录后再抓；③ 都失败则如实告知用户，给出链接请其浏览器人工查看。一次不要并发抓太多，逐篇进行。五类药品中标题未命中靶点的条目，可按用户指定子集抓摘要补全靶点。

## 异常处理

- 某周四命中为 0：大概率该周公开日因节假日顺延，提示用户确认本周实际公开日后用 `--date` 重试。
- 脚本报"页面结构可能已变化"：PATENTSCOPE 前端改版，需要人工检查脚本中的解析正则。
- PATENTSCOPE 临时不可达：告知用户稍候重试，或先在浏览器手工访问 https://patentscope.wipo.int/search/en/advancedSearch.jsf 用上述检索式应急。
