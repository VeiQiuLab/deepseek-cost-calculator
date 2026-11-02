# DeepSeek API 费用计算器（Windows / Python）

中文 Tkinter 桌面程序。完全离线，不需要 API Key，不读取账号、不请求模型、不产生 API 消费。运行仅依赖 Python 标准库；exe 包含运行环境。

## 快速使用

如果有 `DeepSeekCalculator.exe`，直接双击。源码运行：安装 **Python 3.10 或更新版本**（推荐官方 python.org Windows 安装版，包含 Tcl/Tk），解压源码后双击 `run.bat`，或运行：

```powershell
py -3 app.py
```

若 Python 没注册给 `py`，在命令提示符设定 `set "PYTHON_EXE=C:\完整路径\python.exe"` 后运行脚本。路径包含中文和空格可以使用。

1. 选择 Flash/Pro 的高峰或非高峰预设，或直接编辑三项单价。单位是**美元 / 百万 Tokens**。
2. 填入汇率、预算和估算轮数。默认人民币汇率 `7.00` **只是示例值**，没有自动获取实时汇率。
3. 在“对话与上下文”设置输入、回答、思考 Tokens、历史和命中率。回答数不含思考，以免重复计费。
4. 在“工具费用”填写每轮平均成功 Search/Fetch 次数、第三方调用次数及费用；再填送回模型的工具返回 Tokens。
5. 点击“计算 / 反推预算”，查看累计曲线和逐轮费用；横向滚动明细可见各项费用。CSV 包含全部轮次，使用 UTF-8 BOM，便于 Excel 打开。参数可以保存、载入 JSON。

编辑参数后需要重新点击计算。曲线和 CSV 始终对应最后一次成功计算；载入参数后会自动计算。切换模型预设会覆盖三项模型单价，其他参数保持当前值。

## 价格快照与依据

核对日期：**2026-10-30**。不自动联网更新；将来变化时手动改价。

| 模型情景 | 命中输入 USD/百万 | 未命中输入 USD/百万 | 输出 USD/百万 |
|---|---:|---:|---:|
| Flash 非高峰 | 0.003 | 0.15 | 0.6 |
| Flash 高峰 | 0.006 | 0.3 | 1.2 |
| Pro 非高峰 | 0.022 | 0.66 | 1.98 |
| Pro 高峰 | 0.044 | 1.32 | 3.96 |

在 2026-10-30 原价格快照中，Flash API 名称为 `deepseek-flash`，Pro 为 `deepseek-v4-pro`。高峰为非中国法定节假日的周一至周五北京时间 09:00–12:00、14:00–18:00，其他时间按非高峰。程序使用所选情景贯穿整段对话，不自动判断节假日或混合跨时段价格。

Search、Fetch 各为 **0.75 美元 / 千次成功且有结果的请求**，不是按返回结果数量计费。经 DeepSeek Harness / Claude Code / Codex 的服务端工具调用，原快照记载当时免费，**2026-11-01 北京时间 00:00 起收费**。程序默认使用收费情景；适用豁免时手动勾选“Search/Fetch 免费情景”。其他第三方工具不受该开关影响。

官方来源：

