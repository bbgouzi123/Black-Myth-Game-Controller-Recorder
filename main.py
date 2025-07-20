import sys
import os
import json
import time
import threading
from datetime import datetime
from collections import deque

from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QFrame, QSizePolicy, QDesktopWidget)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QPainter
import psutil
import win32gui
import win32con
import win32api
import win32event
import win32process
import win32clipboard
import win32ui
import win32com.client
import win32api
import win32con
import win32gui
from inputs import get_gamepad
import vgamepad
import traceback

RECORDINGS_DIR = 'recordings'
if not os.path.exists(RECORDINGS_DIR):
    os.makedirs(RECORDINGS_DIR)

LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# 全局变量
is_recording = False
is_paused = False
is_replaying = False
recorded_data = []
replay_thread = None
current_log = deque(maxlen=100)

# 游戏进程名
GAME_PROCESS_NAME = 'b1-Win64-Shipping.exe'
GAME_WINDOW_TITLE = 'b1'

# 快捷键
HOTKEY_RECORD = 0x78  # F9
HOTKEY_REPLAY = 0x79  # F10
HOTKEY_STOP = 0x7A    # F11

# 高帧率定时快照录制线程
class GamepadRecorder(threading.Thread):
    def __init__(self, update_callback, record_callback, interval=0.005):
        super().__init__()
        self.update_callback = update_callback
        self.record_callback = record_callback
        self.interval = interval
        self.running = False
        self.recording = False
        self.paused = False
        self.daemon = True
        self.last_state = {'ABS_HAT0X': 0, 'ABS_HAT0Y': 0}  # 保证方向键有初始值

    def run(self):
        self.running = True
        while self.running:
            try:
                events = get_gamepad()
                hat0x_updated = False
                hat0y_updated = False
                for event in events:
                    self.last_state[event.code] = event.state
                    if event.code == 'ABS_HAT0X':
                        hat0x_updated = True
                    if event.code == 'ABS_HAT0Y':
                        hat0y_updated = True
                # 强制补全方向键状态
                if 'ABS_HAT0X' not in self.last_state:
                    self.last_state['ABS_HAT0X'] = 0
                if 'ABS_HAT0Y' not in self.last_state:
                    self.last_state['ABS_HAT0Y'] = 0
                # 每帧都写入方向键状态
                state_copy = self.last_state.copy()
                state_copy['ABS_HAT0X'] = self.last_state['ABS_HAT0X']
                state_copy['ABS_HAT0Y'] = self.last_state['ABS_HAT0Y']
                self.update_callback(state_copy)
                if self.recording and not self.paused:
                    self.record_callback(state_copy)
            except Exception:
                pass
            time.sleep(self.interval)

    def stop(self):
        self.running = False

    def start_record(self):
        self.recording = True
        self.paused = False

    def pause_record(self):
        self.paused = True

    def resume_record(self):
        self.paused = False

    def stop_record(self):
        self.recording = False
        self.paused = False

