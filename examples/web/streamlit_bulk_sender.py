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
except Exception as e:
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
    st.warning("⚠️ 检测到非 Windows 环境或未安装 pywin32。当前已进入 **UI 演示模式**，所有发送操作仅做界面模拟，不会真正发送微信消息。")

st.title("wx4py 批量个性化发送工具")
st.markdown("通过网页版自动化给微信好友批量发送带称呼的专属消息和文件。")

st.sidebar.header("配置区")
st.sidebar.markdown("""
**支持的微信版本**：
本项目目前支持微信 **4.x** 版本（已测试 4.1.7.59, 4.1.8.29）。
使用前请确保电脑已登录并打开微信。
""")

def extract_greeting_name(remark: str) -> str:
    """
    根据备注提取称呼。
    逻辑：提取破折号后内容，然后删除第一个字符（姓氏）。
    例如："25届初二-郑子轩妈妈" -> "郑子轩妈妈" -> "子轩妈妈"
          "张永琪爸爸" -> "张永琪爸爸" -> "永琪爸爸"
    """
    remark = remark.strip()
    if not remark:
        return ""
        
    # 提取破折号后面的部分
    if "-" in remark:
        name_part = remark.split("-")[-1].strip()
    elif "—" in remark: # 兼容中文破折号
        name_part = remark.split("—")[-1].strip()
    else:
        name_part = remark

    # 删除第一个字符（姓氏）
    if len(name_part) > 1:
        return name_part[1:]
    return name_part

# 创建左右两列，左边比例稍大
col1, col2 = st.columns([1.2, 1])

with col1:
    st.header("📝 编辑发送内容")
    # 1. 好友名单输入
    st.subheader("1. 接收好友名单")
    friends_input = st.text_area(
        "请输入好友备注名单（每行一个）：",
        value="25届初二-郑子轩妈妈\n张永琪爸爸\n王小明",
        height=150
    )

    # 2. 消息模板输入
    st.subheader("2. 消息模板")
    st.markdown("使用 `{name}` 作为称呼的占位符。程序会自动提取备注中的名字替换它。")
    message_template = st.text_area(
        "请输入消息模板：",
        value="{name}，您好！\n\n（请在此处输入您的自定义消息内容...）",
        height=200
    )

    # 3. 文件上传
    st.subheader("3. 附加文件（可选，支持多文件合并发送）")
    uploaded_files = st.file_uploader(
        "选择要发送的文件（可一次选择多个，将合并为一条消息发出）",
        accept_multiple_files=True,
    )

    # 4. 发送方式
    use_forward_mode = st.checkbox(
        "通过『文件传输助手』转发（先上传 1 次，后续好友只走『合并转发』，文案放进留言框）",
        value=True,
        help=(
            "勾选后：文件先发到文件传输助手，每个好友通过『多选 → 合并转发』分发，"
            "对每位好友只需 1 次对话框操作，文案作为留言一起送达。"
            "未勾选则每个好友都重新打开聊天 + 重新上传文件。"
        ),
    )

    st.write("") # 留点间距
    start_button = st.button("🚀 开始自动化发送", type="primary", use_container_width=True)

