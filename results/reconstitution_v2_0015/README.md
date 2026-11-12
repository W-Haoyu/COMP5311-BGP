# 相关组重构：时间匹配实验

## 运行

在 coding 文件夹：

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/reconstitution_v2.py --test-slot 0015
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/compare_reconstitution.py --test-slot 0015
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/reconstitution_v2.py --test-slot 0020
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/compare_reconstitution.py --test-slot 0020
```

两个测试均使用 2023-09-01 00:00 UTC 的同一五分钟 rrc00 文件训练；测试文件分别从 00:15 和 00:20 UTC 开始。两个 independently computed rules.json 已核对完全一致。模型使用从先前实验训练数据中选出的 20 个 IPv4 前缀。

## 新实现

对每个前缀，以训练期首条更新为锚点划分互不重叠的 100 秒窗口；窗口内记录 VP、AS_PATH 和标准/large community 特征集合，并按相同集合出现次数赋权。对于保留的每条更新，查询包含它的最高权重组，按该更新的时间重构该组的特征；同权重使用确定性排序。以记录的 VP、路径、community 和时间为依据，采用不超过 100 秒的一对一匹配计算重构命中；真实更新的重复记录分别计数，完全相同时间和特征的重复预测去重。每轮为前缀增加能带来最多重构命中的一个 VP 的全部更新，达到训练召回 94% 或没有新增收益时停止；测试中的未知 VP 默认保留。

两个测试窗口分别保留 654/15467 和 589/14698 条前缀级记录，按本实验的匹配定义，重构召回为 79.38%、79.00%，预测集合的命中精确率为 14.51%、15.92%。精确率的分母为去重后的预测条目数，包含直接保留项；这不是论文的 false positive rate，且与上一版按窗口特征集合计数的指标口径不同，不可直接比较。

## 过滤对比

comparison.json 使用不加锚点的真实保留记录计算测试文件内 AS 无向链路覆盖。旧方案包含跨前缀去重，新方案只做前缀内选择，因此这不是隔离单一因素的消融；两者的记录预算也不同。每个方案分别与相同保留记录数量的 100 次随机逐条采样比较（seed 42）。随机抽样可能拆分单条 BGP 消息，其部署限制与 VP+前缀过滤不一样。结果对照只针对所选前缀的可解析普通 IPv4 announcements，不包括 RIB、撤销和 IPv6。

00:15 时旧/新规则分别保留 3.94%/4.23%，链路覆盖 15.34%/21.01%，对应同数量随机平均 54.08%/55.49%。00:20 时旧/新分别保留 3.77%/4.01%，覆盖 17.77%/23.79%，对应随机平均 52.55%/53.65%。本实现仍明显弱于该随机记录基线，不能说已经达到论文性能。

## 与论文的差距

相关组仍使用固定首条锚定时间窗和集合签名；训练仅五分钟而非两天；不处理 AS_SET、撤销、跨前缀与锚点；先前样本选取和比较均限于一个收集器、同一天和 20 个前缀。MRT 解码有错误，训练与测试文件分别有 5 条解析错误。对多对多时间关联采用一对一匹配是本实验可审计的实现选择，不保证完全一致于论文原始代码。因此这是接近论文思想的增量，不是完整或严格复现。
