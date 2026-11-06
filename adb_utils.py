# -*- coding: utf-8 -*-
"""
刷课自动化 - ADB 与设备操作工具模块
封装 adb 命令调用、截图、OCR、点击、滚动、方向检测等基础能力
"""
import os
import subprocess
import time
import itertools

import numpy as np
import cv2

import config

# 全局缓存 RapidOCR 引擎（懒加载，避免重复初始化）
# 注：已从 easyocr(torch) 替换为 rapidocr_onnxruntime，体积更小、打包友好、无 torch 依赖
_reader = None


def run_adb(*args, timeout=15):
    """执行 adb 命令，返回 stdout 字符串"""
    cmd = [config.ADB_PATH] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return r.stdout
    except subprocess.TimeoutExpired:
        return ""


def get_devices():
    """获取已连接设备列表"""
    out = run_adb("devices")
    devices = []
    for line in out.strip().splitlines()[1:]:
        if line.strip() and "device" in line:
            devices.append(line.split()[0])
    return devices


def auto_connect_emulator():
    """
    自动探测并连接安卓模拟器（也兼容已连手机）
    返回设备序列号，或 None（都没找到）
    """
    # 1. 先检查是否已有设备在线
    devices = get_devices()
    if devices:
        return devices[0]

    # 2. 尝试连接常见模拟器 ADB 端口
    for addr, name in config.EMULATOR_PORTS:
        run_adb("connect", addr)
        time.sleep(1.0)
        devices = get_devices()
        if devices:
            print(f"  ✅ 已连接模拟器 {name} ({addr})")
            return devices[0]

    return None


def get_resolution():
    """获取设备分辨率，返回 (width, height) 物理像素"""
    out = run_adb("shell", "wm", "size")
    # 形如 "Physical size: 1080x2400"
    for line in out.strip().splitlines():
        if "size" in line.lower() or "x" in line:
            nums = line.split(":")[-1].strip()
            if "x" in nums:
                w, h = nums.split("x")
                return int(w.strip()), int(h.strip())
    return 1080, 2400


def get_orientation():
    """获取当前屏幕方向，基于截图实际尺寸（wm size 返回固定物理值，不可靠）"""
    img = screenshot_to_cv()
    if img is None:
        return "portrait"
    h, w = img.shape[:2]
    return "landscape" if w > h else "portrait"


def get_screen_size():
    """获取当前屏幕实际宽高（基于截图，能反映横竖屏）"""
    img = screenshot_to_cv()
    if img is None:
        return get_resolution()
    h, w = img.shape[:2]
    return w, h


def screenshot(path=None):
    """截屏保存到本地，返回图片路径（带重试，防止 pull 到半截损坏文件）"""
    if path is None:
        os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
        path = os.path.join(config.SCREENSHOT_DIR, "screen.png")
    for attempt in range(3):
        run_adb("shell", "screencap", "-p", "/sdcard/screen.png")
        time.sleep(0.3)
        run_adb("pull", "/sdcard/screen.png", path)
        time.sleep(0.2)
        # 验证图片可读
        img = cv2.imread(path)
        if img is not None:
            return path
        time.sleep(0.5)
    return path


def screenshot_to_cv():
    """截屏并返回 OpenCV 图像 (BGR)，失败返回 None"""
    path = screenshot()
    img = cv2.imread(path)
    if img is None:
        # 再试一次
        time.sleep(0.5)
        path = screenshot()
        img = cv2.imread(path)
    return img


def tap(x, y):
    """点击屏幕坐标"""
    run_adb("shell", "input", "tap", str(int(x)), str(int(y)))


def swipe(x1, y1, x2, y2, duration=500):
    """滑动屏幕"""
    run_adb("shell", "input", "swipe",
            str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration)))


def key_back():
    """按返回键"""
    run_adb("shell", "input", "keyevent", "4")


def get_reader():
    """懒加载 RapidOCR 引擎（中英文识别，基于 onnxruntime，无需 torch）"""
    global _reader
    if _reader is None:
        from rapidocr_onnxruntime import RapidOCR
        _reader = RapidOCR()
    return _reader


def ocr_image(cv_img):
    """
    对 OpenCV 图像做 OCR，返回 [(文本, 置信度, 中心x, 中心y), ...]
    RapidOCR 返回格式: [[box(4点), text, score(str)], ...]
    """
    if cv_img is None:
        return []
    reader = get_reader()
    result, _ = reader(cv_img)
    parsed = []
    if not result:
        return parsed
    for item in result:
        box, text, score = item
        try:
            conf = float(score)
        except (ValueError, TypeError):
            conf = 0.5
        if conf < 0.3:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        parsed.append((text, conf, cx, cy))
    return parsed


def ocr_screen():
    """截屏并 OCR，返回 [(文本, 置信度, 中心x, 中心y), ...]"""
    img = screenshot_to_cv()
    return ocr_image(img), img