with col2:
    st.header("👁️ 效果预览")
    st.markdown("这是发送给名单中**第一个联系人**的消息展示效果：")
    
    friends_list = [f.strip() for f in friends_input.split('\n') if f.strip()]
    
    if friends_list and message_template:
        first_friend = friends_list[0]
        greeting_name = extract_greeting_name(first_friend)
        
        try:
            preview_message = message_template.format(name=greeting_name)
            
            st.info(f"👤 **目标好友:** {first_friend}  \n🏷️ **提取的称呼:** {greeting_name}")
            
            # 使用类似于微信对话框的样式（绿色背景气泡）
            st.markdown(f"""
            <div style="background-color: #95ec69; padding: 15px; border-radius: 10px; color: black; max-width: 90%; display: inline-block; margin-bottom: 10px; font-size: 15px; line-height: 1.5; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                {preview_message.replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)
            
            # 渲染文件附件的预览（多文件合并展示在一条气泡内）
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

if start_button:
    if not friends_list:
        st.error("好友名单不能为空！")
        st.stop()
        
    if not message_template:
        st.error("消息模板不能为空！")
        st.stop()
        
    if "{name}" not in message_template:
        st.warning("提示：您的消息模板中没有使用 `{name}` 占位符。发送的消息将不会有个性化称呼。")

    st.subheader("⚙️ 发送进度")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.container()
    
    # 如果有文件，逐个保存到独立临时目录，避免同名覆盖
    temp_file_paths: list[str] = []
    temp_dir_for_files: str | None = None
    if uploaded_files:
        temp_dir_for_files = tempfile.mkdtemp(prefix="wx4py_bulk_")
        for uf in uploaded_files:
            path = os.path.join(temp_dir_for_files, uf.name)
            with open(path, "wb") as f:
                f.write(uf.getbuffer())
            temp_file_paths.append(path)
        
    try:
        with WeChatClient(auto_connect=True) as wx:
            total = len(friends_list)

            # 转发模式：开始批次前把全部文件上传到文件传输助手 1 次
            use_forward = bool(use_forward_mode and temp_file_paths)
            if use_forward:
                status_text.text(f"预上传 {len(temp_file_paths)} 个文件到文件传输助手...")
                try:
                    ok = wx.chat_window.upload_files_to_helper(temp_file_paths)
                except Exception as e:
                    ok = False
                    log_container.error(f"预上传到文件传输助手失败: {e}")
                if not ok:
                    log_container.error("预上传失败，自动回退到逐个上传模式")
                    use_forward = False

            for i, friend_remark in enumerate(friends_list):
                status_text.text(f"正在处理: {friend_remark} ({i+1}/{total})")

                # 通讯录搜索用**完整原始备注**（含前缀和姓氏），与微信里的备注完全一致才能命中
                search_target = friend_remark
                # 称呼只用于消息文案，去掉前缀和姓氏，如 "25届初三-罗雅鹭妈妈" -> "雅鹭妈妈"
                greeting_name = extract_greeting_name(friend_remark)
                final_message = message_template.format(name=greeting_name)

                try:
                    if use_forward:
                        # 仍停留在文件传输助手聊天，对每个好友走"多选 → 合并转发 → 留言"
                        ok = wx.chat_window.forward_recent_merge_to(
                            count=len(temp_file_paths),
                            target=search_target,
                            target_type='contact',
                            leave_message=final_message,
                        )
                        if not ok:
                            raise RuntimeError("合并转发失败（详见日志）")
                        file_log = f"，文件 {len(temp_file_paths)} 个（合并转发 + 留言）"
                    elif temp_file_paths:
                        wx.chat_window.send_message_and_file_to(
                            search_target,
                            final_message,
                            temp_file_paths,
                            target_type='contact',
                        )
                        file_log = f"，文件 {len(temp_file_paths)} 个（每人重复上传）"
                    else:
                        wx.chat_window.send_to(
                            search_target,
                            final_message,
                            target_type='contact',
                        )
                        file_log = ""

                    log_container.success(f"✅ 发送成功: {friend_remark} -> 称呼为: [{greeting_name}]{file_log}")
                except Exception as e:
                    log_container.error(f"❌ 发送失败: {friend_remark}. 错误信息: {str(e)}")

                # 更新进度条
                progress_bar.progress((i + 1) / total)

        status_text.text("🎉 批量发送任务完成！")
        
    except Exception as e:
        st.error(f"微信客户端连接或初始化失败: {str(e)}")
        st.info("请确保已打开微信（支持 4.x 版本），并且当前没有被其他程序独占。")
        
    finally:
        # 清理临时文件与临时目录
        for path in temp_file_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        if temp_dir_for_files and os.path.isdir(temp_dir_for_files):
            try:
                os.rmdir(temp_dir_for_files)
            except Exception:
                pass
