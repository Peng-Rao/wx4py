# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import tempfile
import os

# 确保能导入根目录的 src/wx4py
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="wx4py 批量个性化发送工具", page_icon="💬", layout="wide")

try:
    from src import WeChatClient
except Exception:
    # 兼容 MacOS 演示环境
    import time
    class MockChatWindow:
        def send_to(self, *args, **kwargs):
            time.sleep(0.3)
        def send_file_to(self, *args, **kwargs):
            pass
        def send_message_and_file_to(self, *args, **kwargs):
            time.sleep(0.3)
        def upload_files_to_helper(self, *args, **kwargs):
            time.sleep(0.3)
            return True
        def forward_recent_merge_to(self, *args, **kwargs):
            time.sleep(0.3)
            return True
    class WeChatClient:
        def __init__(self, **kwargs):
            self.chat_window = MockChatWindow()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def disconnect(self):
            pass
    st.warning("⚠️ 检测到非 Windows 环境或未安装 pywin32。当前已进入 **UI 演示模式**，所有发送操作仅做界面模拟，不会真正发送微信消息。")

st.title("wx4py 批量个性化发送工具")
st.markdown("通过网页版自动化给微信好友批量发送带称呼的专属消息和文件。")

st.sidebar.header("配置区")
st.sidebar.markdown("""
**支持的微信版本**：
本项目目前支持微信 **4.x** 版本（已测试 4.1.7.59, 4.1.8.29）。
使用前请确保电脑已登录并打开微信。
""")


# 常见家长称谓后缀，按长度倒序匹配避免短的吃掉长的
_PARENT_SUFFIXES = (
    "妈妈", "爸爸", "家长", "奶奶", "爷爷",
    "外公", "外婆", "姑姑", "舅舅", "阿姨", "叔叔",
)


def extract_greeting_name(remark: str) -> str:
    """
    根据备注提取称呼。

    步骤：
    1. 取破折号后的部分作为"姓名+称谓"段（无破折号则用原文）。
    2. 识别尾部称谓（妈妈/爸爸/家长 等），拆出"学生姓名"。
    3. 仅当**学生姓名恰好 3 字**时认为是"单姓 + 2 字名"，去掉首字（姓氏）。
       其他长度（2 字名、4 字复姓名、更长）一律保留全称，避免误切复姓。

    示例：
        "25届初三-罗雅鹭妈妈"   -> "雅鹭妈妈"   （3 字名，去姓）
        "25届初二-郑子轩妈妈"   -> "子轩妈妈"   （3 字名，去姓）
        "张永琪爸爸"            -> "永琪爸爸"   （3 字名，去姓）
        "欧阳永琪爸爸"          -> "欧阳永琪爸爸"（4 字复姓，全称）
        "王明妈妈"              -> "王明妈妈"   （2 字名，全称）
        "司马相如"              -> "司马相如"   （4 字复姓且无称谓，全称）
        "王小明"                -> "小明"       （3 字名且无称谓，去姓）
    """
    remark = remark.strip()
    if not remark:
        return ""

    if "-" in remark:
        name_part = remark.split("-")[-1].strip()
    elif "—" in remark:  # 中文破折号
        name_part = remark.split("—")[-1].strip()
    else:
        name_part = remark

    # 识别称谓后缀
    suffix = ""
    student_name = name_part
    for s in sorted(_PARENT_SUFFIXES, key=len, reverse=True):
        if name_part.endswith(s) and len(name_part) > len(s):
            suffix = s
            student_name = name_part[: -len(s)]
            break

    # 仅在"单姓 + 2 字名" => 学生姓名 3 字时去姓
    if len(student_name) == 3:
        return student_name[1:] + suffix

    return name_part