# 可拖动的 QTextEdit
class DraggableTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self._main_window = parent

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self._main_window.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self._main_window.move(event.globalPos() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

# 纯QPushButton按钮，主次分明，霓虹渐变
class IconButton(QPushButton):
    def __init__(self, icon, text, shortcut, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setCursor(Qt.PointingHandCursor)
        self.setText(f"{icon}\n{text} {shortcut}")
        self.setFont(QFont('Arial', 10, QFont.Normal))
        self.setStyleSheet('''
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00fff7, stop:1 #7f00ff);
                border-radius: 16px;
                color: #fff;
                font-weight: normal;
                letter-spacing: 1px;
                text-align: center;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7f00ff, stop:1 #00fff7);
                color: #00fff7;
            }
            QPushButton::menu-indicator { width:0; height:0; }
        ''')

# 主窗口
class MainWindow(QWidget):
    refresh_signal = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.replay_file = None
        self.replay_index = 0
        self.replay_total = 0
        self.record_start_time = None
        self.replay_start_time = None
        self._drag_pos = None

        self.setWindowTitle('黑神话手柄录制器')
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(300, 400)
        self.setWindowOpacity(0.9)
        self.init_ui()
        self.installEventFilter(self)
        self.refresh_signal.connect(self.refresh_ui)
        self.move_to_bottom_right()
        self.status = {'record': '未录制', 'replay': '未回放', 'stop': '空闲'}
        self.update_status()
        self.gamepad_info = {}
        self.recorded_data = []
        self.recorder = GamepadRecorder(self.update_gamepad_info, self.record_gamepad_data)
        self.recorder.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_ui)
        self.timer.start(100)
        self.log('程序已启动')
        self.register_hotkeys()

    def register_hotkeys(self):
        # 注册全局热键
        hwnd = int(self.winId())
        # F9
        win32gui.RegisterHotKey(hwnd, 1001, 0, win32con.VK_F9)
        # F10
        win32gui.RegisterHotKey(hwnd, 1002, 0, win32con.VK_F10)
        # F11
        win32gui.RegisterHotKey(hwnd, 1003, 0, win32con.VK_F11)

    def unregister_hotkeys(self):
        hwnd = int(self.winId())
        for hotkey_id in (1001, 1002, 1003):
            try:
                win32gui.UnregisterHotKey(hwnd, hotkey_id)
            except Exception:
                pass

    def nativeEvent(self, eventType, message):
        # 处理全局热键
        if eventType == 'windows_generic_MSG':
            msg = message
            msg = msg.__int__() if hasattr(msg, '__int__') else msg
            from ctypes import windll, c_void_p, byref
            import ctypes.wintypes
            MSG = ctypes.wintypes.MSG.from_address(msg)
            if MSG.message == win32con.WM_HOTKEY:
                hotkey_id = MSG.wParam
                if hotkey_id == 1001:
                    self.handle_record()
                elif hotkey_id == 1002:
                    self.handle_replay()
                elif hotkey_id == 1003:
                    self.handle_stop()
        return False, 0

    def init_ui(self):
        font = QFont('Consolas', 10)
        # 顶部关闭和最小化按钮
        self.btn_min = QPushButton('–')  # 全角破折号更居中
        self.btn_min.setFixedSize(32, 32)
        self.btn_min.setFont(QFont('Arial', 18, QFont.Bold))
        self.btn_min.setStyleSheet('''
            QPushButton {
                background: rgba(30,30,40,0.7);
                color: #00fff7;
                border: none;
                border-radius: 16px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(0,255,247,0.3);
                color: #fff;
            }
        ''')
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close = QPushButton('×')  # Unicode ×
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.setFont(QFont('Arial', 18, QFont.Bold))
        self.btn_close.setStyleSheet('''
            QPushButton {
                background: rgba(30,30,40,0.7);
                color: #ff3c3c;
                border: none;
                border-radius: 16px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(255,60,60,0.5);
                color: #fff;
            }
        ''')
        self.btn_close.clicked.connect(self.close)
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(self.btn_min)
        close_layout.addWidget(self.btn_close)
        close_layout.setContentsMargins(0, 0, 0, 0)
        # 上部：手柄信息
        self.label_gamepad = DraggableTextEdit(self)
        self.label_gamepad.setReadOnly(True)
        self.label_gamepad.setFont(font)
        self.label_gamepad.setMaximumHeight(120)
        self.label_gamepad.setStyleSheet('background: rgba(30,30,40,0.7); color: #00fff7; border-radius: 8px;')
        # 中部：日志
        self.label_log = DraggableTextEdit(self)
        self.label_log.setReadOnly(True)
        self.label_log.setFont(font)
        self.label_log.setMaximumHeight(120)
        self.label_log.setStyleSheet('background: rgba(30,30,40,0.7); color: #fff; border-radius: 8px;')
        # 下部：功能按钮（用自定义IconButton）
        self.btn_record = IconButton('🎥', '录制', 'F9', self)
        self.btn_replay = IconButton('🔁', '回放', 'F10', self)
        self.btn_stop = IconButton('⏹️', '停止', 'F11', self)
        self.btn_record.clicked.connect(self.handle_record)
        self.btn_replay.clicked.connect(self.handle_replay)
        self.btn_stop.clicked.connect(self.handle_stop)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_record)
        btn_layout.addWidget(self.btn_replay)
        btn_layout.addWidget(self.btn_stop)
        # 状态栏
        self.label_status = QLabel()
        self.label_status.setFont(QFont('Arial', 10))
        self.label_status.setStyleSheet('color: #00fff7; background: transparent;')
        # 总体布局
        layout = QVBoxLayout()
        layout.addLayout(close_layout)
        layout.addWidget(self.label_gamepad)
        layout.addWidget(self.label_log)
        layout.addLayout(btn_layout)
        layout.addWidget(self.label_status)
        self.setLayout(layout)
        self.setStyleSheet('background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f2027, stop:0.5 #2c5364, stop:1 #00fff7); border: 2px solid #00fff7; border-radius: 20px;')

    # 支持窗口拖动
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def refresh_ui(self):
        # 刷新手柄信息
        if self.gamepad_info:
            text = '\n'.join([f'{k}: {v}' for k, v in self.gamepad_info.items()])
        else:
            text = '未检测到手柄输入...'
        self.label_gamepad.setText(text)
        # 刷新日志，显示更多条目
        self.label_log.setText('\n'.join(list(current_log)[-20:]))
        self.label_log.moveCursor(self.label_log.textCursor().End)  # 自动滚动到底部
        # 刷新状态
        self.update_status()

    def update_gamepad_info(self, info):
        self.gamepad_info = info

    def record_gamepad_data(self, state):
        if is_recording and not is_paused:
            self.recorded_data.append({'ts': time.time(), 'data': state})

    def log(self, msg):
        now = datetime.now().strftime('%H:%M:%S')
        log_line = f'[{now}] {msg}'
        current_log.append(log_line)
        # 控制台美化输出
        if any(x in msg for x in ['出错', '失败', '异常', '错误']):
            prefix = '\033[91m[ERROR]\033[0m'  # 红色
        elif any(x in msg for x in ['未检测', '无法', '没有', '暂停']):
            prefix = '\033[93m[WARN]\033[0m'   # 黄色
        elif any(x in msg for x in ['开始', '保存', '停止', '完成', '进入', '回放', '录制']):
            prefix = '\033[92m[INFO]\033[0m'   # 绿色
        else:
            prefix = '[INFO]'
        print(f'{prefix} {log_line}')

    def update_status(self):
        # 状态栏详细信息
        mode = '空闲'
        if is_recording and not is_paused:
            mode = '录制中'
        elif is_recording and is_paused:
            mode = '录制暂停'
        elif is_replaying:
            mode = '回放中'
        # 录制时长
        rec_time = ''
        if is_recording and self.record_start_time:
            rec_time = f" 录制时长: {int(time.time() - self.record_start_time)}s"
        # 回放进度
        replay_info = ''
        if is_replaying and self.replay_total > 0:
            replay_info = f" 回放进度: {self.replay_index+1}/{self.replay_total} ({int((self.replay_index+1)/self.replay_total*100)}%)"
        # 当前文件
        file_info = ''
        if self.replay_file:
            file_info = f" 文件: {self.replay_file}"
        self.label_status.setText(f"模式: {mode}{rec_time}{replay_info}{file_info}")

    def handle_record(self):
        global is_recording, is_paused, is_replaying
        if is_replaying:
            is_replaying = False
            self.log('回放被F9中断，进入录制')
            self.update_status()
            self.refresh_signal.emit()
            is_recording = True
            is_paused = False
            self.recorded_data = []
            self.record_start_time = time.time()
            self.recorder.start_record()
            return
        if not is_recording:
            is_recording = True
            is_paused = False
            self.recorded_data = []
            self.record_start_time = time.time()
            self.recorder.start_record()
            self.log('开始录制手柄数据')
        elif is_recording and not is_paused:
            is_paused = True
            self.recorder.pause_record()
            self.log('录制已暂停')
        elif is_recording and is_paused:
            is_paused = False
            self.recorder.resume_record()
            self.log('继续录制')
        self.update_status()

    def handle_replay(self):
        global is_recording, is_replaying, replay_thread
        if is_recording:
            self.handle_stop()
        latest_file = self.get_latest_recording()
        if not latest_file:
            self.log('没有可回放的录制文件')
            return
        if not self.is_game_running():
            self.log('未检测到黑神话游戏进程')
            return
        if not self.activate_game_window():
            self.log('无法激活黑神话游戏窗口')
            return
        is_replaying = True
        self.replay_file = os.path.basename(latest_file)
        self.log(f'开始回放: {self.replay_file}')
        replay_thread = threading.Thread(target=self.replay_recording, args=(latest_file,))
        replay_thread.daemon = True
        replay_thread.start()
        self.update_status()

    def handle_stop(self):
        global is_recording, is_paused, is_replaying
        if is_recording:
            self.save_recording()
            is_recording = False
            is_paused = False
            self.recorder.stop_record()
            self.log('录制已保存并停止')
            self.record_start_time = None
        if is_replaying:
            is_replaying = False
            self.log('回放已停止')
            self.replay_file = None
            self.replay_index = 0
            self.replay_total = 0
            self.replay_start_time = None
            self.update_status()
            self.refresh_signal.emit()
        self.update_status()

    def save_recording(self):
        if self.recorded_data:
            filename = datetime.now().strftime('%Y-%m-%d-%H%M%S') + '.json'
            path = os.path.join(RECORDINGS_DIR, filename)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.recorded_data, f, ensure_ascii=False, indent=2)
            self.log(f'录制数据已保存: {filename}')

    def get_latest_recording(self):
        files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith('.json')]
        if not files:
            return None
        files.sort(reverse=True)
        return os.path.join(RECORDINGS_DIR, files[0])

    def is_game_running(self):
        for proc in psutil.process_iter(['name', 'exe', 'cmdline']):
            try:
                if proc.info['name'] == GAME_PROCESS_NAME or (proc.info['exe'] and GAME_PROCESS_NAME in proc.info['exe']):
                    return True
            except Exception:
                continue
        return False

    def activate_game_window(self):
        def enum_handler(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if GAME_WINDOW_TITLE in title:
                    result.append(hwnd)
        hwnds = []
        win32gui.EnumWindows(enum_handler, hwnds)
        if hwnds:
            try:
                win32gui.ShowWindow(hwnds[0], win32con.SW_RESTORE)
                # 尝试用 Alt 键激活窗口
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)  # 按下 Alt
                win32gui.SetForegroundWindow(hwnds[0])
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)  # 松开 Alt
                return True
            except Exception as e:
                self.log(f'激活游戏窗口失败: {e}')
                return False
        return False

    def replay_recording(self, filepath):
        global is_replaying
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.replay_total = len(data)
            gamepad = vgamepad.VX360Gamepad()
            self.replay_start_time = time.time()
            if not data:
                return
            base_ts = data[0]['ts']
            t0 = time.perf_counter()
            idx = 0
            while is_replaying:
                now = time.perf_counter()
                # 计算应播放到第几帧
                while idx < len(data):
                    target_time = t0 + (data[idx]['ts'] - base_ts)
                    if now < target_time:
                        break
                    # 推送数据到虚拟手柄
                    self.replay_index = idx
                    self.send_to_vgamepad(gamepad, data[idx]['data'])
                    gamepad.update()
                    self.refresh_signal.emit()
                    idx += 1
                if idx >= len(data):
                    if is_replaying:
                        self.log('回放完成，循环再次回放...')
                        self.refresh_signal.emit()
                        idx = 0
                        t0 = time.perf_counter()
                    else:
                        break
                # 精确sleep到下一帧
                if idx < len(data):
                    next_target = t0 + (data[idx]['ts'] - base_ts)
                    sleep_time = max(0, next_target - time.perf_counter())
                    if sleep_time > 0:
                        time.sleep(sleep_time)
            gamepad.reset()
            gamepad.update()
        except Exception as e:
            self.log(f'回放出错: {e}')
            self.save_error_log(traceback.format_exc())
        is_replaying = False
        self.update_status()
        self.refresh_signal.emit()

    def send_to_vgamepad(self, gamepad, info):
        btn_map = {
            'BTN_SOUTH': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A,
            'BTN_EAST': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B,
            'BTN_NORTH': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            'BTN_WEST': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X,
            'BTN_TL': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            'BTN_TR': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            'BTN_SELECT': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
            'BTN_START': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START,
            'BTN_THUMBL': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
            'BTN_THUMBR': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
        }
        # 先清空所有按钮
        gamepad.reset()
        # 按钮
        for k, v in info.items():
            if k in btn_map and v:
                gamepad.press_button(button=btn_map[k])
        # D-Pad方向键映射（用整数，兼容所有vgamepad版本）
        hat_x = info.get('ABS_HAT0X', 0)
        hat_y = info.get('ABS_HAT0Y', 0)
        dpad = 0  # NEUTRAL
        if hat_x == -1 and hat_y == 0:
            dpad = 4  # LEFT
        elif hat_x == 1 and hat_y == 0:
            dpad = 2  # RIGHT
        elif hat_x == 0 and hat_y == -1:
            dpad = 1  # UP
        elif hat_x == 0 and hat_y == 1:
            dpad = 3  # DOWN
        elif hat_x == -1 and hat_y == -1:
            dpad = 8  # UP_LEFT
        elif hat_x == 1 and hat_y == -1:
            dpad = 5  # UP_RIGHT
        elif hat_x == -1 and hat_y == 1:
            dpad = 7  # DOWN_LEFT
        elif hat_x == 1 and hat_y == 1:
            dpad = 6  # DOWN_RIGHT
        print(f'DPAD: {dpad}, HAT0X: {hat_x}, HAT0Y: {hat_y}')  # 调试输出
        gamepad._dpad_direction = dpad
        # D-Pad 方向只发送键盘，不发送手柄数据
        if dpad == 1:  # UP
            send_key(88)  # X
        elif dpad == 3:  # DOWN
            send_key(71)  # G
        elif dpad == 4:  # LEFT
            send_key(90)  # Z
        elif dpad == 2:  # RIGHT
            send_key(67)  # C
        elif dpad == 8:  # UP_LEFT
            send_key(88)  # X
            send_key(90)  # Z
        elif dpad == 5:  # UP_RIGHT
            send_key(88)  # X
            send_key(67)  # C
        elif dpad == 7:  # DOWN_LEFT
            send_key(71)  # G
            send_key(90)  # Z
        elif dpad == 6:  # DOWN_RIGHT
            send_key(71)  # G
            send_key(67)  # C
        else:
            # 如果没有 D-Pad 输入，使用正常的摇杆值
            lx = info.get('ABS_X', 0)
            ly = info.get('ABS_Y', 0)
            gamepad.left_joystick(x_value=lx, y_value=ly)

        # 摇杆 - 只有在没有 D-Pad 输入时才使用正常摇杆值
        if dpad == 0:  # 没有 D-Pad 输入时
            lx = info.get('ABS_X', 0)
            ly = info.get('ABS_Y', 0)
            gamepad.left_joystick(x_value=lx, y_value=ly)
        # 右摇杆始终使用正常值
        rx = info.get('ABS_RX', 0)
        ry = info.get('ABS_RY', 0)
        gamepad.right_joystick(x_value=rx, y_value=ry)
        # 触发器
        lt = info.get('ABS_Z', 0)
        rt = info.get('ABS_RZ', 0)
        gamepad.left_trigger(value=lt)
        gamepad.right_trigger(value=rt)


    def save_error_log(self, detail):
        filename = datetime.now().strftime('%Y-%m-%d-%H%M%S') + '.log'
        path = os.path.join(LOGS_DIR, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(detail)

    def eventFilter(self, obj, event):
        if event.type() == 6:  # QEvent.KeyPress
            key = event.key()
            if key == Qt.Key_F9:
                self.handle_record()
                return True
            elif key == Qt.Key_F10:
                self.handle_replay()
                return True
            elif key == Qt.Key_F11:
                self.handle_stop()
                return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self.recorder.stop()
        self.unregister_hotkeys()
        event.accept()

    def move_to_bottom_right(self):
        screen = QDesktopWidget().availableGeometry()
        size = self.geometry()
        x = screen.width() - self.width() - 20
        y = screen.height() - self.height() - 20
        self.move(x, y)

def send_key(key_code):
    try:
        win32api.keybd_event(key_code, 0, 0, 0)
        time.sleep(0.05)
        win32api.keybd_event(key_code, 0, win32con.KEYEVENTF_KEYUP, 0)
    except Exception as e:
        print(f"发送键盘按键失败: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_()) 