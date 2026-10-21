# Trading Game · 局域网交易台

[![Tests](https://github.com/D3-3109/fakestreet/actions/workflows/tests.yml/badge.svg)](https://github.com/D3-3109/fakestreet/actions/workflows/tests.yml)
[![Docker](https://github.com/D3-3109/fakestreet/actions/workflows/docker.yml/badge.svg)](https://github.com/D3-3109/fakestreet/actions/workflows/docker.yml)

> 一个给几个朋友一起玩的模拟交易游戏：真实行情、虚拟资金、周赛季、杠杆与永续合约。
>
> **上游项目**：[M1XZG/fakestreet](https://github.com/M1XZG/fakestreet)（MIT）— 原版只有现货买卖。
> **本仓库**在其基础上做了大幅扩展：中英双语、杠杆保证金、永续/期货、现货做空、周赛季、实时动态、每日报告、交易所风格首页。

价格是真的，交易是假的。仅供娱乐与学习，不构成任何投资建议。

---

## 这是什么

在局域网里起一个服务，几个人用各自设备打开网页，每人 10 万美元虚拟资金，用**真实市场报价**交易股票、加密货币和外汇，比谁赚得多。

一周一个赛季，到期自动结算、归档冠军、所有人重新起跑。

## 功能

### 交易

- **现货**：按实时价买卖股票 / 加密货币 / 外汇，支持碎股（0.01 BTC）
- **现货做空**：卖出超过持仓即开出空头，数量为负，净值自动扣掉负债
- **逐仓杠杆**：1x 起，**默认无上限**，保证金全额亏光才强平
- **永续合约**：无到期日，按游戏内多空失衡收付资金费
- **期货**：1 小时后按现货价自动结算
- **追加保证金**：降低强平风险，实时看到强平价变化

### 赛季

- 默认 7 天一轮，到期自动归档排名、清空持仓、重置现金、开启新赛季
- 历史赛季与冠军留在荣誉榜里
- 首页顶部有倒计时与进度条

### 界面

- **交易所风格首页**：等权市场指数折线图（24h/3d/7d）、涨跌榜、实时动态纸带、赛季积分榜
- **实时动态**：谁开了什么仓、谁爆了仓、赛季结算，滚动播报
- **提醒铃**：保证金率预警、爆仓、被超越，只推给你自己
- **每日报告**：期初/期末净值、日内高低、成交笔数、爆仓次数、最佳/最差标的
- **资产曲线**：24 小时 / 7 天净值走势
- **迷你走势图**：行情表内 76 个标的的 24 小时 SVG 折线
- **中英双语**：右上角一键切换，后端提示也跟着变

## 快速开始

### 用现成镜像（最省事）

每次推送到 `main` 都会构建并发布多架构镜像（amd64 / arm64）到 GHCR：

```bash
docker run -d --name trading-game \
  -p 8000:8000 \
  -v trading-game-data:/app/data \
  --restart unless-stopped \
  ghcr.io/d3-3109/fakestreet:latest
```

打开 `http://localhost:8000`。数据存在 `trading-game-data` 卷里，重启不丢。

镜像标签：`latest`（主分支）、`sha-xxxxxxx`（每次提交）、`v1.2.3`（打了 tag 的话）。

> 如果 GHCR 包是私有的，需要先 `docker login ghcr.io`。第一次推送后到仓库的
> **Packages** 页面把包设为 public 即可匿名拉取。

### 从源码用 Docker

```bash
docker compose up --build
```

### 不用 Docker

需要 Python 3.10+。

```bash
./run.sh
```

会自动创建 `.venv/`、装依赖、在 8000 端口启动。

## 玩法要点

1. 注册时除了密码，还要设一个**记忆词**——那是找回密码的唯一方式（没有邮箱）
2. 初始资金 10 万美元
3. 行情页可以自己添加标的：股票填代码（如 `BABA`），加密货币搜 CoinGecko，外汇填 ISO 代码（如 `SEK`）
4. 衍生品页可以开杠杆仓位，注意看**强平价**和红字警告
5. 所有设备共享同一个市场、同一个排行榜

## 默认参数（都能用环境变量改）

| 参数 | 默认 | 说明 |
|---|---:|---|
| `TRADING_GAME_STARTING_CASH` | 100000 | 每人起始资金 |
| `TRADING_GAME_SEASON_DAYS` | 7 | 赛季长度（天） |
| `TRADING_GAME_MAX_LEVERAGE` | 0 | 杠杆上限，**0 = 不限制** |
| `TRADING_GAME_MAINTENANCE_MARGIN` | 0 | 强平线（保证金剩余百分比），**0 = 亏光才平** |
| `TRADING_GAME_MIN_MARGIN` | 0.01 | 最小保证金，实际决定杠杆天花板 |
| `TRADING_GAME_MONITOR_INTERVAL` | 2 | 强平扫描间隔（秒） |
| `TRADING_GAME_FUNDING_INTERVAL` | 300 | 资金费结算间隔（秒） |
| `TRADING_GAME_FUNDING_CAP` | 0.003 | 单次资金费上限 |
| `TRADING_GAME_FUTURE_DURATION` | 3600 | 期货到期时长（秒） |
| `TRADING_GAME_SNAPSHOT_INTERVAL` | 300 | 采样间隔（秒），影响图表精度 |
| `TRADING_GAME_CACHE_TTL` | 60 | 行情缓存时长（秒） |

### 想玩温和一点

默认是「赌场模式」：10000 倍杠杆下价格反向 0.01% 就爆仓，保证金全亏。想收敛：

```bash
TRADING_GAME_MAX_LEVERAGE=20
TRADING_GAME_MAINTENANCE_MARGIN=50   # 亏一半就平仓
```

## 数据来源

全部使用免费公开接口，**不需要任何 API key**：

| 资产 | 来源 |
|---|---|
| 股票 | Yahoo Finance（非官方接口） |
| 加密货币 | CoinGecko |
| 外汇 | Frankfurter（欧洲央行数据），备用 open.er-api.com |

这些接口**不保证稳定**，Yahoo 和 CoinGecko 在国内访问可能不通。项目内置了缓存与降级：

- 取不到价格时**拒绝成交**（不会以 0 元成交）
- 接近强平的仓位会强制拉取实时价
- 采样器每 5 分钟主动抓一次，闲置时行情不会冻结

## 技术栈

- **后端**：FastAPI + SQLite，单容器，无外部依赖
- **前端**：原生 HTML/CSS/JS + Chart.js（已内置到 `web/vendor/`），无构建步骤
- **后台任务**：4 个 asyncio 循环（强平 / 资金费 / 采样 / 赛季轮换）
- 整套约 5000 行代码，256MB 内存的机器就能跑

## 文档

| 文件 | 内容 |
|---|---|
| [LOCALIZATION.zh.md](LOCALIZATION.zh.md) | 汉化实现、如何加新语言 |
| [DERIVATIVES.zh.md](DERIVATIVES.zh.md) | 杠杆/保证金/永续/期货/做空的公式与设计理由 |
| [SEASONS_AND_DASHBOARD.zh.md](SEASONS_AND_DASHBOARD.zh.md) | 赛季、采样、日报、动态流、首页 |
| [API_CONTRACT.md](API_CONTRACT.md) | 接口契约 |
| [ROADMAP.md](ROADMAP.md) | 上游的待办清单 |

## 测试

```bash
./.venv/bin/python scripts/smoke_test.py http://127.0.0.1:8000
```

覆盖 109 项：认证流程、现货交易、做空、杠杆开平仓、强平、资金费、赛季轮换、采样、动态流、越权保护。

### 离线模式

测试默认会请求真实行情接口，这在 CI 里不可靠（Yahoo / CoinGecko 会限流数据中心 IP）。设置 `TRADING_GAME_OFFLINE=1` 后，行情层会切换到**确定性桩数据**：

```bash
TRADING_GAME_OFFLINE=1 TRADING_GAME_DB=/tmp/t.db ./run.sh
./.venv/bin/python scripts/smoke_test.py http://127.0.0.1:8000
```

价格由 symbol 哈希推导，每次运行都一样（BTC 固定 65000、AAPL 固定 190），历史曲线是平滑的伪随机游走。这样测的是**结算逻辑、强平数学、赛季轮换**，而不是"今天第三方接口通不通"。

同一套测试在两种模式下都是 109/109 通过。

### CI

| Workflow | 触发 | 做什么 |
|---|---|---|
| `tests.yml` | push / PR | Python 3.10 和 3.12 双版本跑离线冒烟测试；另有一个 job 校验桩数据契约 |
| `docker.yml` | push / PR / tag | 构建多架构镜像推到 GHCR；PR 时只构建不推送，并启动容器做健康检查 |
| `codeql.yml` | 上游自带 | 代码安全扫描 |

CI 里没有任何步骤依赖真实行情，所以不会因为外部接口抖动而随机变红。

## 安全提醒

这是一个**家庭/朋友局域网游戏**，不是产品：

- 密码用 PBKDF2 加盐哈希，但**没有 HTTPS**
- 会话 token 永不过期
- 没有限流
- 不要把它直接暴露到公网，除非自己套一层反向代理 + TLS + 访问控制

## 协议

MIT，见 [LICENSE](LICENSE)。

上游版权归 **M1XZG** 所有（Copyright © 2026）。本仓库的扩展部分同样以 MIT 发布。

## 已知边界

- 强平靠轮询（默认 2 秒），极端行情下可能滞后于真实价格
- 没有订单簿，所有成交按最新价即时全额撮合，大单不影响价格
- 赛季重置会清空所有持仓，不做二次确认
- 动态流不分房间，所有人混在一起
- `overtake` 提醒的排名基线存在内存里，服务重启后第一次不发提醒