# ==================== 会话状态 ====================
# phase: 'idle' | 'running' | 'paused' | 'done'
DEFAULTS = {
    "phase": "idle",
    "friends_queue": [],
    "next_index": 0,
    "total": 0,
    "message_template": "",
    "use_forward": False,
    "temp_file_paths": [],
    "temp_dir_for_files": None,
    "helper_uploaded": False,
    "results": [],   # [{friend, greeting, status, detail}]
    "wx_client": None,
    "fatal_error": "",
}
for _k, _v in DEFAULTS.items():
    st.session_state.setdefault(_k, _v)


def cleanup_temp_files():
    for path in st.session_state.temp_file_paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    tdir = st.session_state.temp_dir_for_files
    if tdir and os.path.isdir(tdir):
        try:
            os.rmdir(tdir)
        except Exception:
            pass
    st.session_state.temp_file_paths = []
    st.session_state.temp_dir_for_files = None


def disconnect_wx():
    wx = st.session_state.wx_client
    if wx is not None:
        try:
            wx.disconnect()
        except Exception:
            pass
    st.session_state.wx_client = None


def reset_to_idle():
    """清理状态，回到 idle，准备开下一轮。"""
    disconnect_wx()
    cleanup_temp_files()
    for k, v in DEFAULTS.items():
        st.session_state[k] = v if not isinstance(v, list) else list(v)


def ensure_wx_client():
    """懒加载 WeChatClient，缓存在 session_state 里跨 rerun 复用。"""
    if st.session_state.wx_client is None:
        st.session_state.wx_client = WeChatClient(auto_connect=True)
    return st.session_state.wx_client


# ==================== 左侧：输入区 ====================
col1, col2 = st.columns([1.2, 1])

with col1:
    st.header("📝 编辑发送内容")
    st.subheader("1. 接收好友名单")
    friends_input = st.text_area(
        "请输入好友备注名单（每行一个）：",
        value="25届初二-郑子轩妈妈\n张永琪爸爸\n王小明",
        height=150,
        disabled=st.session_state.phase in ("running", "paused"),
    )

    st.subheader("2. 消息模板")
    st.markdown("使用 `{name}` 作为称呼的占位符。程序会自动提取备注中的名字替换它。")
    message_template_input = st.text_area(
        "请输入消息模板：",
        value="{name}，您好！\n\n（请在此处输入您的自定义消息内容...）",
        height=200,
        disabled=st.session_state.phase in ("running", "paused"),
    )

    st.subheader("3. 附加文件（可选，支持多文件合并发送）")
    uploaded_files = st.file_uploader(
        "选择要发送的文件（可一次选择多个，将合并为一条消息发出）",
        accept_multiple_files=True,
        disabled=st.session_state.phase in ("running", "paused"),
    )

    use_forward_mode = st.checkbox(
        "通过『文件传输助手』转发（先上传 1 次，后续好友只走『合并转发』，文案放进留言框）",
        value=False,
        help=(
            "勾选后：文件先发到文件传输助手，每个好友通过『多选 → 合并转发』分发，"
            "对每位好友只需 1 次对话框操作，文案作为留言一起送达。"
            "未勾选则每个好友都重新打开聊天 + 重新上传文件。"
        ),
        disabled=st.session_state.phase in ("running", "paused"),
    )

    st.write("")

    # ---- 控制按钮：随 phase 切换 ----
    phase = st.session_state.phase
    btn_a, btn_b, btn_c = st.columns(3)
    start_button = pause_button = resume_button = stop_button = reset_button = False
    if phase == "idle":
        with btn_a:
            start_button = st.button("🚀 开始发送", type="primary", use_container_width=True)
    elif phase == "running":
        with btn_a:
            pause_button = st.button("⏸️ 暂停", use_container_width=True)
        with btn_b:
            stop_button = st.button("⏹️ 停止", use_container_width=True)
    elif phase == "paused":
        with btn_a:
            resume_button = st.button("▶️ 继续", type="primary", use_container_width=True)
        with btn_b:
            stop_button = st.button("⏹️ 停止", use_container_width=True)
    elif phase == "done":
        with btn_a:
            reset_button = st.button("🔄 重新开始", type="primary", use_container_width=True)

