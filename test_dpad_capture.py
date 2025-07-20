#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D-Pad 信号捕获测试脚本
测试手柄 D-Pad 是否能被正确识别
"""

import time
from inputs import get_gamepad

def test_dpad_capture():
    """测试 D-Pad 信号捕获"""
    print("🎮 D-Pad 信号捕获测试")
    print("=" * 40)
    print("请按手柄的 D-Pad 方向键（上下左右）")
    print("按 Ctrl+C 退出")
    print("=" * 40)
    
    try:
        while True:
            events = get_gamepad()
            for event in events:
                if event.code in ['ABS_HAT0X', 'ABS_HAT0Y']:
                    print(f"🎯 D-Pad 信号: {event.code} = {event.state}")
                elif event.code.startswith('ABS_HAT'):
                    print(f"🎯 Hat 信号: {event.code} = {event.state}")
                elif event.code.startswith('BTN_DPAD'):
                    print(f"🎯 D-Pad 按钮: {event.code} = {event.state}")
                elif event.code.startswith('ABS_'):
                    # 只显示轴的变化（避免刷屏）
                    if abs(event.state) > 1000:  # 只显示明显的轴变化
                        print(f"🕹️  轴信号: {event.code} = {event.state}")
                elif event.code.startswith('BTN_'):
                    if event.state == 1:  # 只显示按钮按下
                        print(f"🔘 按钮: {event.code} = {event.state}")
            
            time.sleep(0.01)  # 10ms 间隔
            
    except KeyboardInterrupt:
        print("\n✅ 测试完成")

if __name__ == "__main__":
    test_dpad_capture() 