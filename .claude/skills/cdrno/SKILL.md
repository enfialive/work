---
name: cdrno
description: 对抗体可变区氨基酸序列进行多方案CDR标注（Kabat/Chothia/IMGT/AbM），对唯一CDR序列分配SEQ ID NO，输出汇总对照表与序列清单。
argument-hint: "[抗体序列 或 含多条序列的文本]"
---

# 抗体 CDR 多方案标注与 SEQ ID NO 编号

输入抗体可变区氨基酸序列（单字母），自动识别重链/轻链，输出 Kabat、Chothia、IMGT、AbM 四种 CDR 定义方案下的 CDR 序列标注，并对相同序列使用同一 SEQ ID NO 编号。

## 触发条件

- 用户发送抗体氨基酸序列（单字母格式，通常 ~100-130 aa）
- 用户提及 CDR、CDR标注、CDR编号、SEQ ID NO 等关键词
- 用户要求对抗体序列进行 CDR 分析或比对

## 输入格式

支持以下输入方式：

1. **FASTA 风格多序列**（推荐）：
   ```
   >M1 VH
   EVQLLESGGGLVQPGGSLRLSCAAS...
   >M1 VL
   DIQMTQSPSSLSASVGDRVTITC...
   >M2 VH
   QVTLKESGPGILQSSQTLSLTCSFS...
   ```

2. **逐条粘贴**：直接给出单条或多条序列，带或不带标签

3. **纯序列**：无标签的纯氨基酸序列

### FASTA 标签处理规则

- 保留用户原始标签作为变体名（如 `M1 VH`、`M1 VL`）
- **重复标签**：若同一标签出现多次，第二次起追加 ` (2)`、` (3)` 后缀区分
- **链类型标注冲突**：若用户标签暗示的链类型（如 `>xxx VH`）与算法自动检测结果不一致，**以算法检测为准**进行 CDR 命名，同时在输出中红色高亮标注该冲突，并提示用户确认

### 链类型自动识别

工具通过 FR4 保守基序（`WGxQG`、`FGxGTK`、`FGxGT[KL]`）及 N 端特征自动区分：

| 链类型 | 标识 | CDR 命名 |
|--------|------|----------|
| **VH** — 重链 | H | CDR-H1, CDR-H2, CDR-H3 |
| **VL** — 轻链可变区（含 VK/VL） | L | CDR-L1, CDR-L2, CDR-L3 |

> **约定**：在抗体领域，VL 与 VK 常混用指代轻链可变区。本工具内部算法会区分 Kappa (VK) 与 Lambda (VL)，但在输出中统一以 **VL** 指代轻链，CDR 统一命名为 CDR-L1/L2/L3。

## 工具链

本技能依赖两个核心脚本：

- **`cdr_batch.py`** — CDR 标注引擎：Needleman-Wunsch 全局比对 + Kabat 编号转移 + CDR 区域提取
- **`cdrno_generate_docx.py`** — 通用 Word 导出脚本：接收 FASTA 文本（stdin 或文件路径），自动完成链检测→CDR+FR 标注→SEQ ID NO 分配（V-region → CDR → FR 三级编号）→Word 输出全流程

```bash
# 方式1：管道传入 FASTA
echo ">M1 VH
EVQLLESGGGLVQPGGSLRLSCAAS..." | python cdrno_generate_docx.py

# 方式2：文件传入
python cdrno_generate_docx.py input.fasta
```

输出文件：`CDRNO_SEQ_ID_NO_List.docx`（当前目录）

支持四种 CDR 定义方案：

| 定义方案 | 说明 | 重链 CDR 边界 | 轻链 CDR 边界 |
|---------|------|:-------------:|:-------------:|
| **Kabat** | 基于序列可变性，最广泛使用 | H1: 31–35, H2: 50–65, H3: 95–102 | L1: 24–34, L2: 50–56, L3: 89–97 |
| **Chothia** | 基于结构 loop 区 | H1: 26–32, H2: 52–56, H3: 95–102 | L1: 24–34, L2: 50–56, L3: 89–97 |
| **IMGT** | 基于种系基因，标准化 | H1: 26–33, H2: 51–57, H3: 93–102 | L1: 27–32, L2: 50–52, L3: 89–97 |
| **AbM** | Chothia 扩展版 (Martin) | H1: 26–35, H2: 50–58, H3: 95–102 | L1: 24–34, L2: 50–56, L3: 89–97 |