# ==================== 右侧：预览 ====================
with col2:
    st.header("👁️ 效果预览")
    st.markdown("这是发送给名单中**第一个联系人**的消息展示效果：")

    friends_list = [f.strip() for f in friends_input.split('\n') if f.strip()]

    if friends_list and message_template_input:
        first_friend = friends_list[0]
        greeting_name = extract_greeting_name(first_friend)

        try:
            preview_message = message_template_input.format(name=greeting_name)
            st.info(f"👤 **目标好友:** {first_friend}  \n🏷️ **提取的称呼:** {greeting_name}")
            st.markdown(f"""
            <div style="background-color: #95ec69; padding: 15px; border-radius: 10px; color: black; max-width: 90%; display: inline-block; margin-bottom: 10px; font-size: 15px; line-height: 1.5; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                {preview_message.replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)

            if uploaded_files:
                file_lines = "<br>".join(
                    f"📄 <b>[文件]</b> {f.name}" for f in uploaded_files
                )
                merge_hint = (
                    f"<div style='color:#888;font-size:12px;margin-bottom:6px;'>共 {len(uploaded_files)} 个文件，将合并发送</div>"
                    if len(uploaded_files) > 1 else ""
                )
                st.markdown(f"""
                <div style="background-color: #ffffff; padding: 15px; border-radius: 10px; color: black; border: 1px solid #e5e5e5; max-width: 90%; display: inline-block; font-size: 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                    {merge_hint}{file_lines}
                </div>
                """, unsafe_allow_html=True)
        except KeyError:
            st.error("⚠️ 消息模板格式有误，请确保仅使用了 `{name}` 作为占位符。")
    else:
        st.info("👈 请在左侧输入名单和消息模板即可在此预览效果")

st.write("---")


# ==================== 按钮事件处理（改 phase + 锁定输入快照）====================

def latch_inputs_and_start():
    if not friends_list:
        st.error("好友名单不能为空！")
        return
    if not message_template_input:
        st.error("消息模板不能为空！")
        return
    if "{name}" not in message_template_input:
        st.warning("提示：模板未使用 `{name}` 占位符，将不会有个性化称呼。")

    # 把当前输入"快照"进 session_state，运行中不再受 UI 控件改动影响
    st.session_state.friends_queue = list(friends_list)
    st.session_state.next_index = 0
    st.session_state.total = len(friends_list)
    st.session_state.message_template = message_template_input
    st.session_state.results = []
    st.session_state.fatal_error = ""

    # 落盘上传的文件
    cleanup_temp_files()
    if uploaded_files:
        tdir = tempfile.mkdtemp(prefix="wx4py_bulk_")
        paths = []
        for uf in uploaded_files:
            p = os.path.join(tdir, uf.name)
            with open(p, "wb") as f:
                f.write(uf.getbuffer())
            paths.append(p)
        st.session_state.temp_dir_for_files = tdir
        st.session_state.temp_file_paths = paths

    st.session_state.use_forward = bool(use_forward_mode and st.session_state.temp_file_paths)
    st.session_state.helper_uploaded = False
    st.session_state.phase = "running"
    st.rerun()


if start_button:
    latch_inputs_and_start()

if pause_button:
    st.session_state.phase = "paused"
    st.rerun()

if resume_button:
    st.session_state.phase = "running"
    st.rerun()

if stop_button:
    st.session_state.phase = "done"
    st.rerun()

if reset_button:
    reset_to_idle()
    st.rerun()


# ==================== 进度区 ====================
st.subheader("⚙️ 发送进度")

total = st.session_state.total
done_count = st.session_state.next_index
progress_value = (done_count / total) if total > 0 else 0
st.progress(min(max(progress_value, 0.0), 1.0))

phase = st.session_state.phase
phase_labels = {
    "idle": "🟡 待开始",
    "running": "🟢 运行中",
    "paused": "⏸️ 已暂停",
    "done": "✅ 已结束",
}
status_line = phase_labels.get(phase, phase)
if total:
    status_line += f"　进度 {done_count}/{total}"
if phase == "running" and done_count < total:
    status_line += f"　正在处理：{st.session_state.friends_queue[done_count]}"
st.markdown(f"**状态：** {status_line}")

if st.session_state.fatal_error:
    st.error(st.session_state.fatal_error)

# 历史日志
if st.session_state.results:
    with st.expander(f"📜 发送日志（{len(st.session_state.results)} 条）", expanded=True):
        for r in st.session_state.results:
            line = f"{r['friend']} -> 称呼为: [{r['greeting']}]"
            if r["status"] == "success":
                st.success(f"✅ {line}　{r['detail']}")
            else:
                st.error(f"❌ {line}　{r['detail']}")


# ==================== 真正的发送：一次 rerun 处理一个好友 ====================

def do_one_iteration():
    """在 running 阶段处理 next_index 指向的好友，结束后让 Streamlit 重跑触发下一个。"""
    idx = st.session_state.next_index
    if idx >= st.session_state.total:
        st.session_state.phase = "done"
        return

    friend_remark = st.session_state.friends_queue[idx]
    search_target = friend_remark
    greeting_name = extract_greeting_name(friend_remark)
    final_message = st.session_state.message_template.format(name=greeting_name)

    # 懒连接 WeChat
    try:
        wx = ensure_wx_client()
    except Exception as e:
        st.session_state.fatal_error = f"微信客户端连接失败: {e}。请确认微信已登录、未被其他程序占用。"
        st.session_state.phase = "done"
        return

    # 转发模式下，首次进入循环时先预上传到文件传输助手
    if (
        st.session_state.use_forward
        and st.session_state.temp_file_paths
        and not st.session_state.helper_uploaded
    ):
        try:
            ok = wx.chat_window.upload_files_to_helper(st.session_state.temp_file_paths)
        except Exception as e:
            ok = False
            st.session_state.results.append({
                "friend": "[预上传]",
                "greeting": "",
                "status": "error",
                "detail": f"上传到文件传输助手失败: {e}，已回退到逐个上传模式",
            })
        if ok:
            st.session_state.helper_uploaded = True
        else:
            st.session_state.use_forward = False  # 回退

    try:
        if st.session_state.use_forward:
            ok = wx.chat_window.forward_recent_merge_to(
                count=len(st.session_state.temp_file_paths),
                target=search_target,
                target_type='contact',
                leave_message=final_message,
            )
            if not ok:
                raise RuntimeError("合并转发失败（详见日志）")
            detail = f"文件 {len(st.session_state.temp_file_paths)} 个（合并转发 + 留言）"
        elif st.session_state.temp_file_paths:
            wx.chat_window.send_message_and_file_to(
                search_target,
                final_message,
                st.session_state.temp_file_paths,
                target_type='contact',
            )
            detail = f"文件 {len(st.session_state.temp_file_paths)} 个（每人重复上传）"
        else:
            wx.chat_window.send_to(search_target, final_message, target_type='contact')
            detail = "仅文本"

        st.session_state.results.append({
            "friend": friend_remark,
            "greeting": greeting_name,
            "status": "success",
            "detail": detail,
        })
    except Exception as e:
        st.session_state.results.append({
            "friend": friend_remark,
            "greeting": greeting_name,
            "status": "error",
            "detail": f"错误：{e}",
        })

    st.session_state.next_index = idx + 1
    if st.session_state.next_index >= st.session_state.total:
        st.session_state.phase = "done"


if st.session_state.phase == "running":
    do_one_iteration()
    # 仍然 running 就触发下一轮 rerun；如果在执行期间被点了暂停/停止
    # （Streamlit 会在当前 run 完成后处理那次点击），下一轮会自动跳出
    if st.session_state.phase == "running":
        st.rerun()

# 结束态时清理一次资源
if st.session_state.phase == "done":
    disconnect_wx()
    cleanup_temp_files()