def find_text(ocr_results, keywords, contains=True):
    """
    在 OCR 结果中查找包含关键词的文本
    返回 [(text, conf, cx, cy), ...] 匹配项
    """
    matched = []
    for (text, conf, cx, cy) in ocr_results:
        if contains:
            if any(k in text for k in keywords):
                matched.append((text, conf, cx, cy))
        else:
            if any(k == text for k in keywords):
                matched.append((text, conf, cx, cy))
    return matched


def tap_text(ocr_results, keywords, offset_x=0, offset_y=0):
    """找到含关键词的文本并点击其中心，返回是否成功"""
    m = find_text(ocr_results, keywords)
    if m:
        text, conf, cx, cy = m[0]
        tap(cx + offset_x, cy + offset_y)
        return True
    return False


def image_diff_ratio(img1, img2):
    """计算两帧图像的差异比例"""
    if img1 is None or img2 is None:
        return 1.0
    if img1.shape != img2.shape:
        return 1.0
    diff = cv2.absdiff(img1, img2)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    return np.sum(thresh > 0) / (thresh.shape[0] * thresh.shape[1])


def generate_option_combinations(n_options):
    """生成多选穷举顺序: 1个组合 -> 2个 -> ... -> n个"""
    options = list(range(n_options))
    for k in range(1, n_options + 1):
        for combo in itertools.combinations(options, k):
            yield combo


def get_option_positions(ocr_results):
    """
    从 OCR 结果中提取选项 A/B/C/D 的位置
    返回按字母排序的 [(letter, cx, cy), ...]
    兼容多种格式： "A. 对" "A、民本思想" "A。对" "B错" "A" 等
    """
    options = []
    for (text, conf, cx, cy) in ocr_results:
        t = text.strip()
        # 首字符是 A/B/C/D 即视为选项（覆盖 "A." "A、" "A。" "A对" "A错" 等）
        if t and t[0] in "ABCD":
            # 排除误识别（如单独的字母出现在题号里，但题号一般是数字）
            # 仅当文本较短或是标准选项格式时才算
            options.append((t[0], cx, cy))
    # 去重（按字母，保留第一个出现的位置）
    seen = {}
    for letter, cx, cy in options:
        if letter not in seen:
            seen[letter] = (cx, cy)
    return sorted(seen.items())


def detect_quiz_popup(ocr_results):
    """
    检测屏幕上是否有答题弹窗
    返回题型: 'judge' | 'single' | 'multi' | None
    """
    text_all = "".join(t[0] for t in ocr_results)
    if "判断题" in text_all:
        return "judge"
    if "多选题" in text_all or "多选" in text_all:
        return "multi"
    if "单选题" in text_all or "单选" in text_all:
        return "single"
    # 兜底：有选项字母 + 有提交按钮，视为答题弹窗
    has_option = get_option_positions(ocr_results)
    has_submit = any(k in text_all for k in ["提交", "确定", "确认", "交卷"])
    if has_option and has_submit:
        # 2个选项默认判断题
        return "judge" if len(has_option) <= 2 else "single"
    return None


def get_submit_button(ocr_results):
    """找到提交按钮坐标，返回 (cx, cy) 或 None"""
    for (text, conf, cx, cy) in ocr_results:
        t = text.strip()
        if t in ("提交", "确定", "确认", "交卷") or t == "提交":
            return (cx, cy)
    return None


def handle_quiz(ocr_results):
    """
    统一处理答题弹窗：选选项 + 提交，靠弹窗是否重弹判断对错
    返回 True 表示弹窗已关闭（答对）
    """
    options = get_option_positions(ocr_results)
    if not options:
        return True  # 没识别到选项，当作无弹窗

    n = len(options)
    letters = [o[0] for o in options]
    qtype = detect_quiz_popup(ocr_results)
    print(f"  [答题] 题型={qtype}, 选项数={n}, 选项={letters}")

    for combo in generate_option_combinations(n):
        combo_letters = [options[i][0] for i in combo]
        print(f"    → 尝试组合: {combo_letters}")

        # 点击选中的选项
        for i in combo:
            letter, (cx, cy) = options[i]
            tap(cx, cy)
            time.sleep(0.4)

        # 找提交按钮并点击
        time.sleep(0.6)
        img = screenshot_to_cv()
        new_ocr = ocr_image(img)
        submit = get_submit_button(new_ocr)
        if submit:
            sx, sy = submit
            tap(sx, sy)
            print(f"    点击提交 @({int(sx)},{int(sy)})")
        else:
            print("    ⚠ 未找到提交按钮，尝试按返回或跳过")
        time.sleep(2.0)

        # 判断弹窗是否重新弹出（重新弹出 = 错）
        check_img = screenshot_to_cv()
        check_ocr = ocr_image(check_img)
        if detect_quiz_popup(check_ocr) is None:
            print(f"    ✅ 组合 {combo_letters} 通过，弹窗关闭")
            return True
        else:
            print(f"    ❌ 组合 {combo_letters} 错误，弹窗重弹，继续")

    print("  ⚠ 所有组合都失败")
    return False