- [Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/)
- [Search & Fetch](https://api-docs.deepseek.com/guides/search/)
- [Context Caching](https://api-docs.deepseek.com/guides/kv_cache/)
- [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)

## 公式及适用范围

每轮按“一次用户输入 + 一次模型请求/生成”的固定平均情景计算。从空历史开始。

记：`U` 用户新输入，`A` 可见回答，`T` 思考，`S` 固定提示，`X` 本轮工具返回；`W` 窗口，`L` 手动历史上限（0 表示不额外限制）。

```text
基础输入 B = S + U + X
本轮输出 O = A + T
增长量 G = U + X + A + (勾选保留历史思考时的 T)
关闭携带历史时 G = 0
历史上限 C = W - B - O，再与 L（非零时）取较小值
第 i 轮历史 H_i = min((i-1) × G, C)
第 i 轮输入 I_i = B + H_i
```

窗口为**输入加输出的总预算**，先为输出预留空间。如果 `B+O>W`，拒绝输入，不偷偷裁剪新输入。只按 Token 数模拟滑动截断；不模拟消息边界、摘要成本、tokenizer、模型输出长度上限或服务端拒绝策略。窗口及 Tokens 均可自定义，计算器不负责检查特定 API 的所有参数上限。

首轮按冷缓存，即命中 0。后续轮的预计可命中前缀为 `S+H_i`，不把新用户输入和新工具返回当成命中。命中量 = 可复用前缀 × 命中率；未命中量 = 输入 − 命中。默认截断后命中降为 0，因为滑动截断会改变前缀；只有确认仍能复用时才启用“截断后仍按命中率估算”。缓存是概率情景，不是 TTL/前缀匹配模拟；100% 也不是保证。允许小数命中 Tokens，表示期望值。

普通无 tools 的多轮对话不将以往思考拼入上下文，因此默认不保留；携带 tools 的调用可能需要保留，手动勾选。

```text
模型 USD = (命中 Tokens × 命中价 + 未命中 Tokens × 未命中价 + O × 输出价) / 1,000,000
工具 USD = Search次数 × Search价 / 1,000 + Fetch次数 × Fetch价 / 1,000
           + 第三方次数 × 第三方每次价
每轮 CNY = (模型 USD + 工具 USD) × 汇率 + 其他每轮固定 CNY
累计费用 = 每轮费用之和
```

“其他每轮固定费用”可填第三方人民币收费或其他自定义成本；不要把已经按美元填过的费用再填一次。本版本没有赠送余额、免费 Token 配额、缓存写入价、税费或充值手续费的自动规则。预算可以填实际可用余额。缓存命中率不是免费 Token 额度。

工具代理可能在一轮内多次请求模型：每次都有输入、输出费用。此程序不会仅凭工具次数推断中间模型请求；应先合计其 usage 并选择合适情景，或分段计算。当前单次输入 `X` 的处理是简化预算模型，不能当成复杂工具循环的精确账单重放。

使用 Decimal，逐轮不做货币舍入；界面显示 8 位小数，CSV 保留计算值。没有把显示值再用于预算比较。预算反推用累计函数和二分搜索，返回累计不超预算的最大完整轮数；轮数搜索上限为 `10^12`，达到时显示 `≥`，免费情景也不武断声称无限。估算轮数与完整 CSV 上限为 100000；表格超过 500 轮只显示前后各 250 轮，曲线最多抽样约 600 点。极端输入存在 Decimal 默认 28 位有效数字的精度边界；日常预算不受界面舍入影响。

## 一键打包 exe

双击 `build.bat`。脚本会在源码旁创建独立 `.venv-build`，安装固定版本 PyInstaller，运行公式测试及真实 Tk 窗口启动检查，然后构建：

```text
dist\DeepSeekCalculator.exe
```

首次打包需要联网安装构建依赖。`requirements.txt` 引用构建依赖；**普通运行不需要 pip install**。打包不修改全局 Python 环境。出现错误脚本会停止并保留消息。

手动执行等价步骤：

```powershell
py -3 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv-build\Scripts\python.exe -m unittest discover -v
.\.venv-build\Scripts\python.exe app.py --smoke-test
.\.venv-build\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --additional-hooks-dir hooks --name DeepSeekCalculator app.py
Start-Process -Wait .\dist\DeepSeekCalculator.exe -ArgumentList '--smoke-test'
```

必须在 Windows 上构建 Windows exe，不能直接用 Linux 打包为 Windows。exe 未进行代码签名；若要组织内部签名发布，请按组织流程另行处理。首次单文件启动会解压运行依赖，可能比源码启动慢。

## 测试与文件

`py -3 -m unittest discover -v` 执行标准库 unittest：手算首轮、缓存拆分、截断边界、历史开关、思考保留、工具单位换算、预算恰好够用/下一轮不足、零预算/零费用、非法值，另有 300 组固定随机种子的独立逐轮计算对照。

- `app.py`：GUI、曲线、CSV/参数导入导出
- `cost_model.py`：独立费用模型和预算反推
- `test_cost_model.py`、`test_gui.py`：公式和 GUI 测试
- `run.bat`、`build.bat`：启动与打包
- `hooks/`：便携 Windows Python 的 Tcl 检测兼容；检测不到 Tk 时拒绝打包
- `VALIDATION.md`：本次实测证据与未覆盖项

只有用户点击保存/导出时才写参数和明细文件。没有后台网络、API Key、账户登录或自动读取私有数据。

## GitHub 安装、构建附件与协议

预编译 Windows 包位于本仓库 [Releases](../../releases)，完整解压 ZIP 后启动 EXE。Git 的源码下载不含 EXE。CI 在 Windows 跑公式与 Tk 测试、构建并自检 EXE，产物作为 Actions 附件保存。

本次只归档已有计算器，不更新内置价格；所有价格、免费政策与汇率均按历史情景处理，使用前应查看 DeepSeek 官网并手动调整，不能视为当前报价或实际账单。

自有源码采用 [MIT](LICENSE)，第三方保留 [原协议](THIRD_PARTY_NOTICES.md)。[本次验证](VALIDATION.md) 和 [归档说明](docs/ARCHIVE.md) 说明覆盖边界。
