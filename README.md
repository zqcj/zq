# 竞价抓涨停 -- 决策先机

A 股集合竞价涨停捕捉策略，聚焦 **9:20 前决策先机**。

## 策略规则

| 序号 | 条件 | 说明 |
|------|------|------|
| 1 | 昨日涨停 | 首板、二板均可 |
| 2 | 竞价涨停报价 | 集合竞价 **9:20 之前** 出现涨停价报价 |

### 为什么聚焦 9:20 前？

A 股集合竞价分两段：

- **9:15 - 9:20**：可挂单、可撤单 → 真资金意愿，适合提前决策
- **9:20 - 9:25**：可挂单、不可撤单 → 报价更"硬"，但决策窗口已过

本策略在 9:20 前捕捉涨停价报价，争取先手优势。

## 项目结构

```
├── config/strategy.yaml    # 策略参数
├── src/
│   ├── screener.py         # 昨日涨停筛选（首板/二板）
│   ├── auction_monitor.py  # 集合竞价监控
│   ├── strategy.py         # 策略引擎
│   ├── models.py           # 数据模型
│   └── utils.py            # 涨停价计算等工具
├── main.py                 # 命令行入口
└── requirements.txt
```

## 快速开始

```bash
pip install -r requirements.txt

# 仅查看昨日涨停候选池
python main.py --prepare-only

# 运行完整策略（需在交易时段）
python main.py

# 指定交易日
python main.py --date 20250616

# 模拟竞价时间测试
python main.py --mock-time 09:18:00
```

## 配置说明

`config/strategy.yaml` 关键参数：

```yaml
screener:
  allowed_boards: [1, 2]       # 1=首板, 2=二板
  exclude_st: true             # 排除 ST
  min_float_market_cap: 10     # 最小流通市值（亿）
  max_float_market_cap: 500    # 最大流通市值（亿）

auction:
  start_time: "09:15:00"
  end_time: "09:20:00"         # 决策先机窗口
  limit_up_tolerance: 0.998    # 涨停价容差
  min_auction_gain_pct: 9.0    # 最低竞价涨幅
  min_auction_volume_ratio: 0.01  # 竞价量/昨日成交量
```

## 信号强度

综合评分（0-100），考虑：

- 板位（首板加分高于二板）
- 竞价涨幅
- 竞价量比

## 免责声明

本策略仅供学习研究，不构成投资建议。股市有风险，投资需谨慎。
