#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vgamepad 测试脚本
测试虚拟 Xbox 360 手柄是否被游戏正确识别
"""

import time
import vgamepad
import sys

def test_vgamepad():
    """测试 vgamepad 功能"""
    try:
        # 创建虚拟 Xbox 360 手柄
        gamepad = vgamepad.VX360Gamepad()
        print("✅ 虚拟 Xbox 360 手柄创建成功")
        
        # 初始化手柄
        gamepad.reset()
        gamepad.update()
        print("🔄 手柄已重置到初始状态")
        
        print("\n🎮 开始 vgamepad 测试...")
        print("请打开游戏，观察输入是否被识别")
        print("每个测试会持续 3 秒")
        
        # 测试左摇杆
        print("\n🕹️  测试左摇杆...")
        test_joystick = [
            ("左", -32768, 0),
            ("右", 32767, 0),
            ("上", 0, -32768),
            ("下", 0, 32767),
            ("中心", 0, 0)
        ]
        
        for direction, x, y in test_joystick:
            print(f"  ➡️  {direction} (X:{x}, Y:{y})")
            gamepad.left_joystick(x_value=x, y_value=y)
            gamepad.update()
            time.sleep(3)
        
        # 测试按钮
        print("\n🔘 测试按钮...")
        buttons = [
            ("A", vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A),
            ("B", vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B),
            ("X", vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X),
            ("Y", vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y),
            ("LB", vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),
            ("RB", vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER),
            ("Start", vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START),
            ("Back", vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_BACK)
        ]
        
        for name, button in buttons:
            print(f"  ➡️  {name} 按钮")
            gamepad.press_button(button=button)
            gamepad.update()
            time.sleep(1)
            gamepad.release_button(button=button)
            gamepad.update()
            time.sleep(1)
        
        # 测试 D-Pad
        print("\n🎯 测试 D-Pad...")
        dpad_directions = [
            ("上", 1),
            ("右", 2),
            ("下", 3),
            ("左", 4),
            ("右上", 5),
            ("右下", 6),
            ("左下", 7),
            ("左上", 8),
            ("中心", 0)
        ]
        
        for direction, value in dpad_directions:
            print(f"  ➡️  {direction} (值: {value})")
            gamepad._dpad_direction = value
            gamepad.update()
            time.sleep(2)
        
        # 测试触发器
        print("\n🎚️  测试触发器...")
        print("  ➡️  左触发器")
        gamepad.left_trigger(value=255)
        gamepad.update()
        time.sleep(2)
        
        print("  ➡️  右触发器")
        gamepad.right_trigger(value=255)
        gamepad.update()
        time.sleep(2)
        
        # 回到初始状态
        print("\n➡️  回到初始状态")
        gamepad.reset()
        gamepad.update()
        
        print("\n✅ vgamepad 测试完成")
        print("\n如果游戏没有反应，请检查：")
        print("1. 游戏设置中的控制器选项")
        print("2. 是否选择了 'Xbox 360 Controller' 或 'XInput Device' 作为输入设备")
        print("3. 游戏是否支持 XInput")
        print("4. 尝试在 joy.cpl 中测试 'Xbox 360 Controller'")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("🎮 vgamepad 测试工具")
    print("=" * 50)
    
    if test_vgamepad():
        print("\n🎉 测试完成！")
    else:
        print("\n💥 测试失败！") 