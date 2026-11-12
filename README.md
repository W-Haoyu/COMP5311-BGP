# GILL 论文学习与小规模复现

本项目整理 SIGCOMM 2024 论文 *The Next Generation of BGP Data Collection Platforms*，并使用 RIPE RIS 公开历史数据实现包含更新关联分析、锚点 VP 和过滤的**小规模近似原型**。项目尚未完整复现论文的算法、数据规模或实验结果；不要将本地结果表述为论文原结果。

- [组员阅读与 report 编写文档](docs/论文阅读与复现报告指南.md)
- [最终实验方法和限制](results/anchor_sweep/README.md)
- [早期实验说明](README_early_experiment.md)

## 目录

```text
coding/
├── README.md                 项目入口和环境说明
├── docs/                     论文阅读与 report 指南
├── src/                      解析、原型算法与实验脚本
├── tests/                    自动测试
├── results/                  已保存的实验配置、结果和各阶段说明
├── requirements.txt          Python 依赖版本
├── data/                     本地下载的数据（不提交 Git）
├── notes/                    本地论文提取文本（不提交 Git）
└── .venv/                    本地 Python 环境（不提交 Git）
```

主要代码：

- `src/fast_selected.py`、`src/rib_replay.py`：选择性读取 MRT，初始化部分 RIB 并回放更新。
- `src/reconstitution_v2.py`、`src/hour_training.py`：相关组、重构与一小时训练实验。
- `src/topology_anchor.py`：小型图事件与锚点选择近似。
- `src/anchor_sweep.py`：验证集选择锚点数量，随后在留出窗口评估。
- `src/filter_stream.py`：过滤标准化 JSONL 输入；不是独立的实时 BGP 对等采集器。

## 环境安装与测试

建议使用 Python 3.9–3.11（原实验使用 macOS ARM64、Python 3.9）。在项目根目录：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

`.venv/` 不应在不同机器之间复制；请在自己的机器上重新创建。测试为小型合成测试，不需要下载 405 MiB 快照。

## 下载数据

原始数据由 RIPE RIS 提供，文件名时间均为 UTC。本仓库忽略 `data/`，不会把数据随代码提交。若只阅读已保存的实验结果，不必下载。

一小时训练与最终锚点数量实验所需更新文件：

```bash
mkdir -p data/rrc00
for minute in 00 05 10 15 20 25 30 35 40 45 50 55; do
  file="updates.20230901.00${minute}.gz"
  curl -fL --retry 3 "https://data.ris.ripe.net/rrc00/2023.09/${file}" -o "data/rrc00/${file}"
done
for time in 0100 0110 0125 0130 0145 0150; do
  file="updates.20230901.${time}.gz"
  curl -fL --retry 3 "https://data.ris.ripe.net/rrc00/2023.09/${file}" -o "data/rrc00/${file}"
done
```

如需重新运行 RIB 初始化和图锚点实验，还需下载约 **405 MiB（压缩）**的快照：

```bash
curl -fL --retry 3 https://data.ris.ripe.net/rrc00/2023.09/bview.20230901.0000.gz -o data/rrc00/bview.20230901.0000.gz
gzip -t data/rrc00/bview.20230901.0000.gz
```

## 重跑最终实验

克隆仓库并按上面下载更新后，使用仓库中已保存的前置规则、图锚点与前缀选择结果：

```bash
PYTHONDONTWRITEBYTECODE=1 python src/hour_training.py
PYTHONDONTWRITEBYTECODE=1 python src/anchor_sweep.py
PYTHONDONTWRITEBYTECODE=1 python src/anchor_update_baseline.py
```

这些命令会**覆盖**各自结果目录的同名文件。建议先在独立分支或复制目录中运行。要从原始 RIB 重建前置图与策略，还需按 `results/rib_replay/README.md`、`results/topology_anchor/README.md` 和 `results/pipeline/README.md` 的顺序阅读依赖与限制；相关脚本所需输入并非均由上述最终实验命令自动生成。

## GitHub 协作

在本地项目根目录初始化并检查提交内容：

```bash
git init
git status --short --ignored
git add .
git status --short
```

确认不包含 `data/`、`.venv/`、论文提取文本或大中间日志后，再按小组协作流程提交和推送。`.gitignore` 只对尚未跟踪的文件生效；如果数据已经被 Git 跟踪，需要先检查索引，不能仅靠新增忽略规则移除已有历史。原论文及数据使用须遵循各自的许可和引用要求；建议通过 DOI 链接论文，而不是将论文文件加入仓库。

本项目还未在 GitHub 创建仓库或执行提交。
