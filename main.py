import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import os
import time
import threading
from datetime import datetime
from pynput import keyboard, mouse
import pygame
import sys
import ctypes
from ctypes import wintypes
import win32api
import win32con

class GameControllerRecorder:
    def __init__(self):
        """初始化应用"""
        self.root = tk.Tk()
        self.root.title("黑神话手柄录制器")
        self.root.geometry("400x600")
        self.root.resizable(False, False)
        
        # 设置窗口位置
        self.set_window_position()
        
        # 初始化变量
        self.is_recording = False  # 录制状态
        self.is_playing = False    # 播放状态
        self.force_stop = False    # 强制停止标志
        self.recording_data = []   # 录制数据
        self.current_recording_file = ""  # 当前录制文件名
        self.recording_start_time = 0  # 录制开始时间
        
        # 手柄相关
        self.joysticks = []  # 手柄列表
        self.current_joystick_data = {}  # 当前手柄数据
        
        # 移动控制线程
        self.movement_running = False
        self.movement_thread = None
        self.movement_lock = threading.Lock()
        self.target_keys = set()  # 目标按键集合
        self.pressed_keys = set()  # 当前按下的按键
        
        # 热键监听器
        self.keyboard_listener = None
        
        # 创建录制文件夹
        self.recordings_dir = "recordings"
        if not os.path.exists(self.recordings_dir):
            os.makedirs(self.recordings_dir)
        
        # 加载控制器配置
        self.controller_config = self.load_controller_config()
        
        # 初始化手柄
        self.init_joysticks()
        
        # 初始化虚拟手柄
        # self.init_virtual_joystick() # 删除虚拟手柄初始化
        
        # 设置UI
        self.setup_ui()
        
        # 设置全局热键
        self.setup_global_hotkeys()
    
    def find_and_activate_game_window(self):
        """查找并激活黑神话游戏窗口"""
        try:
            import psutil
            
            # 查找名为b1-Win64-Shipping.exe的进程
            target_process = None
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.info['name'] == 'b1-Win64-Shipping.exe':
                        target_process = proc
                        print(f"找到黑神话游戏进程: {proc.info['name']} (PID: {proc.info['pid']})")
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not target_process:
                print("未找到黑神话游戏进程 b1-Win64-Shipping.exe")
                return False
            
            # 查找该进程的窗口
            import win32gui
            import win32process
            import win32con
            import win32api
            
            def enum_windows_callback(hwnd, windows):
                try:
                    # 获取窗口进程ID
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid == target_process.info['pid']:
                        # 检查窗口是否可见
                        if win32gui.IsWindowVisible(hwnd):
                            window_title = win32gui.GetWindowText(hwnd)
                            if window_title:  # 确保窗口有标题
                                windows.append((hwnd, window_title))
                except:
                    pass
                return True
            
            windows = []
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            if not windows:
                print("未找到黑神话游戏窗口")
                return False
            
            # 选择第一个找到的窗口
            hwnd, window_title = windows[0]
            print(f"找到游戏窗口: {window_title} (句柄: {hwnd})")
            
            # 强力激活窗口
            try:
                # 方法1: 显示窗口
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                
                # 方法2: 设置前台窗口
                win32gui.SetForegroundWindow(hwnd)
                
                # 方法3: 强制激活
                win32gui.BringWindowToTop(hwnd)
                
                # 方法4: 使用SetActiveWindow
                win32gui.SetActiveWindow(hwnd)
                
                # 方法5: 使用SetWindowPos设置到前台
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
                
                # 恢复窗口到正常层级（不影响我们的程序置顶）
                import time
                time.sleep(0.1)
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, 
                                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
                
                # 方法6: 模拟点击窗口来激活
                try:
                    # 获取窗口位置和大小
                    rect = win32gui.GetWindowRect(hwnd)
                    x = rect[0] + (rect[2] - rect[0]) // 2
                    y = rect[1] + (rect[3] - rect[1]) // 2
                    
                    # 模拟鼠标点击窗口中心
                    win32api.SetCursorPos((x, y))
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                except:
                    pass
                
                print(f"成功激活游戏窗口: {window_title}")
                return True
                
            except Exception as e:
                print(f"激活游戏窗口失败: {e}")
                return False
                
        except ImportError:
            print("缺少psutil库，无法自动激活游戏窗口")
            return False
        except Exception as e:
            print(f"查找游戏窗口时出错: {e}")
            return False
    
    def set_window_position(self):
        """设置窗口位置在屏幕右下角"""
        try:
            # 获取屏幕尺寸
            screen_width = self.root.winfo_screenwidth()  # 获取屏幕宽度
            screen_height = self.root.winfo_screenheight()  # 获取屏幕高度
            
            # 获取窗口尺寸
            window_width = 400  # 窗口宽度
            window_height = 600  # 窗口高度
            
            # 计算右下角位置（留出更多边距，避免被任务栏遮挡）
            margin_x = 50  # 水平边距
            margin_y = 80  # 垂直边距（给任务栏留空间）
            x_position = screen_width - window_width - margin_x  # X坐标
            y_position = screen_height - window_height - margin_y  # Y坐标
            
            # 设置窗口位置
            self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
            
            # 设置窗口置顶
            self.root.attributes('-topmost', True)
            
            print(f"窗口已定位到右下角: ({x_position}, {y_position})")  # 调试信息
            print("窗口已设置为置顶")  # 调试信息
        except Exception as e:
            print(f"设置窗口位置失败: {e}")  # 调试信息
        
    def init_joysticks(self):
        """初始化手柄"""
        try:
            pygame.init()  # 初始化pygame
            pygame.joystick.init()  # 初始化手柄系统
            
            joystick_count = pygame.joystick.get_count()  # 获取连接的手柄数量
            print(f"检测到 {joystick_count} 个手柄")  # 打印手柄数量
            
            for i in range(joystick_count):  # 遍历所有手柄
                joystick = pygame.joystick.Joystick(i)  # 创建手柄对象
                joystick.init()  # 初始化手柄
                self.joysticks.append(joystick)  # 添加到手柄列表
                
                # 初始化手柄数据
                self.current_joystick_data[joystick.get_id()] = {
                    'name': joystick.get_name(),  # 手柄名称
                    'axes': [0.0] * joystick.get_numaxes(),  # 轴数据数组，初始化为0
                    'buttons': [False] * joystick.get_numbuttons(),  # 按钮状态数组，初始化为False
                    'hats': [(0, 0)] * joystick.get_numhats()  # 帽子开关数组，初始化为(0,0)
                }
                print(f"检测到手柄: {joystick.get_name()}")  # 打印手柄名称
        except Exception as e:
            print(f"手柄初始化失败: {e}")  # 打印错误信息
            self.joysticks = []  # 清空手柄列表
    
    def start_movement_thread(self):
        """启动移动控制线程"""
        if self.movement_thread is None or not self.movement_thread.is_alive():
            self.movement_running = True  # 设置运行标志
            self.movement_thread = threading.Thread(target=self.movement_control_loop, daemon=True)  # 创建守护线程
            self.movement_thread.start()  # 启动线程
            print("移动控制线程已启动")  # 调试信息
    
    def stop_movement_thread(self):
        """停止移动控制线程"""
        self.movement_running = False  # 设置停止标志
        if self.movement_thread and self.movement_thread.is_alive():
            self.movement_thread.join(timeout=1.0)  # 等待线程结束，最多等待1秒
            print("移动控制线程已停止")  # 调试信息
    
    def movement_control_loop(self):
        """移动控制线程主循环 - 实现流畅的按键发送"""
        while self.movement_running:  # 线程运行循环
            try:
                with self.movement_lock:  # 获取线程锁
                    current_target_keys = self.target_keys.copy()  # 复制当前目标按键
                
                # 释放不再需要的按键
                keys_to_release = self.pressed_keys - current_target_keys
                for key in keys_to_release:
                    self.release_single_key(key)  # 释放单个按键
                
                # 按下新需要的按键
                keys_to_press = current_target_keys - self.pressed_keys
                for key in keys_to_press:
                    self.press_single_key(key)  # 按下单个按键
                
                # 更新当前按下的按键状态
                self.pressed_keys = current_target_keys.copy()
                
                # 线程休眠，控制发送频率（60Hz，约16.67ms）
                time.sleep(0.016)  # 约60FPS的更新频率
                
            except Exception as e:
                print(f"移动控制线程错误: {e}")  # 错误处理
                time.sleep(0.1)  # 出错时稍微等待
    
    def press_single_key(self, key):
        """按下单个按键"""
        try:
            if key == 'W':
                win32api.keybd_event(ord('W'), 0, 0, 0)
                print(f"按下按键: {key} - 前进")
            elif key == 'S':
                win32api.keybd_event(ord('S'), 0, 0, 0)
                print(f"按下按键: {key} - 后退")
            elif key == 'A':
                win32api.keybd_event(ord('A'), 0, 0, 0)
                print(f"按下按键: {key} - 左移")
            elif key == 'D':
                win32api.keybd_event(ord('D'), 0, 0, 0)
                print(f"按下按键: {key} - 右移")
        except Exception as e:
            print(f"按下按键失败 {key}: {e}")
    
    def release_single_key(self, key):
        """释放单个按键"""
        try:
            if key == 'W':
                win32api.keybd_event(ord('W'), 0, win32con.KEYEVENTF_KEYUP, 0)
                print(f"释放按键: {key}")
            elif key == 'S':
                win32api.keybd_event(ord('S'), 0, win32con.KEYEVENTF_KEYUP, 0)
                print(f"释放按键: {key}")
            elif key == 'A':
                win32api.keybd_event(ord('A'), 0, win32con.KEYEVENTF_KEYUP, 0)
                print(f"释放按键: {key}")
            elif key == 'D':
                win32api.keybd_event(ord('D'), 0, win32con.KEYEVENTF_KEYUP, 0)
                print(f"释放按键: {key}")
        except Exception as e:
            print(f"释放按键失败 {key}: {e}")
    
    def update_movement_target(self, left_x, left_y):
        """更新移动目标按键（线程安全）"""
        new_target_keys = set()  # 新的目标按键集合
        
        # 根据摇杆位置确定需要按下的按键
        if left_y < -0.1:  # 前进
            new_target_keys.add('W')
            print(f"摇杆向前 (Y={left_y:.2f}) -> 按下W键")
        elif left_y > 0.1:  # 后退
            new_target_keys.add('S')
            print(f"摇杆向后 (Y={left_y:.2f}) -> 按下S键")
        
        if left_x < -0.1:  # 左移
            new_target_keys.add('A')
            print(f"摇杆向左 (X={left_x:.2f}) -> 按下A键")
        elif left_x > 0.1:  # 右移
            new_target_keys.add('D')
            print(f"摇杆向右 (X={left_x:.2f}) -> 按下D键")
        
        # 线程安全地更新目标按键
        with self.movement_lock:
            self.target_keys = new_target_keys
    
    # def init_virtual_joystick(self): # 删除虚拟手柄初始化
    #     """初始化虚拟手柄（用于发送数据到游戏）"""
    #     try:
    #         # 尝试加载vJoy库
    #         self.vjoy = ctypes.CDLL("vJoyInterface.dll")  # 加载vJoy动态链接库
    #         self.vjoy_available = True  # 设置vJoy可用标志
    #         print("vJoy虚拟手柄可用")  # 打印成功信息
    #     except:
    #         print("vJoy不可用，将使用键盘模拟")  # 打印失败信息
    #         self.vjoy_available = False  # 设置vJoy不可用标志
    
    def load_controller_config(self):
        """加载手柄配置文件"""
        try:
            with open('controller_config.json', 'r', encoding='utf-8') as f:  # 打开配置文件
                return json.load(f)  # 解析JSON配置
        except FileNotFoundError:  # 文件不存在异常
            print("未找到手柄配置文件，使用默认配置")  # 打印提示信息
            return {  # 返回默认配置
                "controller_name": "默认手柄",  # 手柄名称
                "button_mapping": {},  # 按钮映射
                "axis_mapping": {},  # 轴映射
                "hat_mapping": {},  # 帽子开关映射
                "keyboard_mapping": {}  # 键盘映射
            }
        except Exception as e:  # 其他异常
            print(f"加载手柄配置失败: {e}")  # 打印错误信息
            return {}  # 返回空配置
    
    def setup_ui(self):
        """设置用户界面"""
        # 主框架 - 美化背景
        main_frame = tk.Frame(self.root, bg="#F5F5F5", relief="flat", bd=0)
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # 标题 - 美化样式
        title_frame = tk.Frame(main_frame, bg="#2C3E50", relief="raised", bd=1)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        title_frame.columnconfigure(0, weight=1)
        
        title_label = tk.Label(title_frame, text="🎮 黑神话手柄录制器", 
                              font=("微软雅黑", 12, "bold"), 
                              bg="#2C3E50", fg="white", pady=5)
        title_label.grid(row=0, column=0)
        
        # 控制按钮框架 - 2x2布局，美化背景
        button_frame = tk.Frame(main_frame, bg="#F5F5F5", relief="flat", bd=0)
        button_frame.grid(row=1, column=0, pady=(0, 5))
        
        # 第一行按钮 - 使用图标和颜色
        self.record_btn = tk.Button(button_frame, text="⏺", font=("微软雅黑", 16, "bold"),
                                   bg="#FF6B6B", fg="white", relief="raised", bd=2,
                                   command=self.start_recording, width=4, height=2,
                                   cursor="hand2")
        self.record_btn.grid(row=0, column=0, padx=2, pady=2)
        
        # 录制按钮提示
        record_tip = tk.Label(button_frame, text="录制\n(Shift+F9)", 
                             font=("微软雅黑", 6), fg="#666666")
        record_tip.grid(row=0, column=0, padx=(0, 0), pady=(35, 0), sticky="s")
        
        self.play_btn = tk.Button(button_frame, text="▶", font=("微软雅黑", 16, "bold"),
                                 bg="#4ECDC4", fg="white", relief="raised", bd=2,
                                 command=self.play_latest_recording, width=4, height=2,
                                 cursor="hand2")
        self.play_btn.grid(row=0, column=1, padx=2, pady=2)
        
        # 播放按钮提示
        play_tip = tk.Label(button_frame, text="循环最近一次\n(Shift+F10)", 
                           font=("微软雅黑", 6), fg="#666666")
        play_tip.grid(row=0, column=1, padx=(0, 0), pady=(35, 0), sticky="s")
        
        # 第二行按钮
        self.list_btn = tk.Button(button_frame, text="📁", font=("微软雅黑", 16, "bold"),
                                 bg="#45B7D1", fg="white", relief="raised", bd=2,
                                 command=self.show_recordings_list, width=4, height=2,
                                 cursor="hand2")
        self.list_btn.grid(row=1, column=0, padx=2, pady=2)
        
        # 选择按钮提示
        list_tip = tk.Label(button_frame, text="选择", 
                           font=("微软雅黑", 6), fg="#666666")
        list_tip.grid(row=1, column=0, padx=(0, 0), pady=(35, 0), sticky="s")
        
        self.stop_btn = tk.Button(button_frame, text="⏹", font=("微软雅黑", 16, "bold"),
                                 bg="#96CEB4", fg="white", relief="raised", bd=2,
                                 command=self.stop_operations, width=4, height=2,
                                 cursor="hand2")
        self.stop_btn.grid(row=1, column=1, padx=2, pady=2)
        
        # 停止按钮提示
        stop_tip = tk.Label(button_frame, text="停止", 
                           font=("微软雅黑", 6), fg="#666666")
        stop_tip.grid(row=1, column=1, padx=(0, 0), pady=(35, 0), sticky="s")
        
        # 设置按钮悬停效果
        self.setup_button_hover_effects()
        

        
        # 状态显示 - 美化样式
        status_frame = tk.Frame(main_frame, bg="#F8F9FA", relief="sunken", bd=1)
        status_frame.grid(row=2, column=0, pady=(0, 5), sticky="ew")
        status_frame.columnconfigure(0, weight=1)
        
        # 状态标签
        self.status_label = tk.Label(status_frame, text="⏳ 等待操作...", 
                                    font=("微软雅黑", 9), bg="#F8F9FA", fg="#2C3E50")
        self.status_label.grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        
        # 手柄状态显示
        self.joystick_status = tk.Label(status_frame, text="🎮 手柄状态: 未连接", 
                                       font=("微软雅黑", 8), bg="#F8F9FA", fg="#7F8C8D")
        self.joystick_status.grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        
        # 进度条显示
        self.progress_label = tk.Label(status_frame, text="", 
                                      font=("微软雅黑", 7), bg="#F8F9FA", fg="#27AE60")
        self.progress_label.grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        
        # 手柄实时数据显示 - 美化样式
        joystick_frame = tk.Frame(main_frame, bg="#E8F5E8", relief="raised", bd=1)
        joystick_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 2))
        joystick_frame.columnconfigure(0, weight=1)
        joystick_frame.rowconfigure(1, weight=1)
        
        # 手柄数据标题
        joystick_title = tk.Label(joystick_frame, text="📊 手柄数据", 
                                 font=("微软雅黑", 8, "bold"), 
                                 bg="#4CAF50", fg="white", pady=2)
        joystick_title.grid(row=0, column=0, sticky="ew")
        
        self.joystick_data_text = scrolledtext.ScrolledText(joystick_frame, height=3, 
                                                           font=("Consolas", 7),
                                                           bg="#F1F8E9", fg="#2E7D32")
        self.joystick_data_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=2, pady=2)
        
        # 操作日志 - 美化样式
        log_frame = tk.Frame(main_frame, bg="#FFF3E0", relief="raised", bd=1)
        log_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)
        
        # 日志标题
        log_title = tk.Label(log_frame, text="📝 操作日志", 
                            font=("微软雅黑", 8, "bold"), 
                            bg="#FF9800", fg="white", pady=2)
        log_title.grid(row=0, column=0, sticky="ew")
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=3, 
                                                 font=("微软雅黑", 7),
                                                 bg="#FFF8E1", fg="#E65100")
        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=2, pady=2)
        
        # 底部信息 - 美化样式
        info_frame = tk.Frame(main_frame, bg="#E3F2FD", relief="sunken", bd=1)
        info_frame.grid(row=5, column=0, sticky="ew", pady=(2, 0))
        info_frame.columnconfigure(0, weight=1)
        
        info_label = tk.Label(info_frame, text="💾 录制文件保存在 recordings 文件夹中", 
                             font=("微软雅黑", 7), bg="#E3F2FD", fg="#1565C0")
        info_label.grid(row=0, column=0, pady=3)
        
        self.update_joystick_status()
        self.update_joystick_data_display()
    
    def setup_button_hover_effects(self):
        """设置按钮悬停效果和点击动画"""
        # 录制按钮悬停效果
        def on_record_enter(e):
            if self.record_btn['state'] != 'disabled':
                self.record_btn.config(bg="#FF5252")
        
        def on_record_leave(e):
            if self.record_btn['state'] != 'disabled':
                self.record_btn.config(bg="#FF6B6B")
        
        def on_record_click(e):
            # 点击动画效果
            self.record_btn.config(relief="sunken")
            self.root.after(100, lambda: self.record_btn.config(relief="raised"))
        
        self.record_btn.bind("<Enter>", on_record_enter)
        self.record_btn.bind("<Leave>", on_record_leave)
        self.record_btn.bind("<Button-1>", on_record_click)
        
        # 播放按钮悬停效果
        def on_play_enter(e):
            if self.play_btn['state'] != 'disabled':
                self.play_btn.config(bg="#26A69A")
        
        def on_play_leave(e):
            if self.play_btn['state'] != 'disabled':
                self.play_btn.config(bg="#4ECDC4")
        
        def on_play_click(e):
            # 点击动画效果
            self.play_btn.config(relief="sunken")
            self.root.after(100, lambda: self.play_btn.config(relief="raised"))
        
        self.play_btn.bind("<Enter>", on_play_enter)
        self.play_btn.bind("<Leave>", on_play_leave)
        self.play_btn.bind("<Button-1>", on_play_click)
        
        # 选择按钮悬停效果
        def on_list_enter(e):
            self.list_btn.config(bg="#1976D2")
        
        def on_list_leave(e):
            self.list_btn.config(bg="#45B7D1")
        
        def on_list_click(e):
            # 点击动画效果
            self.list_btn.config(relief="sunken")
            self.root.after(100, lambda: self.list_btn.config(relief="raised"))
        
        self.list_btn.bind("<Enter>", on_list_enter)
        self.list_btn.bind("<Leave>", on_list_leave)
        self.list_btn.bind("<Button-1>", on_list_click)
        
        # 停止按钮悬停效果
        def on_stop_enter(e):
            if self.stop_btn['state'] != 'disabled':
                self.stop_btn.config(bg="#66BB6A")
        
        def on_stop_leave(e):
            if self.stop_btn['state'] != 'disabled':
                self.stop_btn.config(bg="#96CEB4")
        
        def on_stop_click(e):
            # 点击动画效果
            self.stop_btn.config(relief="sunken")
            self.root.after(100, lambda: self.stop_btn.config(relief="raised"))
        
        self.stop_btn.bind("<Enter>", on_stop_enter)
        self.stop_btn.bind("<Leave>", on_stop_leave)
        self.stop_btn.bind("<Button-1>", on_stop_click)
    
    def setup_global_hotkeys(self):
        """设置全局热键 - 只保留Shift+F9录制和Shift+F10循环播放"""
        try:
            import keyboard as kb  # 导入keyboard库用于全局热键
            
            # 注册全局热键
            kb.add_hotkey('shift+f9', self.hotkey_start_recording, suppress=True)
            kb.add_hotkey('shift+f10', self.hotkey_play_latest, suppress=True)
            
            print("全局热键已注册: Shift+F9-F10")  # 调试信息
            print("Shift+F9: 开始录制")  # 调试信息
            print("Shift+F10: 循环最近一次")  # 调试信息
            
        except ImportError:
            print("keyboard库不可用，使用pynput热键")  # 调试信息
            # 备用方案：使用pynput
            self.shift_pressed = False  # 跟踪Shift键状态
            
            def on_key_press(key):
                try:
                    # 检测Shift键按下
                    if key == keyboard.Key.shift:
                        self.shift_pressed = True
                        print("Shift键按下")  # 调试信息
                        return
                    
                    # 检测F9-F10键
                    if self.shift_pressed:
                        print(f"检测到组合键: {key}")  # 调试信息
                        if key == keyboard.Key.f9:
                            print("触发Shift+F9 - 开始录制")  # 调试信息
                            self.root.after(0, self.start_recording)
                        elif key == keyboard.Key.f10:
                            print("触发Shift+F10 - 循环最近一次")  # 调试信息
                            self.root.after(0, self.play_latest_recording)
                except AttributeError as e:
                    print(f"热键处理错误: {e}")  # 调试信息
                    pass
            
            def on_key_release(key):
                # 检测Shift键释放
                if key == keyboard.Key.shift:
                    self.shift_pressed = False
                    print("Shift键释放")  # 调试信息
            
            # 创建键盘监听器
            self.keyboard_listener = keyboard.Listener(
                on_press=on_key_press,
                on_release=on_key_release
            )
            self.keyboard_listener.start()
            print("pynput热键监听器已启动")  # 调试信息
    
    def hotkey_start_recording(self):
        """热键回调：开始录制"""
        print("热键触发：开始录制")  # 调试信息
        self.root.after(0, self.start_recording)
    
    def hotkey_play_latest(self):
        """热键回调：循环最近一次"""
        print("热键触发：循环最近一次")  # 调试信息
        
        # 自动激活游戏窗口
        if self.find_and_activate_game_window():
            print("游戏窗口已激活，开始循环播放")
        else:
            print("无法激活游戏窗口，但仍继续播放")
        
        self.root.after(0, self.play_latest_recording)
    
    def hotkey_show_list(self):
        """热键回调：显示录制列表"""
        print("热键触发：显示录制列表")  # 调试信息
        self.root.after(0, self.show_recordings_list)
    
    def hotkey_stop_operations(self):
        """热键回调：停止所有操作"""
        print("🔥 热键触发：停止所有操作")  # 调试信息
        print(f"当前状态 - 录制: {self.is_recording}, 播放: {self.is_playing}")  # 调试信息
        
        # 直接调用停止操作
        self.root.after(0, self.stop_operations)
    
    def update_joystick_status(self):
        """更新手柄状态显示"""
        if self.joysticks:
            status_text = f"🎮 手柄状态: 已连接 ({len(self.joysticks)}个)"
            if self.is_recording:
                status_text += " - 🔴 录制中"
            elif self.is_playing:
                status_text += " - 🔵 循环播放中"
        else:
            status_text = "🎮 手柄状态: 未连接"
        
        self.joystick_status.config(text=status_text)
        
        # 更新进度条
        if self.is_recording:
            progress_text = "🔴 录制进度: " + "█" * (int(time.time() * 2) % 10 + 1)
            self.progress_label.config(text=progress_text)
        elif self.is_playing:
            progress_text = "🔵 播放进度: " + "█" * (int(time.time() * 2) % 10 + 1)
            self.progress_label.config(text=progress_text)
        else:
            self.progress_label.config(text="")
        
        self.root.after(100, self.update_joystick_status)
    
    def update_joystick_data_display(self):
        """更新手柄实时数据显示"""
        if not self.joysticks:
            self.joystick_data_text.delete(1.0, tk.END)
            self.joystick_data_text.insert(tk.END, "未检测到手柄")
            self.root.after(100, self.update_joystick_data_display)
            return
        
        # 实时获取手柄数据
        pygame.event.pump()  # 处理pygame事件
        
        display_text = ""
        for joystick in self.joysticks:
            joystick_id = joystick.get_id()
            
            # 实时获取手柄数据
            axes = [joystick.get_axis(i) for i in range(joystick.get_numaxes())]
            buttons = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]
            hats = [joystick.get_hat(i) for i in range(joystick.get_numhats())]
            
            # 更新当前数据
            if joystick_id in self.current_joystick_data:
                self.current_joystick_data[joystick_id]['axes'] = axes
                self.current_joystick_data[joystick_id]['buttons'] = buttons
                self.current_joystick_data[joystick_id]['hats'] = hats
                data = self.current_joystick_data[joystick_id]
            else:
                # 如果数据不存在，创建新的
                data = {
                    'name': joystick.get_name(),
                    'axes': axes,
                    'buttons': buttons,
                    'hats': hats
                }
                self.current_joystick_data[joystick_id] = data
            
            display_text += f"手柄 {joystick_id}: {data['name']}\n"
            display_text += "=" * 30 + "\n"
            
            # 显示轴数据
            axes_text = "摇杆/轴: "
            for i, axis in enumerate(data['axes']):
                if abs(axis) > 0.05:  # 降低阈值，显示更多数据
                    axis_name = self.get_axis_name(i)
                    axes_text += f"{axis_name}={axis:.2f} "
            if axes_text != "摇杆/轴: ":
                display_text += axes_text + "\n"
            
            # 显示按钮数据
            buttons_text = "按钮: "
            for i, button in enumerate(data['buttons']):
                if button:
                    button_name = self.get_button_name(i)
                    buttons_text += f"{button_name} "
            if buttons_text != "按钮: ":
                display_text += buttons_text + "\n"
            
            # 显示帽子开关数据
            hats_text = "方向键: "
            for i, hat in enumerate(data['hats']):
                if hat != (0, 0):
                    hat_name = self.get_hat_name(i)
                    direction = self.get_hat_direction(hat)
                    hats_text += f"{hat_name}={direction} "
            if hats_text != "方向键: ":
                display_text += hats_text + "\n"
            
            display_text += "\n"
        
        self.joystick_data_text.delete(1.0, tk.END)
        self.joystick_data_text.insert(tk.END, display_text)
        self.root.after(100, self.update_joystick_data_display)
    
    def get_axis_name(self, axis_index):
        """获取轴名称"""
        if 'axis_mapping' in self.controller_config:
            return self.controller_config['axis_mapping'].get(str(axis_index), {}).get('name', f'轴{axis_index}')
        return f'轴{axis_index}'
    
    def get_button_name(self, button_index):
        """获取按钮名称"""
        if 'button_mapping' in self.controller_config:
            return self.controller_config['button_mapping'].get(str(button_index), {}).get('name', f'按钮{button_index}')
        return f'按钮{button_index}'
    
    def get_hat_name(self, hat_index):
        """获取帽子开关名称"""
        if 'hat_mapping' in self.controller_config:
            return self.controller_config['hat_mapping'].get(str(hat_index), {}).get('name', f'帽子{hat_index}')
        return f'帽子{hat_index}'
    
    def get_hat_direction(self, hat_value):
        """获取帽子开关方向"""
        x, y = hat_value
        if x == 0 and y == -1:
            return "上"
        elif x == 0 and y == 1:
            return "下"
        elif x == -1 and y == 0:
            return "左"
        elif x == 1 and y == 0:
            return "右"
        elif x == -1 and y == -1:
            return "左上"
        elif x == 1 and y == -1:
            return "右上"
        elif x == -1 and y == 1:
            return "左下"
        elif x == 1 and y == 1:
            return "右下"
        else:
            return "中"
    
    def log_message(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        print(log_entry.strip())
    
    def start_recording(self):
        """开始录制手柄操作"""
        if self.is_recording:  # 检查是否已在录制中
            messagebox.showwarning("警告", "已经在录制中！")  # 显示警告对话框
            return  # 直接返回
        
        if self.is_playing:  # 检查是否正在播放
            self.stop_operations()  # 停止所有操作
        
        self.is_recording = True  # 设置录制状态为True
        self.recording_data = []  # 清空录制数据数组
        self.recording_start_time = time.time()  # 记录录制开始时间
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 生成时间戳
        self.current_recording_file = f"recording_{timestamp}.json"  # 设置当前录制文件名
        
        self.status_label.config(text="🔴 录制中... 按Shift+F12停止录制")  # 更新状态标签
        self.record_btn.config(state="disabled", bg="#CCCCCC")  # 禁用录制按钮
        self.log_message("开始录制手柄操作")  # 记录日志
        
        # 启动录制线程
        recording_thread = threading.Thread(target=self.recording_loop)  # 创建录制线程
        recording_thread.daemon = True  # 设置为守护线程
        recording_thread.start()  # 启动线程
    
    def recording_loop(self):
        """录制循环 - 持续采集手柄数据"""
        while self.is_recording:  # 当录制状态为True时循环
            pygame.event.pump()  # 处理pygame事件队列
            
            for joystick in self.joysticks:  # 遍历所有连接的手柄
                # 获取手柄轴数据
                axes = [joystick.get_axis(i) for i in range(joystick.get_numaxes())]  # 获取所有轴的值
                
                # 获取按钮状态
                buttons = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]  # 获取所有按钮状态
                
                # 获取帽子开关状态
                hats = [joystick.get_hat(i) for i in range(joystick.get_numhats())]  # 获取所有帽子开关状态
                
                # 更新当前手柄数据
                joystick_id = joystick.get_id()  # 获取手柄ID
                if joystick_id in self.current_joystick_data:  # 检查手柄数据是否存在
                    self.current_joystick_data[joystick_id]['axes'] = axes  # 更新轴数据
                    self.current_joystick_data[joystick_id]['buttons'] = buttons  # 更新按钮数据
                    self.current_joystick_data[joystick_id]['hats'] = hats  # 更新帽子开关数据
                
                # 记录数据
                current_time = time.time() - self.recording_start_time  # 计算当前时间
                data = {  # 创建数据字典
                    'time': current_time,  # 时间戳
                    'joystick_id': joystick.get_id(),  # 手柄ID
                    'axes': axes,  # 轴数据
                    'buttons': buttons,  # 按钮数据
                    'hats': hats  # 帽子开关数据
                }
                
                self.recording_data.append(data)  # 将数据添加到录制数组
            
            time.sleep(0.016)  # 约60FPS - 控制录制频率
    
    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            return
        
        print("🛑 停止录制")  # 调试信息
        self.is_recording = False
        
        # 保存录制数据
        if self.recording_data:
            file_path = os.path.join(self.recordings_dir, self.current_recording_file)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.recording_data, f, indent=2)
            
            self.log_message(f"录制完成，保存到: {self.current_recording_file}")
            self.log_message(f"录制时长: {len(self.recording_data) * 0.016:.2f}秒")
        
        self.status_label.config(text="⏳ 等待操作...")
        
        # 恢复所有按钮状态到正常
        self.record_btn.config(state="normal", bg="#FF6B6B")  # 恢复录制按钮
        self.play_btn.config(state="normal", bg="#4ECDC4")    # 恢复播放按钮
        self.list_btn.config(state="normal", bg="#45B7D1")    # 恢复列表按钮
        self.stop_btn.config(state="normal", bg="#96CEB4")    # 恢复停止按钮
        
        print("✅ 录制已停止，按钮状态已恢复")  # 调试信息
    
    def play_latest_recording(self):
        """播放最近一次录制"""
        recordings = self.get_recordings_list()
        if not recordings:
            self.log_message("没有找到录制文件")
            return
        
        latest_file = recordings[-1]  # 获取最新的录制文件
        self.log_message(f"开始循环最近一次: {latest_file}")
        self.play_recording(latest_file)
    
    def get_recordings_list(self):
        """获取录制文件列表"""
        if not os.path.exists(self.recordings_dir):
            return []
        
        files = []
        for file in os.listdir(self.recordings_dir):
            if file.endswith('.json'):
                files.append(file)
        
        return sorted(files)
    
    def show_recordings_list(self):
        """显示录制文件列表"""
        recordings = self.get_recordings_list()
        if not recordings:
            messagebox.showinfo("提示", "没有找到录制文件！")
            return
        
        # 创建选择窗口
        select_window = tk.Toplevel(self.root)
        select_window.title("选择录制文件")
        select_window.geometry("400x300")
        select_window.transient(self.root)
        select_window.grab_set()
        
        # 文件列表
        listbox = tk.Listbox(select_window, font=("微软雅黑", 10))
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for file in recordings:
            listbox.insert(tk.END, file)
        
        # 按钮框架
        button_frame = ttk.Frame(select_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        def play_selected():
            selection = listbox.curselection()
            if selection:
                selected_file = recordings[selection[0]]
                select_window.destroy()
                self.play_recording(selected_file)
        
        def cancel():
            select_window.destroy()
        
        ttk.Button(button_frame, text="播放", command=play_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=cancel).pack(side=tk.LEFT, padx=5)
        
        # 绑定回车键
        listbox.bind('<Double-Button-1>', lambda e: play_selected())
        listbox.bind('<Return>', lambda e: play_selected())
        
        # 默认选择第一个
        if recordings:
            listbox.selection_set(0)
    
    def play_recording(self, filename):
        """播放录制文件"""
        if self.is_playing:
            messagebox.showwarning("警告", "正在播放中！")
            return
        
        if self.is_recording:
            self.stop_recording()
        
        file_path = os.path.join(self.recordings_dir, filename)
        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"文件不存在: {filename}")
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                recording_data = json.load(f)
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败: {str(e)}")
            return
        

        
        self.is_playing = True
        self.status_label.config(text=f"🔵 循环播放中: {filename} - 按Shift+F12停止")
        
        # 设置按钮状态：禁用录制和播放按钮，但保持停止按钮可用
        self.record_btn.config(state="disabled", bg="#CCCCCC")
        self.play_btn.config(state="disabled", bg="#CCCCCC")
        self.list_btn.config(state="disabled", bg="#CCCCCC")
        # 停止按钮保持可用状态，确保热键和点击都能工作
        self.stop_btn.config(state="normal", bg="#96CEB4")
        
        self.log_message(f"开始循环播放: {filename}")
        
        # 启动移动控制线程（确保回放时摇杆移动正常工作）
        if not self.movement_running:
            self.start_movement_thread()
        
        # 启动播放线程
        play_thread = threading.Thread(target=self.playback_loop, args=(recording_data,))
        play_thread.daemon = True
        play_thread.start()
    
    def playback_loop(self, recording_data):
        """播放循环 - 支持循环播放"""
        if not recording_data:
            self.stop_playback()
            return
        
        try:
            print(f"开始播放，数据条数: {len(recording_data)}")  # 调试信息
            while self.is_playing and not self.force_stop:  # 循环播放，检查强制停止
                start_time = time.time()
                data_count = 0  # 调试计数器
                
                for data in recording_data:
                    # 每5条数据检查一次停止状态
                    if data_count % 5 == 0 and (not self.is_playing or self.force_stop):
                        print("检测到停止信号，退出播放循环")  # 调试信息
                        break
                    
                    data_count += 1
                    if data_count % 500 == 0:  # 每500条数据显示一次进度
                        print(f"播放进度: {data_count}/{len(recording_data)}")  # 调试信息
                    
                    # 等待到指定时间，但更频繁地检查停止状态
                    target_time = data['time']
                    current_time = time.time() - start_time
                    
                    # 将等待时间分成更小的片段，每0.001秒检查一次停止状态
                    while current_time < target_time and self.is_playing and not self.force_stop:
                        time.sleep(0.001)  # 减少到0.001秒
                        current_time = time.time() - start_time
                    
                    if not self.is_playing or self.force_stop:
                        print("检测到停止信号，退出数据循环")  # 调试信息
                        break
                    
                    # 发送手柄数据到游戏
                    self.send_joystick_data(data)
                
                # 如果还在播放状态且没有强制停止，继续下一轮循环
                if self.is_playing and not self.force_stop:
                    print("播放完成，开始循环播放...")  # 调试信息
                    self.log_message("播放完成，开始循环播放...")
                else:
                    print("播放已停止，退出循环")  # 调试信息
                    break
            
            # 播放结束
            self.stop_playback()
            
        except Exception as e:
            print(f"播放循环错误: {e}")
            self.log_message(f"播放错误: {e}")
            self.stop_playback()
    
    def send_joystick_data(self, data):
        """发送手柄数据到游戏"""
        joystick_id = data['joystick_id']
        axes = data['axes']
        buttons = data['buttons']
        hats = data['hats']
        
        # 更新当前手柄数据显示
        if joystick_id in self.current_joystick_data:
            self.current_joystick_data[joystick_id]['axes'] = axes
            self.current_joystick_data[joystick_id]['buttons'] = buttons
            self.current_joystick_data[joystick_id]['hats'] = hats
        
        # 直接使用键盘鼠标模拟
        self.send_keyboard_mouse_data(data)
    
    def send_keyboard_mouse_data(self, data):
        """通过键盘鼠标模拟发送数据 - 基于黑神话游戏操作"""
        try:
            axes = data['axes']
            buttons = data['buttons']
            hats = data['hats']
            
            # 左摇杆 (轴0, 轴1) - 移动控制
            left_x, left_y = axes[0], axes[1] if len(axes) > 1 else 0
            
            # 右摇杆 (轴2, 轴3) - 视角控制
            right_x, right_y = axes[2], axes[3] if len(axes) > 3 else 0
            
            # 触发器 (轴4, 轴5)
            left_trigger, right_trigger = axes[4], axes[5] if len(axes) > 5 else 0
            
            # 调试信息：显示摇杆数据
            if abs(left_x) > 0.1 or abs(left_y) > 0.1:
                print(f"摇杆数据 - X: {left_x:.2f}, Y: {left_y:.2f}")
            
            # 使用配置文件中的按钮映射
            button_mapping = {}
            if 'button_mapping' in self.controller_config:
                for btn_id, btn_info in self.controller_config['button_mapping'].items():
                    button_mapping[int(btn_id)] = btn_info.get('key', btn_info.get('name', ''))
            
            # 处理按钮 - 黑神话游戏按键映射
            for i, button in enumerate(buttons):
                if button and i in button_mapping:
                    key = button_mapping[i]
                    
                    # 检查是否应该停止
                    if not self.is_playing or self.force_stop:
                        break
                    
                    # A按钮 - 跳跃 (空格键)
                    if key == 'SPACE':
                        win32api.keybd_event(win32con.VK_SPACE, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(win32con.VK_SPACE, 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # B按钮 - 翻滚/闪身 (Ctrl键)
                    elif key == 'CTRL':
                        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # X按钮 - 轻攻击 (鼠标左键)
                    elif key == 'MOUSE_LEFT':
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    
                    # Y按钮 - 重攻击 (鼠标右键)
                    elif key == 'MOUSE_RIGHT':
                        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
                    
                    # LB按钮 - 饮酒 (R键)
                    elif key == 'R':
                        win32api.keybd_event(ord('R'), 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(ord('R'), 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # RB按钮 - 疾奔 (Shift键)
                    elif key == 'SHIFT':
                        win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # BACK按钮 - 菜单 (ESC键)
                    elif key == 'ESC':
                        win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # START按钮 - 照相模式 (P键)
                    elif key == 'P':
                        win32api.keybd_event(ord('P'), 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(ord('P'), 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # 左摇杆按下 - 锁定/取消锁定 (鼠标滚轮)
                    elif key == 'MOUSE_WHEEL':
                        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, 120, 0)
                        self.non_blocking_sleep(0.05)
                    
                    # 右摇杆按下 - 场景互动 (E键)
                    elif key == 'E':
                        win32api.keybd_event(ord('E'), 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(ord('E'), 0, win32con.KEYEVENTF_KEYUP, 0)
            
            # 检查是否应该停止
            if not self.is_playing or self.force_stop:
                return
            
            # 处理左摇杆移动 (WASD控制) - 使用线程机制实现流畅移动
            if abs(left_x) > 0.1 or abs(left_y) > 0.1:
                # 确保移动控制线程已启动
                if not self.movement_running:
                    self.start_movement_thread()
                
                # 更新移动目标按键（线程安全）
                self.update_movement_target(left_x, left_y)
            
            # 处理右摇杆 (视角控制 - 鼠标移动)
            if abs(right_x) > 0.1 or abs(right_y) > 0.1:
                move_x = int(right_x * 15)  # 增加灵敏度
                move_y = int(right_y * 15)
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)
            
            # 处理触发器
            if left_trigger > 0.5:
                # 左触发器 - 棍花展示 (V键)
                win32api.keybd_event(ord('V'), 0, 0, 0)
                self.non_blocking_sleep(0.05)
                win32api.keybd_event(ord('V'), 0, win32con.KEYEVENTF_KEYUP, 0)
            
            if right_trigger > 0.5:
                # 右触发器 - 法术释放 (需要配合方向键)
                pass
            
            # 处理帽子开关 (方向键) - 法术选择
            if hats and hats[0] != (0, 0):
                hat_x, hat_y = hats[0]
                if hat_y == -1:  # 上 - 法术1
                    win32api.keybd_event(ord('1'), 0, 0, 0)
                    self.non_blocking_sleep(0.05)
                    win32api.keybd_event(ord('1'), 0, win32con.KEYEVENTF_KEYUP, 0)
                elif hat_y == 1:  # 下 - 法术3
                    win32api.keybd_event(ord('3'), 0, 0, 0)
                    self.non_blocking_sleep(0.05)
                    win32api.keybd_event(ord('3'), 0, win32con.KEYEVENTF_KEYUP, 0)
                elif hat_x == -1:  # 左 - 法术4
                    win32api.keybd_event(ord('4'), 0, 0, 0)
                    self.non_blocking_sleep(0.05)
                    win32api.keybd_event(ord('4'), 0, win32con.KEYEVENTF_KEYUP, 0)
                elif hat_x == 1:  # 右 - 法术2
                    win32api.keybd_event(ord('2'), 0, 0, 0)
                    self.non_blocking_sleep(0.05)
                    win32api.keybd_event(ord('2'), 0, win32con.KEYEVENTF_KEYUP, 0)
                    
        except Exception as e:
            print(f"键盘鼠标模拟失败: {e}")
            self.log_message(f"发送数据失败: {e}")
    
    def non_blocking_sleep(self, duration):
        """非阻塞的睡眠，能够响应停止信号"""
        start_time = time.time()
        while time.time() - start_time < duration and self.is_playing and not self.force_stop:
            time.sleep(0.001)  # 每1毫秒检查一次停止状态
    
    def stop_playback(self):
        """停止播放"""
        print("🛑 停止播放")  # 调试信息
        self.is_playing = False
        self.force_stop = False # 确保强制停止标志被重置
        self.status_label.config(text="⏳ 等待操作...")
        
        # 恢复所有按钮状态到正常
        self.record_btn.config(state="normal", bg="#FF6B6B")  # 恢复录制按钮
        self.play_btn.config(state="normal", bg="#4ECDC4")    # 恢复播放按钮
        self.list_btn.config(state="normal", bg="#45B7D1")    # 恢复列表按钮
        self.stop_btn.config(state="normal", bg="#96CEB4")    # 恢复停止按钮
        
        # 清理移动控制线程和按键状态
        self.stop_movement_thread()
        self.release_all_keys()
        
        self.log_message("播放已停止")
        print("✅ 播放已停止，按钮状态已恢复")  # 调试信息
    
    def stop_operations(self):
        """停止所有操作"""
        print("🛑 执行停止所有操作")  # 调试信息
        
        if self.is_recording:
            print("停止录制...")  # 调试信息
            self.stop_recording()
        
        if self.is_playing:
            print("停止播放...")  # 调试信息
            self.stop_playback()
        
        # 停止移动控制线程
        print("停止移动控制线程...")  # 调试信息
        self.stop_movement_thread()
        
        # 释放所有当前按下的按键，避免按键卡住
        print("释放所有按键...")  # 调试信息
        self.release_all_keys()
        
        # 重置强制停止标志
        self.force_stop = False
        
        # 恢复所有按钮状态到正常
        print("恢复按钮状态...")  # 调试信息
        self.status_label.config(text="⏳ 等待操作...")
        self.record_btn.config(state="normal", bg="#FF6B6B")  # 恢复录制按钮
        self.play_btn.config(state="normal", bg="#4ECDC4")    # 恢复播放按钮
        self.list_btn.config(state="normal", bg="#45B7D1")    # 恢复列表按钮
        self.stop_btn.config(state="normal", bg="#96CEB4")    # 恢复停止按钮
        
        self.log_message("操作已停止")
        print("✅ 所有操作已停止，按钮状态已恢复")  # 调试信息
    

    
    def release_all_keys(self):
        """释放所有当前按下的按键"""
        try:
            for key in self.pressed_keys:
                if key == 'W':
                    win32api.keybd_event(ord('W'), 0, win32con.KEYEVENTF_KEYUP, 0)
                elif key == 'S':
                    win32api.keybd_event(ord('S'), 0, win32con.KEYEVENTF_KEYUP, 0)
                elif key == 'A':
                    win32api.keybd_event(ord('A'), 0, win32con.KEYEVENTF_KEYUP, 0)
                elif key == 'D':
                    win32api.keybd_event(ord('D'), 0, win32con.KEYEVENTF_KEYUP, 0)
                print(f"释放按键: {key}")
            
            # 清空按键状态
            self.pressed_keys.clear()
            print("所有按键已释放")
        except Exception as e:
            print(f"释放按键失败: {e}")

    def run(self):
        """运行程序"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.stop_operations()
        finally:
            # 确保程序退出时停止移动线程并释放所有按键
            self.stop_movement_thread()
            self.release_all_keys()
            if self.keyboard_listener:
                self.keyboard_listener.stop()
            pygame.quit()

if __name__ == "__main__":
    print("程序启动中...")  # 调试信息
    try:
        app = GameControllerRecorder()  # 创建应用实例
        print("应用实例创建成功")  # 调试信息
        app.run()  # 运行应用
    except Exception as e:
        print(f"程序启动失败: {e}")  # 调试信息
        import traceback
        traceback.print_exc()  # 打印详细错误信息 