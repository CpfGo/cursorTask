# A股2026主线识别系统

同花顺数据增强 + 集合竞价强弱 + Serenity产业链卡点 + HTML 网页报告。

本仓库实现规格 **V6.7**（规格正文标题为 V6.5）描述的完整主线识别流水线：优先使用同花顺数据源，接口不可用时自动切换其他可用行情源并**明确标注来源**；所有无法验证的字段一律标记 `DATA_MISSING`，不用猜测补全。系统不给出买卖指令，只输出资金强度、主线地位、风险方向和仓位环境。

## 核心原则

集合竞价强弱 → 盘中资金流向 → AI 内部产业链归类 → 产业链卡点 → 主线强度 → 资金运作阶段 → 仓位

硬性约束（摘录）：

- 结论必须基于当日拉取的数据，而不是新闻印象或历史龙头记忆。
- 不要求用户提供板块或产业链分类，系统根据行业、概念、资金、涨停结构、主营标签自行归类。
- 同一只股票只归入一个主产业链。
- 涨幅只作辅助指标，不能单独决定主线或龙头。
- 「洗盘 / 打压 / 出货」只作为由成交额、换手、资金流、梯队、赚钱效应共同验证的交易结构标签。
- 最终产物是可保存的单文件 HTML 报告，标题为 **A股主线识别日报**。

## 架构

```
config/settings.yaml          数据源优先级、评分权重、交易时段
src/ashare2026/
  data/                       同花顺优先 + 东方财富/新浪兜底
  classify/                   产业链归类（当日资金标签，不套固定龙头）
  pipeline/step0..step11      规格 STEP0–STEP11
  scoring/                    竞价 100 分、主线加权、赚钱效应 0–5
  report/html.py              单文件深色交易台 HTML
  api/app.py                  FastAPI + 控制台 UI
```

流水线步骤：

| 步骤 | 模块 | 内容 |
|---|---|---|
| STEP0 | 集合竞价强弱 | 9:15–9:30 优先竞价；过 9:30 用开盘后数据复盘并标注 |
| STEP1 | 市场环境 | 主升浪 / 震荡轮动 / 高位退潮 / 系统风险 四选一 |
| STEP2 | 板块资金与成交额 | 行业/概念 TOP20、即时资金、3日/5日连续性 |
| STEP3 | Serenity 卡点 | 先排序产业链层级，再给稀缺环节与证据强度 |
| STEP4 | 龙头识别 | 总龙头 / 中军 / 补涨 |
| STEP5 | 梯队与赚钱效应 | 结构标签 + 0–5 分 |
| STEP6 | ETF 资金 | 按产业链自动匹配代表 ETF |
| STEP7 | 产业周期与资金阶段 | 周期与建仓→出货路径 |
| STEP8 | 主线评分 | 成交额 25 + 即时资金 20 + 连续性 15 + 龙头 15 + 梯队 10 + ETF 10 + 赚钱效应 5 |
| STEP9 | 最弱方向 | 退潮/兑现/分歧/低开/流出 |
| STEP10 | 仓位 | 激进 80–100% / 正常 50–80% / 谨慎 20–50% / 防守 0–20% |
| STEP11 | 反证条件 | 对前三主线给出可证伪条件 |

## 数据源优先级

规格中的同花顺源按 1–10 依次尝试：

1. 全A涨跌幅排行 `https://data.10jqka.com.cn/market/zdfph/`
2. 行情中心 `https://q.10jqka.com.cn/`
3. 涨停雷达 `https://yuanchuang.10jqka.com.cn/mrnxgg_list/`
4. 概念板块 `https://q.10jqka.com.cn/gn/`
5. 行业板块 `https://q.10jqka.com.cn/thshy/`
6. 个股实时资金
7. 概念即时流入
8. 概念 3 日流入
9. 概念 5 日流入
10. 7x24 消息（只验证催化，不作为强弱主依据）

同花顺网页接口若返回 401/403，系统会改用东方财富 delay 行情、涨停池等备用源，并在报告「数据源与可用性」中写明实际来源。概念 3 日 / 5 日资金按浏览器方式拉取同花顺 `gnzjl` 资金表（先打开父页、带 `hexin-v`、`Referer`、`X-Requested-With`，并尝试 `/free/1/`），解析真实表格行；**解析不到行时标记 `DATA_MISSING`，不会用 5 日数据冒充 3 日，也不会编造净额。** 涨停原因只采用涨停雷达/复盘原文中出现的股票与题材，不用行业字段冒充。

## 安装

Python 3.11+。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 使用

生成 HTML 日报：

```bash
python -m ashare2026 report -o reports/daily.html
```

检查数据可用性：

