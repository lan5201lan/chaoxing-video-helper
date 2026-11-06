# -*- coding: utf-8 -*-
"""
刷课自动化 - 配置文件
学习通(超星) 视频任务点自动刷课
手机: Android（分辨率脚本自动探测）
"""
import os
import sys

# ADB 可执行文件路径
# 优先用同目录/上级目录下的 adb.exe（便携式分发）；找不到则尝试系统 PATH 里的 adb
def _find_adb():
    # 1. 脚本同目录
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adb.exe")
    if os.path.exists(local):
        return local
    # 2. 上级 tools/platform-tools
    up = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "tools", "platform-tools", "adb.exe")
    if os.path.exists(up):
        return up
    # 3. 打包进 exe 时（PyInstaller），adb 在资源目录
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        bundled = os.path.join(base, "adb.exe")
        if os.path.exists(bundled):
            return bundled
    # 4. 兜底用系统 PATH 的 adb
    return "adb"

ADB_PATH = _find_adb()

# 常见安卓模拟器 ADB 端口（自动探测连接，按顺序尝试）
# 端口 -> 模拟器名称
EMULATOR_PORTS = [
    ("127.0.0.1:5555", "雷电/蓝叠"),
    ("127.0.0.1:5557", "雷电(多开)"),
    ("127.0.0.1:7555", "MuMu"),
    ("127.0.0.1:62001", "夜神"),
    ("127.0.0.1:21503", "逍遥"),
    ("127.0.0.1:16384", "MuMu12"),
]

# 截图保存目录（本地临时）
def _app_dir():
    """返回可写的应用数据目录。
    打包成 exe 后，进度/截图应写在 exe 所在目录（而非只读的 _MEIPASS 临时目录）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

SCREENSHOT_DIR = os.path.join(_app_dir(), "screenshots")

# 进度记录文件（记录已刷完的章节编号，重启后可续刷）
PROGRESS_FILE = os.path.join(_app_dir(), "progress.txt")

# OCR 语言（中文简 + 英文）
OCR_LANG = ["ch_sim", "en"]

# 轮询间隔（秒）
POLL_INTERVAL = 2.0          # 检测弹窗/状态的间隔
POPUP_CHECK_COOLDOWN = 2.0   # 答题弹窗处理后的冷却时间

# 视频完成判定
# 当 OCR 识别到这些文字之一时，认为视频已播完/进入完成状态
COMPLETED_KEYWORDS = [
    "已完成", "完成", "恭喜", "任务点已完成",
    "重新播放", "重播", "再次观看",
]

# 播放结束的另一种判据：连续 N 帧屏幕几乎不变（画面卡住不动）
IDLE_FRAMES_THRESHOLD = 5      # 连续 N 帧无变化判定为卡住
IDLE_PIXEL_DIFF = 0.001        # 帧差异比例阈值

# 答题弹窗识别关键词
QUIZ_POPUP_KEYWORDS = [
    "单选题", "多选题", "判断题", "填空题", "简答题",
    "请选择", "请选出", "正确", "错误", "提交",
    "A.", "B.", "C.", "D.", "A、", "B、", "C、", "D、",
]

# 提交按钮文字
SUBMIT_KEYWORDS = ["提交", "确定", "确认", "交卷", "下一题"]

# 退出按钮（左上角返回箭头）—— 实测坐标
# 横屏 2400x1080: 返回箭头约 (195,165)
# 竖屏 1080x2400: 返回箭头约 (60,155)
BACK_ICON_LANDSCAPE = {"x_ratio": 0.081, "y_ratio": 0.153}  # 195/2400, 165/1080
BACK_ICON_PORTRAIT = {"x_ratio": 0.056, "y_ratio": 0.065}    # 60/1080, 155/2400

# 播放键（视频中央大播放键）—— 实测 (540, 1140) 竖屏 1080x2400
PLAY_BUTTON_PORTRAIT = {"x_ratio": 0.5, "y_ratio": 0.475}  # 540/1080, 1140/2400

# 下一节按钮 —— 通过 OCR 找文字更稳，这里是兜底坐标比例
NEXT_SECTION_KEYWORDS = ["下一节", "下一课", "下一个", "下一节视频"]

# 章节列表滚动参数
SCROLL_STEP_RATIO = 0.6   # 每次滚动屏幕高度的比例
SCROLL_SLEEP = 1.0        # 滚动后等待

# 多选穷举：最多选项数
MAX_OPTIONS = 4

# 完成某章节后，标记"已完成"用的关键词（用于跳过已完成的）
DONE_MARK_KEYWORDS = ["已完成", "已看完", "√"]
