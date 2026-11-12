# RIB 初始化与连续更新回放

本实验从 RIPE RIS rrc00 的 `bview.20230901.0000.gz` 快照，加载 `results/pipeline/report.json` 中选定的 20 个 IPv4 前缀，并按时间应用 00:00、00:05、00:10 UTC 三份连续更新文件。数据来源：https://data.ris.ripe.net/rrc00/2023.09/ 。快照压缩文件约 405 MiB；扫描时先按 MRT 前缀筛选，仅对目标前缀解码和维护状态。

在 coding 目录运行：

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -u src/rib_replay.py
```

运行将覆盖本目录的 `summary.json` 和 `state_changes.jsonl`。后者每行记录一个产生路径或定向链路权重变化的更新消息，包含 UTC Unix 秒、peer ASN@IP、变化前后路径和链路权重差。一个消息可能涵盖多个前缀；它不是论文所定义或平衡采样的独立事件。文件按时间戳和输入顺序排序。

此次运行读取 1,189,967 个 MRT 记录，目标前缀的 852 条初始 RIB 路由全部载入。更新中 49,845 条前缀通告和 4,200 条撤销被应用；记录了 35,814 条有状态变化的消息。最终为 749 条路由、379 条不同定向链路。记录间存在观测点和前缀重复；不是全球路由图。

限制：仅普通 IPv4 NLRI 和 AS_SEQUENCE，未处理 IPv6 MP_REACH/UNREACH、AS_SET、AS4_PATH 重建和 BGP peer 会话状态重置。对不能正确处理的新通告，删除同 VP/前缀的旧已知路径以避免静默保留陈旧值；不存在表示“未知”的独立路由状态，因此不能等同真实撤销。RIB 和更新的时间一致性依赖 RIS 快照语义。三份更新文件分别存在 5、4、5 个 MRT 解析错误；可能造成状态不完整。快照不含每条路由全部属性的状态，事件文件尚未用于论文的 15 维拓扑特征、事件筛选和锚点选择。结果不能称为完整 GILL 复现。