> **注**：以上边界均基于 Kabat 编号体系。Chothia H1 的结束位置在部分文献中可能延伸至 H34（取决于 H35 位插入情况），本工具使用严格的 Chothia 定义（H26–H32）。AbM 使用与 Chothia 相同起点的扩展范围（H26–H35），即 Martin/Enhanced Chothia 惯例。

## 处理流程

### 第一步：解析输入

1. 从用户消息中提取所有抗体序列
2. 识别 FASTA 标签（如 `>H1`、`>L1`）作为变体名
3. 若无标签，按 `Variant-1`, `Variant-2` 自动命名
4. 去除空格、换行、数字等非氨基酸字符，仅保留 `ACDEFGHIKLMNPQRSTVWY`
5. 验证序列长度（≥30 aa）
6. 自动检测每条序列的链类型（VH / VK / VL）

### 第二步：运行 CDR 批量标注

**首选方式**：将用户 FASTA 输入写入临时文件，调用通用脚本一键生成 Word：

```bash
python cdrno_generate_docx.py input.fasta
```

**备选方式**（仅需对话中 Markdown 摘要时）：从 Python 直接导入核心函数：

```python
from cdr_batch import analyze_cdr
# def_name ∈ {'Kabat', 'Chothia', 'IMGT', 'AbM'}
result = analyze_cdr(seq, def_name)
# result['regions'] 中每个元素含 name, sequence, length, start_label, end_label
```

### 第三步：分配 SEQ ID NO

**范围**：对用户提供的每条完整抗体可变区序列以及所有提取的 CDR 和 FR 序列统一分配 SEQ ID NO。

1. **先为完整 V-region 序列分配编号**：按用户输入顺序，每条唯一序列一个 SEQ ID NO（相同序列复用同一编号）
2. **再为 CDR 序列分配编号**：收集所有 `(变体名, CDR标签, 定义方案, 序列)`，从 V-region 编号最大值之后接续
3. **最后为 FR 序列分配编号**：收集所有 `(变体名, FR标签, 定义方案, 序列)`，从 CDR 编号最大值之后接续
4. 建立 `序列 → SEQ ID NO` 映射字典
5. **相同序列 = 相同 SEQ ID NO**（跨方案、跨变体、跨轻重链、跨 CDR/FR 均去重）
6. 编号从 1 开始递增

> **FR 区域说明**：每个 CDR 定义方案在定义 CDR 边界的同时也隐含定义了 FR 边界。FR1–FR4 的边界因方案而异：
>
> **重链 VH：**
>
> | 区域 | Kabat | Chothia | IMGT | AbM |
> |------|:-----:|:-------:|:----:|:---:|
> | FR1 | 1–30 | 1–25 | 1–25 | 1–25 |
> | FR2 | 36–49 | 33–51 | 34–50 | 36–49 |
> | FR3 | 66–94 | 57–94 | 58–92 | 59–94 |
> | FR4 | 103–113 | 103–113 | 103–113 | 103–113 |
>
> **轻链 VL：**
>
> | 区域 | Kabat | Chothia | IMGT | AbM |
> |------|:-----:|:-------:|:----:|:---:|
> | FR1 | 1–23 | 1–23 | 1–26 | 1–23 |
> | FR2 | 35–49 | 35–49 | 33–49 | 35–49 |
> | FR3 | 57–88 | 57–88 | 53–88 | 57–88 |
> | FR4 | 98–107 | 98–107 | 98–107 | 98–107 |
>
> 由于不同方案下同一 FR 的序列可能不同（如 Kabat FR2 vs Chothia FR2），它们各自独立分配 SEQ ID NO。

### 第四步：输出汇总表（Markdown 对话 + Word 文件）

**最终交付物为 Word 文档（.docx）**，同时在对话中展示 Markdown 摘要。

**表格〇：V-region 序列编号（最先输出）**

| Variant | 链类型 | 序列 | SEQ ID NO |
|:-------:|:------:|------|:---------:|
| **H1** | VH | `EVQLLESG...` | SEQ ID NO: 1 |
| **H2** | VH | `EVQLLESG...` | SEQ ID NO: 2 |
| **L1** | VL | `DIQMTQSP...` | SEQ ID NO: 3 |