```bash
python -m ashare2026 check
```

启动控制台与 API（深色交易台首页，可一键生成报告）：

```bash
python -m ashare2026 serve --port 8000
```

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 控制台 UI |
| GET | `/health` | 健康检查 |
| GET | `/api/v1/availability` | 数据可用性表 |
| POST | `/api/v1/analyze` | 拉取行情并识别主线 |
| GET | `/api/v1/report` | 最新 HTML 报告 |
| GET | `/api/v1/result` | JSON 结果 |

## HTML 报告

- 单文件：HTML + CSS + JS，不依赖 CDN / 外部字体 / 外部图片。
- 首屏：竞价最强板块、市场第一主线、最弱方向、市场状态、推荐仓位。
- 交互：模块折叠、数值列排序、右侧锚点、高亮最高分产业链与竞价最强/最弱、表格悬停、移动端压缩卡片。
- 红涨绿跌，金色主线，灰色 `DATA_MISSING`。

## 测试

```bash
pytest
```

测试使用夹具行情，不依赖交易时段，覆盖评分分档、一股一链、3 日资金不得编造、HTML 必选章节、API。

## Windows 本机启动（有 Python）

已安装 Python 3.11+ 时，双击仓库根目录的 `启动.bat`：

1. 进入脚本所在目录
2. 若无 `.venv` 则创建
3. 激活虚拟环境；仅当 `ashare2026` / `tzdata` / `uvicorn` 无法导入时执行 `pip install -e ".[dev]"`
4. 打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)
5. 运行 `python -m ashare2026 serve --port 8000`

关掉黑色控制台窗口即停止。控制台使用 UTF-8（`chcp 65001`）。**需要联网**拉取行情。未安装 Python 时请用下面的 `.exe`。

## Windows 可执行文件

无需安装 Python。GitHub Actions 在 `windows-latest` 上用 PyInstaller 打成 **onedir** 目录（`AShare2026.exe` + 依赖文件），产物作为工作流 Artifacts 上传，并在 PR 评论中附下载链接。

### 从 Actions 下载

1. 打开 [GitHub Actions：a-share-2026-tests](https://github.com/CpfGo/cursorTask/actions/workflows/a-share-2026.yml)。
2. 选中一次成功的运行（含 job **windows-exe**）。
3. 页面底部 **Artifacts** 下载 `AShare2026-windows`（zip，默认保留 30 天）。
4. 解压后**整夹保留**，双击 `AShare2026.exe`（不要只拷走这一个文件）。
5. 浏览器打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。关掉黑色控制台窗口即停止服务。

也可在对应 Pull Request 的评论里点本次运行链接。

### 本地打包（须在 Windows 上）

已安装 Python 3.11+ 时，双击仓库根目录的 `打包exe.bat`：

1. 进入脚本所在目录，控制台使用 UTF-8（`chcp 65001`）
2. 若无 `.venv` 则创建并激活
3. `python -m pip install -e ".[pack]"`
4. `python -m PyInstaller ashare2026.spec --noconfirm`（用 `python -m`，不要用未加入 PATH 的裸 `pyinstaller` 命令）
5. 成功后打印 `dist\AShare2026\AShare2026.exe`，并打开 `dist\AShare2026` 文件夹

关掉黑色控制台窗口前会 `pause`。产物路径：`dist\AShare2026\AShare2026.exe`。双击 exe 后打开 http://127.0.0.1:8000 。

等价的手动命令：

```bat
cd /d 本仓库根目录
chcp 65001
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -e ".[pack]"
python -m PyInstaller ashare2026.spec --noconfirm
explorer dist\AShare2026
```

命令行仍可带子命令（与 `python -m ashare2026` 相同）：

```bat
AShare2026.exe serve --port 8000
AShare2026.exe report -o reports\daily.html
AShare2026.exe check
```

### 限制

- 可执行文件**需要联网**才能拉取同花顺 / 东方财富行情；无网时报告会标 `DATA_MISSING`。
- 未签名，Windows SmartScreen 或杀毒软件可能拦截，需选择「更多信息 → 仍要运行」。
- 必须保留解压后的整个目录（`_internal` 等），单独复制 `.exe` 无法启动。
- Linux / macOS 环境打不出真正的 Windows `.exe`；请用上述 Actions 产物或在 Windows 上本地打包。
- Artifact 会过期（当前 30 天），过期后重新跑工作流即可。

## 仓位与免责

仓位只有四种环境判断，不是下单指令。激进/正常/谨慎/防守的触发条件写在报告「仓位判断」中。若实时数据不足，首屏和右侧导航区域会显示：

`DATA_MISSING：实时数据不足，以下结论仅基于可用数据，不进行无法验证的判断。`
