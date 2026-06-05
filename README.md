# manuscript-citation-workflow

根据已经写好的小论文引言内容，倒插参考文献。

---

## 一、开始前你要准备什么

1. **一篇带【】占位符的稿件**  
   正文里每个要填文献的地方，都写成单独的 `【1】`、`【2】`……  
   **不要**写成 `【1–5】`，或一句里多个号挤在一起当一条。

2. **PDF 文件路径**  
   例如：`G:\小论文\xxx\Manuscript.pdf`  
   Agent 会从这个 PDF 里数【】、提取原句。

3. **给这篇论文起一个 project-id**  
   英文短名即可，例如：`jem-grassland-pes`、`my-paper-2026`。  
   每篇论文一个独立文件夹，互不干扰。

4. **工作目录**  
   工具在：`d:\cursor\code\web\manuscript-citation-workflow\`

5. **Python 环境**（Agent 一般会帮你跑；你自己跑脚本时需要）

   ```bash
   pip install pymupdf
   ```

---

## 二、怎么叫出这个 Agent

在 Cursor 聊天里，用下面任一方式开头：

- `@manuscript-citation-workflow`
- 或直接说：**倒插文献**、**填【】**、**引文阶段1**

Agent 会按四阶段流水线工作。**必须一阶段一阶段来，不能跳。**

---

## 三、全流程总览（四阶段）

| 阶段 | 内容 |
|------|------|
| 阶段 1 | 查文献、做核查表 → 你在 Canvas 里审 |
| 阶段 2 | 按你的意见改 → 可多轮 |
| 阶段 3 | 导出可粘贴正文 |
| 阶段 4 | 导出 References 列表 |

---

## 四、阶段 1：查文献 + 做核查表

### 1. 你要说的话（示例）

```text
@manuscript-citation-workflow 引文阶段1
PDF：G:\你的路径\Manuscript.pdf
project-id：my-new-paper
稿件标题：（可选，写上更好）
目标期刊：Journal of Environmental Management
```

### 2. Agent 会做什么

1. 新建文件夹：`manuscript-citation-workflow/my-new-paper/`
2. 从 PDF 提取所有【】，生成 `citation-registry.json`（每条【】一行，叫 C001、C002……）
3. 为每个【】找真实文献、填 DOI、写 claim（这句话在支撑什么观点）、标证据强度 A/B/C
4. 检查规则（见下文「硬性规则」）
5. 生成 Canvas 核查表（可视化审阅界面，带 DOI 链接）

### 3. 你会得到什么

1. **`citation-registry.json` 文件**：机器用的总账本，记录每条【】的文献和状态
2. **Canvas 页面**：给人看的核查表，按章节折叠，可点 DOI
3. **Canvas 路径类似**：  
   `C:\Users\Administrator\.cursor\projects\d-cursor-code-web\canvases\<项目名>-citation-audit-phase1.canvas.tsx`

### 4. 你要做什么

1. 在 Cursor 里打开 Canvas（**不是**改 `.tsx` 源码）
2. 逐条看：文献对不对、DOI 能不能点开、claim 是否匹配你的句子
3. 对每条选决定（见下表）

   | 你的选择 | 含义 |
   |----------|------|
   | `keep` | 保留 Agent 推荐的文献 |
   | `delete_marker` | 这个【】不填文献，正文里保留空【】 |
   | `replace` | 换一篇文献（说明理由或给 DOI） |
   | `split_feock_inline` | 正文自己归纳，只插一条分维引用（特殊场景） |
   | `keep_engel_2008` | 保留 Engel 2008（讨论节等特殊保留） |

4. 审完后，点 Canvas 里的 **「将审阅意见发送到聊天」**，或在聊天里直接说：

   ```text
   C007 delete_marker
   C012 replace，换用 xxx 2020
   C003 keep
   ```

### 5. 阶段 1 结束标志

1. Canvas 里每条你都看过
2. 你发出了审阅意见 → 进入阶段 2

> **注意**：阶段 1 **不会**给你可粘贴的正文，只有核查表。

---

## 五、阶段 2：按你的意见改（可多轮）

### 1. 你要说的话（示例）

```text
引文阶段2
C007 delete_marker
C028 delete_marker
C012 replace，理由：原推荐只支撑子观点
C058 keep
```

或：`Canvas 审阅意见已发送`（Agent 会读 `.canvas.data.json`）

### 2. Agent 会做什么

1. 更新 `citation-registry.json` 里每条的决定
2. 对 `replace` 的条目重新找文献
3. 检查 DOI 预算（同一 DOI 全文最多用 2 次）
4. 把确认过的条目标成 `status: locked`
5. 同步 Canvas，给你变更摘要（改了哪些 C00x、为什么改）

### 3. 你要做什么

1. 如果还有 `pending`（未确认）的条目 → 继续审 Canvas，再发意见
2. 如果全部 `locked` 且 Agent 说 DOI 预算通过 → 可以进阶段 3
3. 可以多轮，不满意就继续。例如继续说：

   ```text
   引文阶段2，C035 replace，Yin 那篇 DOI 不对
   ```

   直到你满意为止。

---

## 六、阶段 3：导出可粘贴正文

### 1. 前置条件（缺一不可）

- 所有条目 `status: locked`
- 你说：**「全部确认」**
- DOI 预算检查通过（零违规）

### 2. 你要说的话

```text
引文阶段3，全部确认
```

### 3. Agent 会运行（或你自己跑）

```bash
cd d:\cursor\code\web\manuscript-citation-workflow
python _backfill_source_paragraphs.py
python _phase34_export.py manuscript-citation-workflow/my-new-paper/citation-registry.json --require-locked
```

### 4. 你会得到

`my-new-paper/phase3-cited-paragraphs.md`，两部分：

- **Part 1 — 对照表（核对用）**：每个【】对应一行，是完整书目引文（含题名、期刊、DOI）。
- **Part 2 — 段内引文版正文（直接粘贴用）**。示例：

  > ……遥感监测（Hou et al., 2021）、面板数据回归（Hu et al., 2019）、双重差分（Xiao et al., 2025）、断点回归【】以及生态—经济耦合评价（Burkhard et al., 2012）……

### 5. 你要做什么

1. 打开 `phase3-cited-paragraphs.md`
2. 从 **Part 2** 复制段落，贴回 Word/LaTeX
3. 用 **Part 1** 核对完整引文是否正确

---

## 七、阶段 4：导出 References

### 1. 你要说的话

```text
引文阶段4
```

（阶段 3 跑 `_phase34_export.py` 时，已经同时生成了 phase4，通常不用再单独跑）

### 2. 你会得到

`my-new-paper/phase4-references.md`  
按 JEM 体例、DOI 去重、字母序排列的参考文献列表。

### 3. 你要做什么

核对 DOI、卷期页码，贴到稿件末尾 References 部分。

---

## 八、硬性规则（Agent 会自动检查，你也应知道）

1. **禁止 MDPI 期刊**
2. **同一 DOI 全文最多 2 次**（按 C001 → C002 → … 顺序消耗）
3. **一个【】= 一条 registry**，不能合并
4. **只推荐真实可查的文献**，不能编造
5. **C 级证据不能作为【】处唯一推荐**；找不到 A/B 级 → 删【】或改述
6. **阶段不能跳**：1 → 2 → 3 → 4

---

## 九、不要做的事

1. **不要**直接改 Canvas 的 `.tsx` 源码 — 在 Canvas 预览界面里操作
2. **不要**在阶段 1 就要求 paste-ready 正文 — 那是阶段 3 的事
3. **不要**跳过「全部确认」就进阶段 3 — 会报错或被拒绝
4. **PDF 改了之后**，要重新跑 `_backfill_source_paragraphs.py` 再导出

---

## 十、每篇新论文的「最短启动清单」

1. 稿件里每个引文位写成单独 `【n】`
2. 准备好 PDF 绝对路径 + `project-id`
3. 聊天：`@manuscript-citation-workflow 引文阶段1`，`PDF：...`，`project-id：...`
4. 打开 Canvas 审阅 → 发意见
5. 聊天：`引文阶段2` + 你的 C00x 决定（可多轮）
6. 聊天：`引文阶段3，全部确认`
7. 打开 phase3 Part 2 粘贴正文；phase4 粘贴 References

---

## 十一、常见问题

**Q：继续改某篇已做过的论文？**  
说 `project-id` 和要改的 C00x，从阶段 2 继续即可。

**Q：PDF 里中文乱码、个别句子不对？**  
PDF 提取有时不完美；Part 2 大部分句子可用，个别需手工微调。以后可考虑用 Word 作源文件（可再扩展）。

**Q：Canvas 和 registry 不一致？**  
让 Agent 运行 `_generate_canvas.py` 重建 Canvas，或 `_phase2_sync_from_canvas.py` 从 Canvas 同步回 registry。

**Q：怎么知道能不能进阶段 3？**  
Agent 会说「全部 locked + DOI 预算通过」；或自己跑：

```bash
python _validate_doi_budget.py
```

---

## 十二、你实际在聊天里怎么说（模板）

### 1. 新论文第一次

```text
@manuscript-citation-workflow 引文阶段1
PDF：G:\路径\Manuscript.pdf
project-id：paper-abc
目标期刊：JEM
```

### 2. 审完后

```text
引文阶段2
C001 keep
C007 delete_marker
C012 replace，需要支撑 RDD 方法的中文草原研究
```

### 3. 全部满意

```text
引文阶段3，全部确认
```

### 4. 要 References

```text
引文阶段4
```

（若阶段 3 已跑过，直接打开 `phase4-references.md` 即可，无需再说这句话）

---

## 总结

这就是完整流程。核心就三句：

1. **阶段 1** 在 Canvas 审文献
2. **阶段 2** 改到全部 `locked`
3. **阶段 3** 复制 Part 2 贴回稿件

其余都是 Agent 和脚本在后台跑。