- 每条唯一的完整可变区序列分配独立 SEQ ID NO
- 若多条变体序列完全相同，共用同一编号
- 重链与轻链合并列出
- 链类型列统一使用 **VH** / **VL**（不区分 VK/VL）
- 若标签暗示的链型与检测结果不一致，以检测为准并在该行红色标注

**表格一：CDR 标注对照表（重链+轻链合并为一张表）**

- 重链与轻链**合并为一张表**，CDR-H1/H2/H3 在前，CDR-L1/L2/L3 在后

| Variant | CDR | Kabat | Chothia | IMGT | AbM |
|:-------:|:---:|:-----:|:-------:|:----:|:---:|
| **H1** | CDR-H1 | SEQ ID NO: X | SEQ ID NO: Y | ... | ... |
| | CDR-H2 | ... | ... | ... | ... |
| | CDR-H3 | ... | ... | ... | ... |
| **H2** | CDR-H1 | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |
| **L1** | CDR-L1 | SEQ ID NO: X | SEQ ID NO: Y | ... | ... |
| | CDR-L2 | ... | ... | ... | ... |
| | CDR-L3 | ... | ... | ... | ... |

- 每行 = 一个变体的一个 CDR（每个变体占 3 行）
- 每列 = 一种定义方案
- 每个单元格 = 对应的 SEQ ID NO
- 若某变体与参考变体（该链类型第一条）在该位置不同，用 **粗体** 标记

**表格三：FR 标注对照表（重链+轻链合并为一张表）**

- 格式与表格一一致，重链 FR1/FR2/FR3/FR4 在前，轻链在后

| Variant | FR | Kabat | Chothia | IMGT | AbM |
|:-------:|:--:|:-----:|:-------:|:----:|:---:|
| **H1** | FR1 | SEQ ID NO: X | SEQ ID NO: Y | ... | ... |
| | FR2 | ... | ... | ... | ... |
| | FR3 | ... | ... | ... | ... |
| | FR4 | ... | ... | ... | ... |
| **H2** | FR1 | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... |
| **L1** | FR1 | SEQ ID NO: X | SEQ ID NO: Y | ... | ... |
| | FR2 | ... | ... | ... | ... |
| | FR3 | ... | ... | ... | ... |
| | FR4 | ... | ... | ... | ... |

- 每行 = 一个变体的一个 FR（每个变体占 4 行）
- 每列 = 一种定义方案
- 每个单元格 = 对应的 SEQ ID NO
- 若某变体与参考变体（该链类型第一条）在该位置不同，用 **粗体** 标记
- 由于不同方案下同一 FR 的边界不同（如 Kabat FR2 vs Chothia FR2），各方案的 FR 序列可能不同，各自独立分配 SEQ ID NO

**表格二：SEQ ID NO 序列清单（轻重链共用，统一编号）**

| SEQ ID NO | Source Variant(s) | Sequence | Length |
|:---------:|:-----------------|----------|:------:|
| 1 | [V-region] M1 VH [Heavy] | `EVQLLESG...` | 117 |
| 2 | [V-region] M1 VL [VL], M5 VL [VL] | `DIVMTQSP...` | 112 |
| 3 | [CDR-H1] M1 VH (Kabat) | `SYWMN` | 5 |
| 4 | [CDR-H1] M1 VH (Chothia), M1 VH (IMGT), M1 VH (AbM) | `GYAFSSYWMN` | 10 |
| ... | ... | ... | ... |
| 5 | [FR1] M1 VH (Kabat) | `EVQLLESGGGLVQPGGSLRLSCAAS` | 25 |
| 6 | [FR1] M1 VH (Chothia), M1 VH (IMGT), M1 VH (AbM) | `EVQLLESGGGLVQPGGSLRLSCAASGFTFS` | 30 |
| ... | ... | ... | ... |

