# PECVD Fluent 2024 R1 本地 MCP 接入包

## 下载到电脑

登录有仓库访问权限的 GitHub 账号，打开 <https://github.com/bsp11111111/pecvd-fluent-mcp>，点击绿色 **Code → Download ZIP** 即可下载整个项目。

也可以打开 [整理好的安装压缩包](https://github.com/bsp11111111/pecvd-fluent-mcp/blob/main/downloads/pecvd-fluent-mcp-2024R1.zip)，点击文件页右上方的 **Download raw file** 下载图标。Word 手册在 [docs/Windows安装操作手册.docx](docs/Windows安装操作手册.docx)。

下载后完整解压，在包含 `01_Install.cmd` 的目录开始操作；无需下载单独的源代码文件。

适用你的环境：ANSYS 2024 R1 可以正常打开，尚未配置 MCP。版本 0.1.0，2026-10-28。

**本包是可运行的本地接入代码、简化网格与课题基准资料。当前交付尚未在你的电脑上运行 Fluent，也没有生成等离子体分布、沉积速率预测或图 4 的验证结果。** 本机安装并连接 MCP 客户端后，客户端中的助手才能调用你电脑上的求解器。本对话的云环境没有到你电脑的连接。

## 一、今天先完成连接

1. 将整个压缩包解压到例如 `C:\PECVD\pecvd-fluent-mcp`。不要只取出一个脚本。建议路径用英文，保留完整目录。
2. 从 <https://www.python.org/downloads/windows/> 安装 **Python 3.11 64 位**，包含 Python Launcher。不要使用 ANSYS 自带 Python 安装这些依赖。
3. 双击 `01_Install.cmd`。它会创建本工程自己的 `.venv`、安装 MCP 和固定版本 PyFluent，并生成 `mcp-config.generated.json`。首次安装需要联网，窗口最后应显示 `Installed`。不需要改 PowerShell 执行策略。
4. 双击 `02_Check.cmd`，查看 `environment-report.json`。`fluent_executable` 应是实际存在的 `fluent.exe` 路径；`dependencies` 应显示 `mcp: 1.29.0`、`ansys-fluent-core: 0.26.1`。
5. 如果找不到 Fluent，把 `local-config.example.json` 复制为 `local-config.json`，把路径改成真实安装路径，再运行检测。JSON 中反斜杠写成 `\\`。

默认寻找：环境变量 `AWP_ROOT241` 对应路径，或 `C:\Program Files\ANSYS Inc\v241\fluent\ntbin\win64\fluent.exe`。软件能手动打开并不保证自动化启动能借到许可证，许可证以实际启动结果为准。

固定旧版 PyFluent 是为了兼容 2024 R1：开发时核实 `0.26.1` 的版本枚举包含 `24.1`，而 `0.43.0` 已不包含。不要把安装命令改成无版本限制的最新版。

## 二、选一个支持本地 MCP 的客户端

一个可选入口是 **Claude Desktop Windows 桌面版**。需自行安装并登录有权使用的客户端；账号权限和功能以其当前版本为准。本接入包不包含任何账号或订阅。

在支持本地 STDIO MCP 的客户端中添加服务：

- 名称：`pecvd-fluent`。
- 启动命令：本工程 `.venv\Scripts\python.exe` 的完整路径。
- 参数：`-m pecvd_mcp.server`，这是两个参数，不是一个含空格的参数。
- 环境变量：按 `mcp-config.generated.json` 中生成的实际路径填写。

对使用 JSON 配置的 Claude Desktop，通常可在“设置 → 开发者 → 编辑配置”打开配置文件；Windows 常见位置为 `%APPDATA%\Claude\claude_desktop_config.json`。把生成文件中的 `pecvd-fluent` 服务合并到已有 `mcpServers`，保留你原来的其他服务。完全退出并重启客户端。

Cursor／VS Code 等支持 MCP 的客户端也可使用相同启动命令，配置格式以各自界面为准。**普通聊天网页不会因为在电脑上启动本包就自动获得本地工具。** 必须在实际支持本地 MCP 的客户端中建立连接。

安装生成的配置会像下面这样，但不要照抄示例盘符，应使用你生成文件里的真实路径：

```json
{
  "mcpServers": {
    "pecvd-fluent": {
      "command": "C:\\PECVD\\pecvd-fluent-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "pecvd_mcp.server"],
      "env": {
        "PECVD_WORKSPACE": "C:\\PECVD\\pecvd-fluent-mcp\\runs",
        "PECVD_PACKAGE_ROOT": "C:\\PECVD\\pecvd-fluent-mcp"
      }
    }
  }
}
```

`Start_MCP.cmd` 是另一种启动入口，供支持命令脚本的客户端使用；双击后等待输入是正常的，它不是带按钮的应用程序。MCP 本包只用 STDIO，不需要公网 IP、开放端口或远程桌面密码。

## 三、连接后的第一条指令

把下面这段发给已接入 MCP 的客户端助手：

> 使用 pecvd-fluent 工具。先 check_environment，再 read_paper_baseline。创建一个新项目 first_check_01，生成 baseline 网格，启动 Fluent 2024 R1 的二维双精度界面，载入并检查网格。读 mesh-check.trn，确认没有负体积和拓扑错误后，配置非反应连接测试，初始化，先迭代 25 步并保存 case/data。检查日志，不要把该测试称为等离子体或沉积验证，不要覆盖旧项目。

真实调用顺序：

1. `check_environment()`，确认版本、路径与依赖。
2. `read_paper_baseline()`，读取已摘录工况和缺失项。
3. `create_connection_project("first_check_01")`，生成新网格和项目记录。
4. `launch_fluent("first_check_01")`，启动**单独的新 Fluent 进程**，使用你的本地许可；保留你已打开的其他工程。
5. `load_and_check_gap_mesh("first_check_01")`。
6. `read_project_text("first_check_01", "mesh-check.trn")`。需要实际检查体积、拓扑和单位；有错误就停止，保留日志排查。
7. 检查通过才调用 `configure_nonreactive_connection_test("first_check_01", true)`。
8. `initialize_connection_test("first_check_01")`。
9. `iterate_connection_test("first_check_01", 25)`，读取返回的迭代日志。
10. `save_case_and_data("first_check_01")`，再关闭 `close_managed_fluent()`。

每次迭代最多 500 步。迭代完成只表示命令执行结束，收敛还需检查残差、进出口质量守恒和监测量。退出 MCP 客户端会结束它管理的 Fluent 会话，退出前先保存。

若项目名已存在，换新名，例如 `first_check_02`。需要修改本包源码时，先结束 MCP 和其管理的 Fluent，再修改、重启。移动整个工程后重新运行安装以更新路径。

## 四、连接测试到底算了什么

已实现的几何是 `r=0–165 mm, z=0–15 mm` 的轴对称极板间隙，晶圆边界为 `r=0–150 mm`；Fluent 坐标 `x=z`、`y=r`，单位为米。默认 132×24 四边形单元。包括晶圆、边缘环、轴线、上部等效入口和侧出口。

可选 `baseline`（全开）、`center_open`（r<75 mm 开）、`edge_open`（r>75 mm 开）。它们是图 2 开孔区域的等效入口**连接测试**，没有匀流腔、孔道和多孔阻力，不能用它们代替论文完整反应器并声称复现图 4。

设置采用单一中性理想气体替代物、层流和传热，按 SiH₄/NH₃ 比例换算平均分子量。黏度 `1.2e-5 Pa·s`、比热 `2000 J/(kg·K)`、导热系数 `0.04 W/(m·K)` 是明确标注的数值测试假设，**不是已核实的 SiH₄/NH₃ 物性**。不启用电子、离子、多组分化学反应或表面沉积。

因此该测试用于确认“客户端 → MCP → PyFluent → Fluent → 网格/设置/迭代/真实 case 文件”整条链路可用。开发云环境没有 ANSYS 安装和许可，原生网格检查、Windows GUI 启动及设置赋值仍需在你电脑上实际验收。

## 五、论文基准和真正的研究模型

详细工况、方程路线、待补数据和宏观—微观接口见 `docs/建模依据与阶段任务.md`。基准数据的机器可读文件为 `pecvd_mcp/baseline.json`，含来源页码及标准状态假设。

完整模型还需要建立匀流腔及多孔板，并实现等离子体漂移扩散／电子能量／泊松方程、主要中性粒子反应输运、晶圆表面反应。Fluent 普通流动模块不自动提供这套低温非平衡等离子体模型，需要可靠的 UDS/UDF 或与 COMSOL Plasma 等独立模型交换数据。当前包没有实现这些方程，也没有用预设电子密度替代真实放电。

目前已提供两个数据接口：

- `check_external_plasma_table` 检查真实外部计算的 `r_m,z_m,ne_m3,Te_eV` CSV，只检查格式和范围；不把数据自动插值加载进 Fluent，不代表已验证等离子体物理。
- `convert_actual_wafer_flux_to_deposition` 将**实际净入膜质量通量**转换成沉积速率。需要你提供已求得的通量、薄膜密度和来源说明；不根据入口流量凭空估算沉积。

## 六、输出文件在哪里

所有项目输出默认在工程的 `runs/项目名/`：

|文件|内容|
|---|---|
|`gap.msh`|连接测试的 Fluent ASCII 网格|
|`project.json`|论文工况、来源、换算、模型层级和缺失项|
|`mesh-check.trn`|本地 Fluent 原生网格检查日志，连接后才会产生|
|`connection-test-settings.json`|测试物性假设与边界设置，配置后才会产生|
|`iterations-*.trn`|真实迭代输出，运行后才会产生|
|`connection-test-*.cas.h5` 及对应 data|真实 Fluent 工程和数据，保存后才会产生|
|`operations.jsonl`|本桥管理的操作记录|
|`plasma_template.csv`|空表头，不包含模拟电子密度|
|`wafer_flux_template.csv`|空表头，不包含虚构沉积结果|
|`wafer_deposition.csv`、`deposition_summary.json`|提供真实净通量和密度后得到的单位转换与径向统计|
|`wafer_deposition.svg`|由所提供的径向净通量转换并旋转得到的全片图，轴对称假设，无虚构角向变化|

沉积 CSV 要覆盖 `r=0` 到 `r=0.150 m`。净入膜质量通量不同于任意一种自由基的到壁通量，也不同于包含 H₂ 等副产物的总气相通量。速率换算单位为 nm/min 和 Å/min；论文图 4 使用 Å/min。

## 七、常见问题

|现象|处理|
|---|---|
|找不到 `py -3.11`|安装 Python 3.11 并包含 Python Launcher，重新打开安装脚本|
|依赖下载失败|检查网络、保存报错后重试；不需要关闭证书验证|
|Fluent 路径为空|用 `local-config.json` 指定真实 `fluent.exe`|
|Fluent 启动超时／许可证错误|先手动检查 2024 R1 许可，关闭不需要的测试实例，保留错误文本|
|客户端找不到工具|检查生成配置、完整 Python 路径、服务日志，完全退出并重启客户端|
|启动脚本后窗口没按钮|STDIO 服务等待 MCP 客户端请求；按第二节接入客户端|
|图 4 没有生成|当前没有安装完整反应与表面模型；连接测试不会输出研究沉积结果|
|CSV 出现 NaN／负数／单位不符|按模板提供 SI 坐标、m⁻³ 电子密度、eV 电子温度、kg/(m²·s) 净入膜通量|

提供给后续排查的信息：`environment-report.json`、MCP 客户端错误、当前项目的网格检查和迭代日志。许可证密钥不需要提供。

测试方法见 `tests/`。双周汇报模板位于 `docs/双周汇报模板.md`；本包没有自动每半个月发送汇报的任务，需要在获得阶段工程和日志后更新报告。
