# -*- coding: utf-8 -*-
"""
刷课自动化 - 主脚本
学习通(超星) 视频任务点自动刷课

流程:
1. 停在章节列表页（竖屏）
2. 循环: 找章节 -> 进入 -> 点播放键 -> 处理答题弹窗 -> 等视频播完 -> 退出 -> 处理退出弹窗 -> 回列表
"""
import os
import sys
import time

# 强制 UTF-8 输出，避免 Windows GBK 控制台对 emoji/中文报错（配合 bat 的 chcp 65001）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adb_utils as adb
import config


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------
# 页面导航
# ---------------------------------------------------------------

def get_orientation():
    """获取当前屏幕方向（基于截图实际尺寸）"""
    return adb.get_orientation()


def click_back():
    """点击左上角返回按钮（根据实际屏幕方向选择坐标）"""
    orient = get_orientation()
    w, h = adb.get_screen_size()
    if orient == "landscape":
        # 横屏 2400x1080，返回键实测 (195,165)
        x = int(w * config.BACK_ICON_LANDSCAPE["x_ratio"])
        y = int(h * config.BACK_ICON_LANDSCAPE["y_ratio"])
    else:
        x = int(w * config.BACK_ICON_PORTRAIT["x_ratio"])
        y = int(h * config.BACK_ICON_PORTRAIT["y_ratio"])
    log(f"  点击返回 @({x},{y}) [{orient}]")
    adb.tap(x, y)
    time.sleep(2.5)


def click_play_button():
    """点击视频播放键（竖屏详情页中央）"""
    w, h = adb.get_screen_size()
    x = int(w * config.PLAY_BUTTON_PORTRAIT["x_ratio"])
    y = int(h * config.PLAY_BUTTON_PORTRAIT["y_ratio"])
    log(f"  点击播放键 @({x},{y})")
    adb.tap(x, y)
    time.sleep(4.0)


def scroll_down():
    """向下滚动章节列表"""
    w, h = adb.get_screen_size()
    x = w // 2
    y1 = int(h * 0.75)
    y2 = int(h * 0.25)
    adb.swipe(x, y1, x, y2, duration=600)
    time.sleep(1.5)