- 列顺序：SEQ ID NO → Source Variant(s) → Sequence → Length
- **Source Variant(s)** 列包含类型前缀 `[V-region]`、`[CDR-H1]`、`[FR1]` 等，后跟来源变体与方案
- **Sequence** 列使用等宽字体（Consolas），固定列宽、**自动换行**，不通过拉大列宽来容纳长序列
- 行底色按类别区分：
  - V-region：**浅蓝底**（`D6E4F0`）
  - CDR：**白底**
  - FR：**浅绿底**（`E2EFDA`）
- 排序规则：按 SEQ ID NO 编号递增排列（即 V-region → CDR → FR 的自然编号顺序）
- FR 序列与 CDR 序列之间不刻意插入空行或分节标记，以编号递增顺序自然衔接

### （可选）第五步：突变分析

如果用户提供了多条同源变体序列，可以额外输出：

1. **突变概览** — 以第一条变体为参照，列出每条变体的突变位点与数量（格式：`原残基+位置+新残基`，基于 Kabat 编号）
2. **突变位点定位** — 标注每个突变位点在不同 CDR 定义方案下的区域归属（FR1 / CDR-H1 / FR2 / ...）

### 第六步：生成专利申请说明书文字

Word 文档末尾自动生成以下专利文字区块：

**区块一：Kabat 规则定义的 CDR 实施方案**
- 将 Kabat 方案下共享相同 CDR 序列组合的变体归为一个条目
- 每个条目列出 HCDR1/2/3 + LCDR1/2/3 的 SEQ ID NO 集合
- 结尾标注"按照 Kabat 规则定义"

**区块二：IMGT 规则定义的 CDR 实施方案**
- 格式同区块一，使用 IMGT 方案的 CDR 数据
- 结尾标注"按照 IMGT 规则定义"

**区块三：AbM 规则定义的 CDR 实施方案**
- 格式同区块一，使用 AbM 方案的 CDR 数据
- 结尾标注"按照 AbM 规则定义"

**区块四：重链可变区和轻链可变区全景覆盖**
- 列出所有 VH 和 VL 的 SEQ ID NO
- 声明上述重链/轻链可变区包含的 CDR 按 Kabat、IMGT、AbM 或 Chothia 规则定义

**区块五：重链可变区逐条列举**
- 每个独特 VH 序列一条，含 % 同一性声明（至少 90%~99%）
- 格式：`所述重链可变区包含如SEQ ID NO：N所示氨基酸序列，或与SEQ ID NO：N的氨基酸序列具有至少90%...同一性的氨基酸序列，或由SEQ ID NO：N组成`

**区块六：轻链可变区逐条列举**
- 每个独特 VL 序列一条，格式同区块五

**区块七：重链可变区+轻链可变区配对组合**
- 按变体名称前缀匹配同一抗体的天然 VH+VL 配对（不做全排列）
- 每组配对含两条链各自的 % 同一性声明

> **注意**：生成的文字中靶点名称默认为 `X`，需手动替换为实际靶点。如有多个 VH/VL 家族需用"或者"分隔，可手动调整区块四的结构。

## 输出规范

1. 对话中展示 Markdown 格式摘要，同时生成 Word 文档（.docx）作为最终交付物
2. SEQ ID NO 格式统一为 `SEQ ID NO: N`（N 为数字）
3. 变体名保留用户原始标签
4. Table 1 重链与轻链合并为一张表；Table 2 列序为 SEQ ID NO → Source Variant(s) → Sequence → Length
5. Word 中 Sequence 列使用 Consolas 等宽字体、固定列宽、自动换行；V-region 行蓝底、CDR 行白底；与参考变体不同的 SEQ ID NO 以红色粗体标注
6. 附简短解读：指出哪些 CDR 区域保守、哪些有变异、变异落在哪些定义方案中

## 重要说明

⚠️ **局限性**：
- 本工具使用参考序列（IGHV3-23 / IGKV1-39 / IGLV1-44 种系）的 Needleman-Wunsch 全局比对来转移 Kabat 编号
- 对于高度变异的抗体（尤其长 CDR-H3 含大量插入），编号精度可能下降
- 仅支持重链 (VH) 和轻链 (VK/VL) 可变区，不适用于恒定区或全长序列
- 结果仅供科研参考，关键应用建议结合 [abYsis](http://www.bioinf.org.uk/abs/) 或 [ANARCI](http://opig.stats.ox.ac.uk/webapps/anarci/) 交叉验证
