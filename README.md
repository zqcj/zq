# 竞价抓涨停 -- 决策先机

A 股集合竞价 + 开盘买点捕捉策略。

## 策略规则

| 序号 | 条件 | 时段 |
|------|------|------|
| 1 | 昨日涨停（首板/二板均可） | 盘前 |
| 2 | 集合竞价 9:20 前出现涨停价报价 | 9:15–9:20 |
| 3 | 9:30 成交高开 3%–6% | 开盘后 |
| 4 | 股价涨幅超过 7% 即为买点 | 9:30–10:00 |
| 5 | 符合当前热点主线，主力资金大幅关注最佳 | 辅助评分 |
| 6 | 换手率 8%–20%（拉升型涨停板） | 昨日 + 当日 |

## 策略流程

```
盘前筛选（规则1+6）
  └─ 昨日涨停池：首板 / 二板，换手率 8%-20%

9:15–9:20（规则2）
  └─ 竞价涨停报价监控

9:30–10:00（规则3-6）
  └─ 高开 3%-6% 确认
  └─ 涨幅 ≥ 7% 触发买点
  └─ 当日换手率 8%-20%
  └─ 热点主线 + 主力资金评分排序
```

## 项目结构

```
├── config/strategy.yaml
├── src/
│   ├── screener.py          # 规则1：昨日涨停筛选
│   ├── auction_monitor.py   # 规则2：竞价涨停报价
│   ├── opening_monitor.py   # 规则3-4：高开 + 买点
│   ├── hot_sector.py        # 规则5：热点主线 + 主力资金
│   ├── strategy.py          # 策略引擎
│   └── utils.py
├── main.py
└── tests/
```

## 快速开始

```bash
pip install -r requirements.txt

# 查看昨日涨停候选池
python3 main.py --prepare-only

# 仅竞价扫描（规则1-2）
python3 main.py --auction-only --mock-time 09:18:00

# 完整策略（规则1-5）
python3 main.py --mock-time 09:35:00
```

## 配置说明

```yaml
opening:
  open_gain_min: 3.0
  open_gain_max: 6.0
  buy_gain_threshold: 7.0
  turnover_min: 8.0           # 换手率下限（%）
  turnover_max: 20.0          # 换手率上限（%）

screener:
  turnover_min: 8.0           # 昨日涨停日换手率
  turnover_max: 20.0

hot_sector:
  top_sector_count: 10        # 热点板块数量
  min_main_force_inflow: 500  # 主力净流入下限（万元）
  require_hot_sector: true    # 是否必须命中热点
```

## 信号强度

综合评分（0-100），考虑：

- 板位（首板 > 二板）
- 高开幅度（接近 4.5% 中值更佳）
- 当前涨幅
- 热点主线匹配数
- 主力净流入规模

## 免责声明

本策略仅供学习研究，不构成投资建议。股市有风险，投资需谨慎。
