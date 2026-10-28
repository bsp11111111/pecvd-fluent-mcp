# Codex 桌面版：按你当前状态继续操作

适用状态：已在 Windows 运行安装和检测，截图显示 Python 3.11.9、MCP 1.29.0、PyFluent 0.26.1，Fluent 2024 R1 已找到。

## 1. 已完成的步骤可以跳过

你已完成 Python 安装、`01_Install.cmd` 和 `02_Check.cmd`。保持当前工程目录，无需重新安装，也无需因为下载新版手册就重新解压工程。

当前工程目录是：

```text
E:\新建文件夹 (2)\pecvd-fluent-mcp-main\pecvd-fluent-mcp-main
```

当前已识别的 Fluent 是：

```text
E:\Program Files\ANSYS Inc\v241\fluent\ntbin\win64\fluent.exe
```

## 2. 只修改 Codex 的配置

在资源管理器地址栏打开 `%USERPROFILE%\.codex`，用文本编辑器打开 `config.toml`。如果 Codex 使用了自定义配置目录，请打开它实际使用的配置文件。

保留已有的其他配置。若之前已添加 `pecvd-fluent`，替换它的两个区块，避免重复定义；若没有，在末尾追加下面的内容：

```toml
[mcp_servers.pecvd-fluent]
command = 'E:\新建文件夹 (2)\pecvd-fluent-mcp-main\pecvd-fluent-mcp-main\.venv\Scripts\python.exe'
args = ["-m", "pecvd_mcp.server"]
startup_timeout_sec = 60
tool_timeout_sec = 600

[mcp_servers.pecvd-fluent.env]
PECVD_WORKSPACE = 'E:\新建文件夹 (2)\pecvd-fluent-mcp-main\pecvd-fluent-mcp-main\runs'
PECVD_PACKAGE_ROOT = 'E:\新建文件夹 (2)\pecvd-fluent-mcp-main\pecvd-fluent-mcp-main'
```

注意：

- `command` 指向工程内的 `.venv\Scripts\python.exe`，不是 Fluent 可执行文件。
- TOML 的单引号内，反斜杠保持一个即可，保留中文、空格及括号。
- 两层同名文件夹与截图相符，不要删去一层。
- `mcp-config.generated.json` 不直接粘贴进这个 TOML 文件。
- 如果路径已改变，按新的真实路径修改这三个路径字段。

配置字段参考：OpenAI Codex 官方配置 Schema 中的 `mcp_servers`、`command`、`args`、`env`、`startup_timeout_sec` 和 `tool_timeout_sec`：<https://github.com/openai/codex/blob/main/codex-rs/core/config.schema.json>。

## 3. 重启 Codex，先确认一次真实工具调用

保存配置，完全退出并重新打开 Codex，使用运行在同一台 Windows 电脑上的本地会话。不要把上述路径配置到云端或 WSL/Linux 执行环境中。

发送：

> 请列出 pecvd-fluent 的可用工具，并实际调用 check_environment，返回检测结果。

验收结果：Codex 实际调用工具，返回 Windows、Python 版本、Fluent 路径与工程目录。若只显示一段 Python 代码、说“可以调用”或复述工具说明，还不能算连接成功。

`phase: disconnected` 和 `license_verified: false` 不表示此步失败。它们表示尚未启动本桥管理的 Fluent，本次许可证还没有验证。

如果显示没有此工具或服务启动失败，先检查配置文件是否加载、Python 路径是否存在、是否重复定义同名区块，保存客户端错误信息再排查。此时不必重新安装 ANSYS。

## 4. 连接成功后再启动测试

发送给同一个 Codex 本地会话：

> 使用 pecvd-fluent 工具，读取 read_paper_baseline，创建新项目 first_check_01，生成 baseline 网格，启动 Fluent 2024 R1 的二维双精度界面。载入网格，读取 mesh-check.trn，确认体积为正、没有拓扑错误后，配置非反应连接测试并初始化。先迭代 25 步，读取日志并保存真实 case/data。项目若已存在，用新的项目名；结果标为连接测试，不称为等离子体或沉积验证。

这一阶段应由工具新启动一个 Fluent 进程。可以保留自己已打开的其他工程；本桥不接管那些进程。客户端如要求确认工具调用，按实际操作核对后处理即可。

按主手册第三节的工具顺序进行；网格检查有错误时先处理错误，不继续求解。原生 Fluent 的边界赋值、初始化与保存还需要在本机实际验收；迭代步数完成也不自动代表收敛。

## 5. 查看输出

项目默认输出到：

```text
E:\新建文件夹 (2)\pecvd-fluent-mcp-main\pecvd-fluent-mcp-main\runs\first_check_01
```

检查网格日志、迭代日志和实际保存的 `connection-test-*.cas.h5` 及对应 data。保存之后再关闭本桥管理的 Fluent。

## 6. 哪些部分目前还没完成

当前先验证 Codex 能控制 Fluent，测试模型是非反应的极板间隙替代物。完整匀流腔、多孔层、等离子体方程、活性粒子反应输运、表面沉积和论文图 4 验证仍需继续实现。

因此不需要让 Codex 根据空模板编造电子密度或沉积曲线。后续研究模型任务按 `建模依据与阶段任务.md` 推进。
