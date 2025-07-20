import tkinter as tk
from tkinter import ttk
import pygame
import json
import os
import threading
import time
from datetime import datetime
import win32api
import win32con
import win32gui
import win32process
import psutil

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
        self.is_recording = False
        self.is_playing = False
        self.force_stop = False
        self.recording_data = []
        self.current_recording_file = ""
        self.recording_start_time = 0
        
        # 手柄相关
        self.joysticks = []
        self.current_joystick_data = {}
        
        # 移动控制线程
        self.movement_running = False
        self.movement_thread = None
        self.movement_lock = threading.Lock()
        self.target_keys = set()
        self.pressed_keys = set()
        
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
        
        # 设置UI
        self.setup_ui()
        
        # 设置全局热键
        self.setup_global_hotkeys()

    def set_window_position(self):
        """设置窗口位置在屏幕右下角"""
        try:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = 400
            window_height = 600
            margin_x = 50
            margin_y = 80
            x_position = screen_width - window_width - margin_x
            y_position = screen_height - window_height - margin_y
            self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
            self.root.attributes('-topmost', True)
            print(f"窗口已定位到右下角: ({x_position}, {y_position})")
            print("窗口已设置为置顶")
        except Exception as e:
            print(f"设置窗口位置失败: {e}")
    
    def init_joysticks(self):
        """初始化手柄"""
        try:
            pygame.init()
            pygame.joystick.init()
            
            joystick_count = pygame.joystick.get_count()
            print(f"检测到 {joystick_count} 个设备")
            
            # 过滤真实手柄设备
            real_joysticks = []
            for i in range(joystick_count):
                joystick = pygame.joystick.Joystick(i)
                joystick.init()
                
                device_name = joystick.get_name()
                axes_count = joystick.get_numaxes()
                buttons_count = joystick.get_numbuttons()
                
                # 过滤条件：真实手柄通常有多个轴和按钮
                if axes_count >= 4 and buttons_count >= 8:
                    real_joysticks.append(joystick)
                    print(f"检测到真实手柄: {device_name} (轴:{axes_count}, 按钮:{buttons_count})")
                else:
                    print(f"过滤掉虚拟设备: {device_name} (轴:{axes_count}, 按钮:{buttons_count})")
            
            self.joysticks = real_joysticks
            print(f"实际使用 {len(self.joysticks)} 个真实手柄")
            
            # 初始化手柄数据
            for joystick in self.joysticks:
                self.current_joystick_data[joystick.get_id()] = {
                    'name': joystick.get_name(),
                    'axes': [0.0] * joystick.get_numaxes(),
                    'buttons': [False] * joystick.get_numbuttons(),
                    'hats': [(0, 0)] * joystick.get_numhats()
                }
                
        except Exception as e:
            print(f"手柄初始化失败: {e}")
            self.joysticks = []
    
    def load_controller_config(self):
        """加载手柄配置文件"""
        try:
            with open('controller_config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print("未找到手柄配置文件，使用默认配置")
            return {
                "controller_name": "默认手柄",
                "button_mapping": {},
                "axis_mapping": {},
                "hat_mapping": {},
                "keyboard_mapping": {}
            }
        except Exception as e:
            print(f"加载手柄配置失败: {e}")
            return {}

    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1A1A2E", relief="flat", bd=0)
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # 标题
        title_frame = tk.Frame(main_frame, bg="#16213E", relief="flat", bd=0)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        title_frame.columnconfigure(0, weight=1)
        
        title_label = tk.Label(title_frame, text="🎮 黑神话手柄录制器", 
                              font=("微软雅黑", 14, "bold"), 
                              bg="#16213E", fg="#00D4FF", pady=8)
        title_label.grid(row=0, column=0)
        
        # 控制按钮框架
        button_frame = tk.Frame(main_frame, bg="#1A1A2E", relief="flat", bd=0)
        button_frame.grid(row=1, column=0, pady=(0, 10))
        
        # 配置按钮框架的列权重
        for i in range(4):
            button_frame.columnconfigure(i, weight=1)
        
        # 录制按钮
        self.record_btn = tk.Button(button_frame, text="⏺", font=("微软雅黑", 18, "bold"),
                                   bg="#FF2E63", fg="white", relief="flat", bd=0,
                                   command=self.start_recording, width=3, height=2,
                                   cursor="hand2", activebackground="#FF1744",
                                   activeforeground="white")
        self.record_btn.grid(row=0, column=0, padx=3, pady=3, sticky="ew")
        
        # 录制按钮提示
        record_tip = tk.Label(button_frame, text="录制\nF1", 
                             font=("微软雅黑", 7, "bold"), fg="#FF6B9D", bg="#1A1A2E")
        record_tip.grid(row=1, column=0, pady=(2, 0))
        
        # 播放按钮
        self.play_btn = tk.Button(button_frame, text="▶", font=("微软雅黑", 18, "bold"),
                                 bg="#08D9D6", fg="white", relief="flat", bd=0,
                                 command=self.play_latest_recording, width=3, height=2,
                                 cursor="hand2", activebackground="#00BCD4",
                                 activeforeground="white")
        self.play_btn.grid(row=0, column=1, padx=3, pady=3, sticky="ew")
        
        # 播放按钮提示
        play_tip = tk.Label(button_frame, text="播放\nF2", 
                           font=("微软雅黑", 7, "bold"), fg="#64B5F6", bg="#1A1A2E")
        play_tip.grid(row=1, column=1, pady=(2, 0))
        
        # 选择按钮
        self.list_btn = tk.Button(button_frame, text="📁", font=("微软雅黑", 18, "bold"),
                                 bg="#252A34", fg="#00D4FF", relief="flat", bd=0,
                                 command=self.show_recordings_list, width=3, height=2,
                                 cursor="hand2", activebackground="#1976D2",
                                 activeforeground="white")
        self.list_btn.grid(row=0, column=2, padx=3, pady=3, sticky="ew")
        
        # 选择按钮提示
        list_tip = tk.Label(button_frame, text="选择文件\nF3", 
                           font=("微软雅黑", 7, "bold"), fg="#45B7D1", bg="#1A1A2E")
        list_tip.grid(row=1, column=2, pady=(2, 0))
        
        # 停止按钮
        self.stop_btn = tk.Button(button_frame, text="⏹", font=("微软雅黑", 18, "bold"),
                                 bg="#FF9F43", fg="white", relief="flat", bd=0,
                                 command=self.stop_operations, width=3, height=2,
                                 cursor="hand2", activebackground="#FF7043",
                                 activeforeground="white")
        self.stop_btn.grid(row=0, column=3, padx=3, pady=3, sticky="ew")
        
        # 停止按钮提示
        stop_tip = tk.Label(button_frame, text="停止\nF4", 
                           font=("微软雅黑", 7, "bold"), fg="#FFB74D", bg="#1A1A2E")
        stop_tip.grid(row=1, column=3, pady=(2, 0))
        
        # 设置按钮悬停效果
        self.setup_button_hover_effects()
        
        # 状态显示
        status_frame = tk.Frame(main_frame, bg="#16213E", relief="flat", bd=1)
        status_frame.grid(row=2, column=0, pady=(0, 10), sticky="ew")
        status_frame.columnconfigure(0, weight=1)
        
        # 状态标签
        self.status_label = tk.Label(status_frame, text="⏳ 等待操作...", 
                                    font=("微软雅黑", 9, "bold"), bg="#16213E", fg="#00D4FF")
        self.status_label.grid(row=0, column=0, sticky=tk.W, padx=8, pady=4)
        
        # 手柄状态显示
        self.joystick_status = tk.Label(status_frame, text="🎮 手柄状态: 未连接", 
                                       font=("微软雅黑", 8), bg="#16213E", fg="#FF6B9D")
        self.joystick_status.grid(row=1, column=0, sticky=tk.W, padx=8, pady=2)
        
        # 进度条显示
        self.progress_label = tk.Label(status_frame, text="", 
                                      font=("微软雅黑", 7), bg="#16213E", fg="#08D9D6")
        self.progress_label.grid(row=2, column=0, sticky=tk.W, padx=8, pady=2)
        
        # 手柄实时数据显示
        joystick_frame = tk.Frame(main_frame, bg="#0F3460", relief="flat", bd=1)
        joystick_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))
        joystick_frame.columnconfigure(0, weight=1)
        joystick_frame.rowconfigure(1, weight=1)
        
        # 手柄数据标题
        joystick_title = tk.Label(joystick_frame, text="📊 手柄数据", 
                                 font=("微软雅黑", 9, "bold"), 
                                 bg="#0F3460", fg="#00D4FF", pady=4)
        joystick_title.grid(row=0, column=0, sticky="ew")
        
        self.joystick_data_text = tk.Text(joystick_frame, height=4, 
                                         font=("Consolas", 8),
                                         bg="#1A1A2E", fg="#08D9D6",
                                         insertbackground="#00D4FF",
                                         selectbackground="#FF2E63",
                                         relief="flat", bd=0,
                                         state="disabled")
        self.joystick_data_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=3, pady=3)
        
        # 操作日志
        log_frame = tk.Frame(main_frame, bg="#0F3460", relief="flat", bd=1)
        log_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)
        
        # 日志标题
        log_title = tk.Label(log_frame, text="📝 操作日志", 
                            font=("微软雅黑", 9, "bold"), 
                            bg="#0F3460", fg="#00D4FF", pady=4)
        log_title.grid(row=0, column=0, sticky="ew")
        
        self.log_text = tk.Text(log_frame, height=4, 
                               font=("微软雅黑", 8),
                               bg="#1A1A2E", fg="#FF6B9D",
                               insertbackground="#00D4FF",
                               selectbackground="#FF2E63",
                               relief="flat", bd=0,
                               state="disabled")
        self.log_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=3, pady=3)
        
        # 底部信息
        info_frame = tk.Frame(main_frame, bg="#16213E", relief="flat", bd=1)
        info_frame.grid(row=5, column=0, sticky="ew", pady=(5, 0))
        info_frame.columnconfigure(0, weight=1)
        
        info_label = tk.Label(info_frame, text="💾 录制文件保存在 recordings 文件夹中", 
                             font=("微软雅黑", 8), bg="#16213E", fg="#08D9D6")
        info_label.grid(row=0, column=0, pady=4)
        
        self.update_joystick_status()
        self.update_joystick_data_display()

    def setup_button_hover_effects(self):
        """设置按钮悬停效果和点击动画"""
        # 录制按钮悬停效果
        def on_record_enter(e):
            if self.record_btn['state'] != 'disabled':
                self.record_btn.config(bg="#FF1744")
        
        def on_record_leave(e):
            if self.record_btn['state'] != 'disabled':
                self.record_btn.config(bg="#FF2E63")
        
        def on_record_click(e):
            original_bg = self.record_btn.cget('bg')
            self.record_btn.config(bg="#FF1744")
            self.root.after(100, lambda: self.record_btn.config(bg=original_bg))
        
        self.record_btn.bind("<Enter>", on_record_enter)
        self.record_btn.bind("<Leave>", on_record_leave)
        self.record_btn.bind("<Button-1>", on_record_click)
        
        # 播放按钮悬停效果
        def on_play_enter(e):
            if self.play_btn['state'] != 'disabled':
                self.play_btn.config(bg="#00BCD4")
        
        def on_play_leave(e):
            if self.play_btn['state'] != 'disabled':
                self.play_btn.config(bg="#08D9D6")
        
        def on_play_click(e):
            original_bg = self.play_btn.cget('bg')
            self.play_btn.config(bg="#00BCD4")
            self.root.after(100, lambda: self.play_btn.config(bg=original_bg))
        
        self.play_btn.bind("<Enter>", on_play_enter)
        self.play_btn.bind("<Leave>", on_play_leave)
        self.play_btn.bind("<Button-1>", on_play_click)
        
        # 选择按钮悬停效果
        def on_list_enter(e):
            self.list_btn.config(bg="#1976D2")
        
        def on_list_leave(e):
            self.list_btn.config(bg="#252A34")
        
        def on_list_click(e):
            original_bg = self.list_btn.cget('bg')
            self.list_btn.config(bg="#1976D2")
            self.root.after(100, lambda: self.list_btn.config(bg=original_bg))
        
        self.list_btn.bind("<Enter>", on_list_enter)
        self.list_btn.bind("<Leave>", on_list_leave)
        self.list_btn.bind("<Button-1>", on_list_click)
        
        # 停止按钮悬停效果
        def on_stop_enter(e):
            if self.stop_btn['state'] != 'disabled':
                self.stop_btn.config(bg="#FF7043")
        
        def on_stop_leave(e):
            if self.stop_btn['state'] != 'disabled':
                self.stop_btn.config(bg="#FF9F43")
        
        def on_stop_click(e):
            original_bg = self.stop_btn.cget('bg')
            self.stop_btn.config(bg="#FF7043")
            self.root.after(100, lambda: self.stop_btn.config(bg=original_bg))
        
        self.stop_btn.bind("<Enter>", on_stop_enter)
        self.stop_btn.bind("<Leave>", on_stop_leave)
        self.stop_btn.bind("<Button-1>", on_stop_click)
    
    def setup_global_hotkeys(self):
        """设置全局热键 - F1-F4四个快捷键"""
        try:
            import keyboard as kb
            
            # 注册全局热键
            kb.add_hotkey('f1', self.hotkey_start_recording, suppress=True)
            kb.add_hotkey('f2', self.hotkey_play_latest, suppress=True)
            kb.add_hotkey('f3', self.hotkey_show_list, suppress=True)
            kb.add_hotkey('f4', self.hotkey_stop_operations, suppress=True)
            
            print("全局热键已注册: F1-F4")
            print("F1: 开始录制")
            print("F2: 循环最近一次")
            print("F3: 显示录制列表")
            print("F4: 停止所有操作")
            
        except ImportError:
            print("keyboard库不可用，使用pynput热键")
            try:
                from pynput import keyboard
                
                def on_key_press(key):
                    try:
                        print(f"检测到按键: {key}")
                        if key == keyboard.Key.f1:
                            print("触发F1 - 开始录制")
                            self.root.after(0, self.start_recording)
                        elif key == keyboard.Key.f2:
                            print("触发F2 - 循环最近一次")
                            self.root.after(0, self.play_latest_recording)
                        elif key == keyboard.Key.f3:
                            print("触发F3 - 显示录制列表")
                            self.root.after(0, self.show_recordings_list)
                        elif key == keyboard.Key.f4:
                            print("触发F4 - 停止所有操作")
                            self.root.after(0, self.stop_operations)
                                
                    except AttributeError as e:
                        print(f"热键处理错误: {e}")
                        pass
                
                # 创建键盘监听器
                self.keyboard_listener = keyboard.Listener(
                    on_press=on_key_press
                )
                self.keyboard_listener.start()
                print("pynput热键监听器已启动")
                
            except ImportError:
                print("pynput库也不可用，热键功能将不可用")
    
    def hotkey_start_recording(self):
        """热键回调：开始录制"""
        print("热键触发：开始录制")
        self.root.after(0, self.start_recording)
    
    def hotkey_play_latest(self):
        """热键回调：循环最近一次"""
        print("热键触发：循环最近一次")
        if self.find_and_activate_game_window():
            print("游戏窗口已激活，开始循环播放")
        else:
            print("无法激活游戏窗口，但仍继续播放")
        self.root.after(0, self.play_latest_recording)
    
    def hotkey_show_list(self):
        """热键回调：显示录制列表"""
        print("热键触发：显示录制列表")
        self.root.after(0, self.show_recordings_list)
    
    def hotkey_stop_operations(self):
        """热键回调：停止所有操作"""
        print("热键触发：停止所有操作")
        self.root.after(0, self.stop_operations)

    def find_and_activate_game_window(self):
        """查找并激活黑神话游戏窗口"""
        try:
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
            def enum_windows_callback(hwnd, windows):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid == target_process.info['pid']:
                        if win32gui.IsWindowVisible(hwnd):
                            window_title = win32gui.GetWindowText(hwnd)
                            if window_title:
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
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetActiveWindow(hwnd)
                
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
                
                time.sleep(0.1)
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, 
                                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
                
                # 模拟点击窗口中心
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                    x = rect[0] + (rect[2] - rect[0]) // 2
                    y = rect[1] + (rect[3] - rect[1]) // 2
                    
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
    
    def update_joystick_status(self):
        """更新手柄状态显示"""
        if self.joysticks:
            status_text = f"🎮 手柄状态: 已连接 ({len(self.joysticks)}个真实手柄)"
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
            self.joystick_data_text.config(state="normal")
            self.joystick_data_text.delete(1.0, tk.END)
            self.joystick_data_text.insert(tk.END, "未检测到手柄")
            self.joystick_data_text.config(state="disabled")
            self.root.after(100, self.update_joystick_data_display)
            return
        
        # 实时获取手柄数据
        pygame.event.pump()
        
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
                if abs(axis) > 0.05:
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
        
        # 临时启用编辑，更新内容，然后重新禁用
        self.joystick_data_text.config(state="normal")
        self.joystick_data_text.delete(1.0, tk.END)
        self.joystick_data_text.insert(tk.END, display_text)
        self.joystick_data_text.config(state="disabled")
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
        
        # 临时启用编辑，插入内容，然后重新禁用
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        
        print(log_entry.strip())

    def start_recording(self):
        """开始录制手柄操作"""
        if self.is_recording:
            self.log_message("⚠️ 已经在录制中！")
            return
        
        if self.is_playing:
            self.stop_operations()
        
        self.is_recording = True
        self.recording_data = []
        self.recording_start_time = time.time()
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_recording_file = f"recording_{timestamp}.json"
        
        self.status_label.config(text="🔴 录制中... 按F4停止录制")
        self.record_btn.config(state="disabled", bg="#4A4A4A")
        self.log_message("开始录制手柄操作")
        
        # 启动录制线程
        recording_thread = threading.Thread(target=self.recording_loop)
        recording_thread.daemon = True
        recording_thread.start()
    
    def recording_loop(self):
        """录制循环 - 持续采集手柄数据"""
        while self.is_recording:
            pygame.event.pump()
            
            for joystick in self.joysticks:
                # 获取手柄轴数据
                axes = [joystick.get_axis(i) for i in range(joystick.get_numaxes())]
                
                # 获取按钮状态
                buttons = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]
                
                # 获取帽子开关状态
                hats = [joystick.get_hat(i) for i in range(joystick.get_numhats())]
                
                # 更新当前手柄数据
                joystick_id = joystick.get_id()
                if joystick_id in self.current_joystick_data:
                    self.current_joystick_data[joystick_id]['axes'] = axes
                    self.current_joystick_data[joystick_id]['buttons'] = buttons
                    self.current_joystick_data[joystick_id]['hats'] = hats
                
                # 记录数据
                current_time = time.time() - self.recording_start_time
                data = {
                    'time': current_time,
                    'joystick_id': joystick.get_id(),
                    'axes': axes,
                    'buttons': buttons,
                    'hats': hats
                }
                
                self.recording_data.append(data)
            
            time.sleep(0.016)  # 约60FPS
    
    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            return
        
        print("🛑 停止录制")
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
        self.record_btn.config(state="normal", bg="#FF2E63")
        self.play_btn.config(state="normal", bg="#08D9D6")
        self.list_btn.config(state="normal", bg="#252A34")
        self.stop_btn.config(state="normal", bg="#FF9F43")
        
        print("✅ 录制已停止，按钮状态已恢复")
    
    def play_latest_recording(self):
        """播放最近一次录制"""
        recordings = self.get_recordings_list()
        if not recordings:
            self.log_message("没有找到录制文件")
            return
        
        latest_file = recordings[-1]
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
        """显示录制文件列表 - 使用Treeview显示两列数据"""
        recordings = self.get_recordings_list()
        if not recordings:
            self.log_message("没有找到录制文件")
            return
        
        # 创建选择窗口
        select_window = tk.Toplevel(self.root)
        select_window.title("选择录制文件")
        select_window.geometry("600x400")
        select_window.transient(self.root)
        select_window.grab_set()
        
        # 设置窗口样式
        select_window.configure(bg="#1A1A2E")
        
        # 标题标签
        title_label = tk.Label(select_window, text="📁 录制文件列表", 
                              font=("微软雅黑", 12, "bold"), 
                              fg="#00D4FF", bg="#1A1A2E")
        title_label.pack(pady=(10, 5))
        
        # 创建Treeview框架
        tree_frame = tk.Frame(select_window, bg="#1A1A2E")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建Treeview
        tree = ttk.Treeview(tree_frame, columns=("文件名", "创建时间"), show="headings", height=15)
        
        # 设置列标题
        tree.heading("文件名", text="📄 文件名")
        tree.heading("创建时间", text="🕒 创建时间")
        
        # 设置列宽
        tree.column("文件名", width=350, anchor="w")
        tree.column("创建时间", width=200, anchor="center")
        
        # 设置样式
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", 
                       background="#2A2A3E", 
                       foreground="#FFFFFF", 
                       fieldbackground="#2A2A3E",
                       rowheight=25)
        style.configure("Treeview.Heading", 
                       background="#3A3A4E", 
                       foreground="#00D4FF",
                       font=("微软雅黑", 9, "bold"))
        
        # 创建滚动条
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局Treeview和滚动条
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 获取文件信息并排序
        file_info_list = []
        for filename in recordings:
            file_path = os.path.join(self.recordings_dir, filename)
            try:
                # 获取文件创建时间
                creation_time = os.path.getctime(file_path)
                creation_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(creation_time))
                file_info_list.append((filename, creation_time_str, creation_time))
            except:
                # 如果获取时间失败，使用文件名作为时间
                file_info_list.append((filename, "未知时间", 0))
        
        # 按创建时间排序，最新的在前面
        file_info_list.sort(key=lambda x: x[2], reverse=True)
        
        # 插入数据到Treeview
        for filename, creation_time_str, _ in file_info_list:
            tree.insert("", "end", values=(filename, creation_time_str))
        
        # 点击事件处理
        def on_item_click(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                filename = item['values'][0]  # 第一列是文件名
                select_window.destroy()
                self.play_recording(filename)
        
        # 双击事件处理
        def on_item_double_click(event):
            on_item_click(event)
        
        # 绑定点击事件
        tree.bind('<ButtonRelease-1>', on_item_click)
        tree.bind('<Double-Button-1>', on_item_double_click)
        tree.bind('<Return>', on_item_click)
        
        # 默认选择第一个文件
        if tree.get_children():
            first_item = tree.get_children()[0]
            tree.selection_set(first_item)
            tree.focus(first_item)
        
        # 关闭按钮
        close_btn = tk.Button(select_window, text="关闭", 
                             font=("微软雅黑", 10, "bold"),
                             fg="#FFFFFF", bg="#666666",
                             relief="flat", padx=20, pady=5,
                             command=select_window.destroy)
        close_btn.pack(pady=10)
        
        # 设置窗口焦点
        select_window.focus_set()
    
    def play_recording(self, filename):
        """播放录制文件"""
        if self.is_playing:
            self.log_message("⚠️ 正在播放中！")
            return
        
        if self.is_recording:
            self.stop_recording()
        
        file_path = os.path.join(self.recordings_dir, filename)
        if not os.path.exists(file_path):
            self.log_message(f"文件不存在: {filename}")
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                recording_data = json.load(f)
        except Exception as e:
            self.log_message(f"读取文件失败: {str(e)}")
            return
        
        self.is_playing = True
        self.status_label.config(text=f"🔵 循环播放中: {filename} - 按F4停止")
        
        # 设置按钮状态
        self.record_btn.config(state="disabled", bg="#4A4A4A")
        self.play_btn.config(state="disabled", bg="#4A4A4A")
        self.list_btn.config(state="disabled", bg="#4A4A4A")
        self.stop_btn.config(state="normal", bg="#FF9F43")
        
        self.log_message(f"开始循环播放: {filename}")
        
        # 启动移动控制线程
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
            print(f"开始播放，数据条数: {len(recording_data)}")
            while self.is_playing and not self.force_stop:
                start_time = time.time()
                data_count = 0
                
                for data in recording_data:
                    # 每条数据都检查停止状态
                    if not self.is_playing or self.force_stop:
                        print("检测到停止信号，退出播放循环")
                        break
                    
                    data_count += 1
                    if data_count % 500 == 0:
                        print(f"播放进度: {data_count}/{len(recording_data)}")
                    
                    # 等待到指定时间，但更频繁地检查停止状态
                    target_time = data['time']
                    current_time = time.time() - start_time
                    
                    # 将等待时间分成更小的片段，每0.0001秒检查一次停止状态
                    while current_time < target_time and self.is_playing and not self.force_stop:
                        time.sleep(0.0001)
                        current_time = time.time() - start_time
                    
                    if not self.is_playing or self.force_stop:
                        print("检测到停止信号，退出数据循环")
                        break
                    
                    # 发送手柄数据到游戏
                    self.send_joystick_data(data)
                
                # 如果还在播放状态且没有强制停止，继续下一轮循环
                if self.is_playing and not self.force_stop:
                    print("播放完成，开始循环播放...")
                    self.log_message("播放完成，开始循环播放...")
                else:
                    print("播放已停止，退出循环")
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
            # 首先检查是否应该停止
            if not self.is_playing or self.force_stop:
                return
                
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
                # 每个按钮操作前都检查停止状态
                if not self.is_playing or self.force_stop:
                    return
                    
                if button and i in button_mapping:
                    key = button_mapping[i]
                    
                    # A按钮 - 跳跃 (空格键)
                    if key == 'SPACE':
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(win32con.VK_SPACE, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(win32con.VK_SPACE, 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # B按钮 - 翻滚/闪身 (Ctrl键)
                    elif key == 'CTRL':
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # X按钮 - 轻攻击 (鼠标左键)
                    elif key == 'MOUSE_LEFT':
                        if not self.is_playing or self.force_stop: return
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        if not self.is_playing or self.force_stop: return
                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    
                    # Y按钮 - 重攻击 (鼠标右键)
                    elif key == 'MOUSE_RIGHT':
                        if not self.is_playing or self.force_stop: return
                        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        if not self.is_playing or self.force_stop: return
                        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
                    
                    # LB按钮 - 饮酒 (R键)
                    elif key == 'R':
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(ord('R'), 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(ord('R'), 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # RB按钮 - 疾奔 (Shift键)
                    elif key == 'SHIFT':
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # BACK按钮 - 菜单 (ESC键)
                    elif key == 'ESC':
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(win32con.VK_ESCAPE, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(win32con.VK_ESCAPE, 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # START按钮 - 照相模式 (P键)
                    elif key == 'P':
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(ord('P'), 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(ord('P'), 0, win32con.KEYEVENTF_KEYUP, 0)
                    
                    # 左摇杆按下 - 锁定/取消锁定 (鼠标滚轮)
                    elif key == 'MOUSE_WHEEL':
                        if not self.is_playing or self.force_stop: return
                        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, 120, 0)
                        self.non_blocking_sleep(0.05)
                    
                    # 右摇杆按下 - 场景互动 (E键)
                    elif key == 'E':
                        if not self.is_playing or self.force_stop: return
                        win32api.keybd_event(ord('E'), 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        if not self.is_playing or self.force_stop: return
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
                if not self.is_playing or self.force_stop: return
                move_x = int(right_x * 15)  # 增加灵敏度
                move_y = int(right_y * 15)
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)
            
            # 处理触发器
            if left_trigger > 0.5:
                if not self.is_playing or self.force_stop: return
                # 左触发器 - 棍花展示 (V键)
                win32api.keybd_event(ord('V'), 0, 0, 0)
                self.non_blocking_sleep(0.05)
                if not self.is_playing or self.force_stop: return
                win32api.keybd_event(ord('V'), 0, win32con.KEYEVENTF_KEYUP, 0)
            
            if right_trigger > 0.5:
                # 右触发器 - 法术释放 (需要配合方向键)
                pass
            
            # 处理帽子开关 (方向键) - 法术选择
            for hat in hats:
                if hat != (0, 0):
                    x, y = hat
                    if x == -1:  # 左
                        win32api.keybd_event(win32con.VK_LEFT, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(win32con.VK_LEFT, 0, win32con.KEYEVENTF_KEYUP, 0)
                    elif x == 1:  # 右
                        win32api.keybd_event(win32con.VK_RIGHT, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(win32con.VK_RIGHT, 0, win32con.KEYEVENTF_KEYUP, 0)
                    elif y == -1:  # 上
                        win32api.keybd_event(win32con.VK_UP, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(win32con.VK_UP, 0, win32con.KEYEVENTF_KEYUP, 0)
                    elif y == 1:  # 下
                        win32api.keybd_event(win32con.VK_DOWN, 0, 0, 0)
                        self.non_blocking_sleep(0.05)
                        win32api.keybd_event(win32con.VK_DOWN, 0, win32con.KEYEVENTF_KEYUP, 0)
                        
        except Exception as e:
            print(f"发送键盘鼠标数据错误: {e}")
    
    def start_movement_thread(self):
        """启动移动控制线程"""
        if self.movement_thread is None or not self.movement_thread.is_alive():
            self.movement_running = True
            self.movement_thread = threading.Thread(target=self.movement_control_loop, daemon=True)
            self.movement_thread.start()
            print("移动控制线程已启动")
    
    def stop_movement_thread(self):
        """停止移动控制线程"""
        self.movement_running = False
        if self.movement_thread and self.movement_thread.is_alive():
            self.movement_thread.join(timeout=1.0)
            print("移动控制线程已停止")
    
    def movement_control_loop(self):
        """移动控制线程主循环 - 实现流畅的按键发送"""
        while self.movement_running:
            try:
                with self.movement_lock:
                    current_target_keys = self.target_keys.copy()
                
                # 释放不再需要的按键
                keys_to_release = self.pressed_keys - current_target_keys
                for key in keys_to_release:
                    self.release_single_key(key)
                
                # 按下新需要的按键
                keys_to_press = current_target_keys - self.pressed_keys
                for key in keys_to_press:
                    self.press_single_key(key)
                
                # 更新当前按下的按键状态
                self.pressed_keys = current_target_keys.copy()
                
                # 线程休眠，控制发送频率（60Hz，约16.67ms）
                time.sleep(0.016)
                
            except Exception as e:
                print(f"移动控制线程错误: {e}")
                time.sleep(0.1)
    
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
        new_target_keys = set()
        
        # 增加摇杆死区，忽略轻微的偏移
        deadzone = 0.2  # 死区阈值
        
        # 根据摇杆位置确定需要按下的按键
        if left_y < -deadzone:  # 前进
            new_target_keys.add('W')
            print(f"摇杆向前 (Y={left_y:.2f}) -> 按下W键")
        elif left_y > deadzone:  # 后退
            new_target_keys.add('S')
            print(f"摇杆向后 (Y={left_y:.2f}) -> 按下S键")
        
        if left_x < -deadzone:  # 左移
            new_target_keys.add('A')
            print(f"摇杆向左 (X={left_x:.2f}) -> 按下A键")
        elif left_x > deadzone:  # 右移
            new_target_keys.add('D')
            print(f"摇杆向右 (X={left_x:.2f}) -> 按下D键")
        
        # 线程安全地更新目标按键
        with self.movement_lock:
            self.target_keys = new_target_keys
    
    def non_blocking_sleep(self, duration):
        """非阻塞睡眠，允许在睡眠期间响应停止信号"""
        start_time = time.time()
        while time.time() - start_time < duration:
            if not self.is_playing or self.force_stop:
                break
            time.sleep(0.001)
    
    def stop_playback(self):
        """停止播放"""
        print("🛑 停止播放")
        self.is_playing = False
        self.force_stop = True
        
        # 停止移动控制线程
        self.stop_movement_thread()
        
        # 释放所有按键
        self.release_all_keys()
        
        # 恢复按钮状态
        self.record_btn.config(state="normal", bg="#FF2E63")
        self.play_btn.config(state="normal", bg="#08D9D6")
        self.list_btn.config(state="normal", bg="#252A34")
        self.stop_btn.config(state="normal", bg="#FF9F43")
        
        self.status_label.config(text="⏳ 等待操作...")
        self.log_message("播放已停止")
        print("✅ 播放已停止，按钮状态已恢复")
    
    def stop_operations(self):
        """停止所有操作"""
        print("🛑 执行停止所有操作")
        
        # 停止录制
        if self.is_recording:
            print("停止录制...")
            self.stop_recording()
        
        # 停止播放
        if self.is_playing:
            print("停止播放...")
            self.stop_playback()
        
        # 停止移动控制线程
        print("停止移动控制线程...")
        self.stop_movement_thread()
        
        # 释放所有按键
        print("释放所有按键...")
        self.release_all_keys()
        
        # 恢复按钮状态
        print("恢复按钮状态...")
        self.record_btn.config(state="normal", bg="#FF2E63")
        self.play_btn.config(state="normal", bg="#08D9D6")
        self.list_btn.config(state="normal", bg="#252A34")
        self.stop_btn.config(state="normal", bg="#FF9F43")
        
        self.status_label.config(text="⏳ 等待操作...")
        self.log_message("操作已停止")
        print("✅ 所有操作已停止，按钮状态已恢复")
    
    def release_all_keys(self):
        """释放所有按键"""
        try:
            # 释放WASD键
            for key in ['W', 'A', 'S', 'D']:
                try:
                    if key == 'W':
                        win32api.keybd_event(ord('W'), 0, win32con.KEYEVENTF_KEYUP, 0)
                    elif key == 'A':
                        win32api.keybd_event(ord('A'), 0, win32con.KEYEVENTF_KEYUP, 0)
                    elif key == 'S':
                        win32api.keybd_event(ord('S'), 0, win32con.KEYEVENTF_KEYUP, 0)
                    elif key == 'D':
                        win32api.keybd_event(ord('D'), 0, win32con.KEYEVENTF_KEYUP, 0)
                except:
                    pass
            
            # 释放其他常用键
            keys_to_release = [
                win32con.VK_SPACE,    # 空格
                win32con.VK_CONTROL,  # Ctrl
                win32con.VK_SHIFT,    # Shift
                win32con.VK_ESCAPE,   # ESC
                ord('R'),             # R
                ord('E'),             # E
                ord('P'),             # P
                ord('V'),             # V
                win32con.VK_LEFT,     # 左箭头
                win32con.VK_RIGHT,    # 右箭头
                win32con.VK_UP,       # 上箭头
                win32con.VK_DOWN      # 下箭头
            ]
            
            for key in keys_to_release:
                try:
                    win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
                except:
                    pass
            
            # 释放鼠标按键
            try:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            except:
                pass
            
            print("所有按键已释放")
            
        except Exception as e:
            print(f"释放按键时出错: {e}")
    
    def run(self):
        """运行应用"""
        try:
            print("应用实例创建成功")
            self.root.mainloop()
        except KeyboardInterrupt:
            print("程序被用户中断")
        except Exception as e:
            print(f"程序运行错误: {e}")
        finally:
            # 程序退出时清理
            self.stop_operations()
            if self.keyboard_listener:
                self.keyboard_listener.stop()

# 主程序入口
if __name__ == "__main__":
    app = GameControllerRecorder()
    app.run()