def load_progress():
    """从文件加载已刷章节编号"""
    if os.path.exists(config.PROGRESS_FILE):
        with open(config.PROGRESS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_progress(done_sections):
    """保存已刷章节编号到文件"""
    with open(config.PROGRESS_FILE, "w", encoding="utf-8") as f:
        for num in sorted(done_sections):
            f.write(num + "\n")


def find_min_section(ocr_results, skip=None):
    """
    在章节列表中找编号最小且未刷的章节
    返回 (cx, cy, 编号字符串) 或 None
    按编号排序，选最小的未刷编号（避免 OCR 乱序导致跳节）
    """
    import re
    if skip is None:
        skip = set()
    sections = []
    for (text, conf, cx, cy) in ocr_results:
        t = text.strip()
        m = re.match(r"^(\d+\.\d+\.\d+)", t)
        if m:
            num = m.group(1)
            if num not in skip:
                sections.append((num, cx, cy))
    if not sections:
        return None
    # 按编号排序（转成 tuple 比较，如 2.1.1 -> (2,1,1)）
    sections.sort(key=lambda s: tuple(int(x) for x in s[0].split(".")))
    num, cx, cy = sections[0]
    return (cx, cy, num)


def is_section_list(ocr_results):
    """
    判断当前是否在「章节列表页」
    特征：出现 2 个及以上的章节编号（如 2.1.1、2.1.2...）
    """
    import re
    nums = [t[0].strip() for t in ocr_results
            if re.match(r"^\d+\.\d+\.\d+", t[0].strip())]
    return len(nums) >= 2


def back_to_list():
    """
    从视频/详情页返回到章节列表页
    循环点返回，直到 OCR 识别到多个章节编号（说明回到列表）
    """
    for i in range(5):
        click_back()
        time.sleep(1.5)
        handle_exit_popup()
        img = adb.screenshot_to_cv()
        ocr = adb.ocr_image(img)
        if is_section_list(ocr):
            log("  已回到章节列表页")
            return True
        orient = get_orientation()
        if orient == "landscape":
            log("  仍在横屏，继续返回...")
            continue
    log("  ⚠ 多次返回仍未确认回到列表")
    return False


# ---------------------------------------------------------------
# 视频等待与弹窗处理
# ---------------------------------------------------------------

def _read_progress(ocr):
    """
    从 OCR 结果读取视频进度 (当前秒, 总秒) 或 None
    时间格式如 "22:36" "25:26"
    """
    times = []
    for t, conf, cx, cy in ocr:
        t = t.strip()
        if ":" in t and len(t) <= 6:
            parts = t.split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                times.append((int(parts[0]) * 60 + int(parts[1]), cx, cy))
    if len(times) < 2:
        return None
    # 当前时间在左，总时长在右（横屏），按 x 坐标排序
    times.sort(key=lambda x: x[1])
    cur = times[0][0]
    total = times[-1][0]
    return cur, total


def wait_video(initial_landscape=True):
    """
    等待视频播放完成，期间持续检测答题弹窗
    判定策略（可靠优先）：
    1. 检测答题弹窗 -> 处理
    2. 周期性触碰屏幕唤醒进度条，读时间戳判断是否走满
    3. 读不到时间戳时，周期轻触屏幕唤醒进度条
    """
    log("  等待视频播放，检测弹窗...")
    last_tap = 0  # 上次触碰屏幕的时间（用于唤醒进度条）

    while True:
        img = adb.screenshot_to_cv()
        ocr = adb.ocr_image(img)

        # 1. 检测答题弹窗
        qtype = adb.detect_quiz_popup(ocr)
        if qtype is not None:
            log(f"  💡 检测到答题弹窗（{qtype}），处理中...")
            adb.handle_quiz(ocr)
            time.sleep(1.5)
            continue

        # 2. 读进度条时间戳，判断是否走满
        progress = _read_progress(ocr)
        if progress is not None:
            cur, total = progress
            if total > 0:
                ratio = cur / total
                if ratio >= 0.97:
                    log(f"  进度 {cur}s/{total}s = {ratio:.0%}，接近播完，确认...")
                    time.sleep(4.0)
                    img2 = adb.screenshot_to_cv()
                    ocr2 = adb.ocr_image(img2)
                    p2 = _read_progress(ocr2)
                    if p2 is None or (p2[1] > 0 and p2[0] / p2[1] >= 0.95):
                        log("  ✅ 视频已播完（进度走满）")
                        return "finished"
        else:
            # 读不到时间戳：进度条可能隐藏了，周期性轻触唤醒
            now = time.time()
            if now - last_tap > 8:
                w, h = adb.get_screen_size()
                adb.tap(int(w * 0.5), int(h * 0.5))
                last_tap = now
                time.sleep(1.0)
                continue

        time.sleep(config.POLL_INTERVAL)


def handle_exit_popup():
    """
    点返回退出视频后，可能弹出答题弹窗
    循环处理直到没有弹窗
    """
    for _ in range(10):
        img = adb.screenshot_to_cv()
        ocr = adb.ocr_image(img)
        qtype = adb.detect_quiz_popup(ocr)
        if qtype is None:
            return True
        log(f"  退出时弹出答题弹窗（{qtype}），处理中...")
        adb.handle_quiz(ocr)
        time.sleep(1.5)
    return False


# ---------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------

def main():
    log("=" * 50)
    log("学习通视频刷课自动化 启动")
    log("=" * 50)

    devices = adb.get_devices()
    if not devices:
        log("未检测到设备，尝试自动连接安卓模拟器...")
        ser = adb.auto_connect_emulator()
        if not ser:
            log("❌ 未检测到设备或模拟器！")
            log("   请先启动安卓模拟器（雷电/MuMu/夜神等）并安装学习通App，")
            log("   或者连接已开启 USB 调试的安卓手机。")
            sys.exit(1)
        devices = [ser]
    log(f"✅ 设备: {devices[0]}")

    w, h = adb.get_resolution()
    log(f"📐 分辨率: {w}x{h}")

    log("初始化 OCR（首次会下载模型）...")
    adb.get_reader()
    log("✅ OCR 就绪")

    log("-" * 50)
    log("请确保手机停在【章节列表页】（竖屏）")
    log("脚本将自动循环，Ctrl+C 中断")
    log("-" * 50)
    time.sleep(3)

    section_count = 0
    scroll_miss = 0
    done_sections = load_progress()  # 从文件加载已刷章节
    if done_sections:
        log(f"  已加载历史进度 {len(done_sections)} 节: {sorted(done_sections)}")

    try:
        # 启动时检测：如果已经在横屏播放状态，先处理完当前这节
        init_orient = get_orientation()
        if init_orient == "landscape":
            log("  检测到已在横屏（可能在播放），先接管当前节...")
            wait_video()
            back_to_list()
            time.sleep(2.0)

        while True:
            # 1. 确保在章节列表页（竖屏）
            img = adb.screenshot_to_cv()
            ocr = adb.ocr_image(img)

            # 如果不在列表页（可能卡在详情页/横屏），先返回
            if not is_section_list(ocr):
                if get_orientation() == "landscape":
                    log("  当前在横屏，返回...")
                    click_back()
                    handle_exit_popup()
                    continue
                else:
                    log("  当前不在章节列表，返回...")
                    click_back()
                    time.sleep(1.5)
                    continue

            # 2. 找编号最小且未刷的章节
            pos = find_min_section(ocr, skip=done_sections)
            if pos is None:
                log("  未找到未刷章节，向下滚动...")
                scroll_down()
                scroll_miss += 1
                if scroll_miss > 15:
                    log("⚠ 连续滚动多次未找到新章节，可能已全部完成")
                    log("  当前进度:", sorted(done_sections))
                    scroll_miss = 0
                continue

            cx, cy, num = pos
            scroll_miss = 0
            log(f"  进入章节 {num} @({int(cx)},{int(cy)})")
            adb.tap(cx, cy)
            time.sleep(3.0)

            # 3. 点击播放键（重试直到进入横屏）
            for attempt in range(3):
                click_play_button()
                orient = get_orientation()
                if orient == "landscape":
                    log("  ✅ 已进入横屏播放")
                    break
                else:
                    log(f"  ⚠ 第{attempt+1}次未进入横屏，重试...")
                    time.sleep(2.0)
            else:
                log("  ❌ 多次尝试仍未进入播放，跳过本节返回列表")
                back_to_list()
                continue

            # 4. 等待视频播完（期间处理弹窗）
            wait_video()

            # 5. 返回章节列表
            back_to_list()

            # 6. 标记本节已完成并持久化
            done_sections.add(num)
            save_progress(done_sections)
            section_count += 1
            log(f"🎉 已完成第 {section_count} 节（{num}），累计 {len(done_sections)} 节")
            time.sleep(2.0)

    except KeyboardInterrupt:
        log("\n⚠ 用户中断")
        save_progress(done_sections)
        log(f"本次完成 {section_count} 节，累计 {len(done_sections)} 节")
        sys.exit(0)


if __name__ == "__main__":
    main()
