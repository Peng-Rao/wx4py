# wx4py 批量个性化发送网页工具

这是一个基于 [Streamlit](https://streamlit.io/) 和 [wx4py](https://github.com/claw-codes/wx4py) 的 Web 应用程序，可以自动化地批量向微信好友发送个性化的文本消息和文件。

## 功能特点
- 网页可视化操作界面。
- 支持批量处理多个好友备注名单。
- 自动根据好友备注提取称呼（支持提取破折号后的名字并去除姓氏）。
- 支持自定义消息模板（使用 `{name}` 占位符）。
- 支持添加单个文件附件，将与消息一并发送。

## 环境要求
- 操作系统：Windows 10/11
- Python 3.9+
- 微信客户端 4.x（已测试 4.1.7.59, 4.1.8.29）

## 安装依赖
一条命令同时安装 `wx4py` 和 Web 端所需的 `streamlit`（通过 `web` extras）：

```bash
pip install "wx4py[web]"
```

如果你是直接克隆了仓库做开发，使用：

```bash
pip install -e ".[web]"
```

## 运行方法

### 方式一：克隆仓库后启动（推荐做开发或第一次体验）

**Windows（PowerShell / CMD）：**

```bash
git clone https://github.com/claw-codes/wx4py.git
cd wx4py
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[web]"
streamlit run examples/web/streamlit_bulk_sender.py
```

**macOS / Linux（仅 UI 演示模式，真实发送需要 Windows）：**

```bash
git clone https://github.com/claw-codes/wx4py.git
cd wx4py
python -m venv .venv
source .venv/bin/activate
pip install -e ".[web]"
streamlit run examples/web/streamlit_bulk_sender.py
```

> 之后每次回到这个项目，先 `cd wx4py` 再激活虚拟环境（Windows 用 `.venv\Scripts\activate`，macOS/Linux 用 `source .venv/bin/activate`），然后直接 `streamlit run examples/web/streamlit_bulk_sender.py`。

### 方式二：纯 pip 安装后启动（不克隆仓库）

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
.venv\Scripts\activate
pip install "wx4py[web]"
# 把这个示例文件下载到本地任意目录后运行，或直接克隆仓库取该文件
streamlit run examples/web/streamlit_bulk_sender.py
```

### 自定义端口（可选）

```bash
streamlit run examples/web/streamlit_bulk_sender.py --server.port 8502
```

运行后，你的默认浏览器将会自动打开该网页工具（默认地址 `http://localhost:8501`）。停止服务在终端按 `Ctrl+C`。

## 使用说明
1. **接收好友名单**：在文本框中输入需要发送的好友备注（每行一个）。例如：`25届初二-郑子轩妈妈`。
2. **消息模板**：输入你想发送的消息内容，并在需要称呼的地方使用 `{name}`。例如：`{name}，下午好🌞`。
3. **附加文件**：点击“Browse files”选择你要附带发送的文件（可选）。
4. **开始发送**：点击蓝色的 `🚀 开始发送` 按钮。程序将自动调用电脑上的微信客户端依次给名单上的好友发消息。

> **注意**：发送过程中，请保持微信窗口在电脑前台，不要随意用鼠标点击微信界面，以免干扰自动化操作。
