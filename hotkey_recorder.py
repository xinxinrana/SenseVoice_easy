import keyboard
import sounddevice as sd
import numpy as np
import threading
import queue
import pyperclip
from funasr import AutoModel
import tkinter as tk
import time
from PIL import Image, ImageDraw
import pystray
import io
import re

class StatusIndicator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.withdraw()  # 隐藏主窗口
        
        # 创建系统托盘图标
        self.create_tray_icon()
        
        # 添加消息队列
        self.message_queue = queue.Queue()
        
        # 获取屏幕尺寸并计算合适的指示器大小
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.size = min(screen_width, screen_height) // 100  # 自适应大小，约为屏幕较小边的1%
        self.size = max(24, min(48, self.size))  # 限制大小在12-24之间
        
        # 设置窗口位置
        x = screen_width - self.size - 20
        y = screen_height - self.size - 60
        self.root.geometry(f'{self.size}x{self.size}+{x}+{y}')
        
        # 创建圆形指示器
        self.canvas = tk.Canvas(self.root, width=self.size, height=self.size,
                              bg='black', highlightthickness=0)
        self.canvas.pack()
        self.indicator = self.canvas.create_oval(2, 2, self.size-2, self.size-2,
                                               fill='gray')
        
        # 透明度控制
        self.last_active = time.time()
        self.check_activity()
        
        # 开始处理消息
        self.process_messages()
    
    def create_tray_icon(self):
        # 创建图标
        icon_size = 64
        image = Image.new('RGB', (icon_size, icon_size), 'black')
        draw = ImageDraw.Draw(image)
        draw.ellipse([2, 2, icon_size-2, icon_size-2], fill='gray')
        
        # 创建托盘图标
        self.tray_icon = pystray.Icon(
            "SenseVoice",
            image,
            "SenseVoice",
            menu=pystray.Menu(
                pystray.MenuItem("退出", self.quit_app)
            )
        )
        # 在新线程中启动托盘图标
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
    
    def quit_app(self):
        self.tray_icon.stop()
        self.root.quit()
    
    def process_messages(self):
        try:
            while True:
                try:
                    color = self.message_queue.get_nowait()
                    self.canvas.itemconfig(self.indicator, fill=color)
                    self.last_active = time.time()
                    self.root.attributes('-alpha', 1.0)
                except queue.Empty:
                    break
        finally:
            self.root.after(100, self.process_messages)
        
    def set_color(self, color):
        self.message_queue.put(color)
        # 更新托盘图标颜色
        icon_size = 64
        image = Image.new('RGB', (icon_size, icon_size), 'black')
        draw = ImageDraw.Draw(image)
        draw.ellipse([2, 2, icon_size-2, icon_size-2], fill=color)
        self.tray_icon.icon = image
        
    def check_activity(self):
        if time.time() - self.last_active > 5:  # 5秒后降低透明度
            self.root.attributes('-alpha', 0.2)
        self.root.after(1000, self.check_activity)
        
    def update(self):
        self.root.update()

# 初始化状态指示器
status_indicator = None

# 初始化模型
model = AutoModel(
    model="iic/SenseVoiceSmall",
    vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
    vad_kwargs={"max_single_segment_time": 30000},
    trust_remote_code=True,
)

# 录音参数
SAMPLE_RATE = 16000
is_recording = False
audio_queue = queue.Queue()
recording_lock = threading.Lock()

def callback(indata, frames, time, status):
    if status:
        print(status)
    if is_recording:
        audio_queue.put(indata.copy())

def process_audio():
    if status_indicator:
        status_indicator.set_color('red')  # 显示正在处理状态
    
    audio_data = []
    while not audio_queue.empty():
        audio_data.append(audio_queue.get())
    
    if audio_data:
        # 合并录音数据
        audio = np.concatenate(audio_data, axis=0)
        audio = audio.flatten()
        
        try:
            # 识别语音
            print("正在识别...")
            result = model.generate(
                input=audio,
                cache={},
                language="auto",
                use_itn=True,
                batch_size_s=60,
                merge_vad=True
            )
            text = result[0]["text"]
            print(f"识别结果: {text}")
            
            # 去除所有前缀标记
            text = re.sub(r'<\|.*?\|>', '', text)
            text = text.strip()
            
            ## 将结果复制到剪贴板
            # pyperclip.copy(text)
            # 直接输出到当前输入框框中
            keyboard.write(text)
            
            if status_indicator:
                status_indicator.set_color('green')  # 识别成功，显示绿色

            print("识别完成!")
            print(f"优化识别结果: {text}")
            # print("结果已复制到剪贴板")
        except Exception as e:
            if status_indicator:
                status_indicator.set_color('red')  # 发生错误，显示红色
            print(f"识别过程中出错: {str(e)}")

def start_recording():
    global is_recording
    with recording_lock:
        is_recording = True
        print("开始录音...")
        if status_indicator:
            status_indicator.set_color('yellow')

def stop_recording():
    global is_recording
    with recording_lock:
        is_recording = False
        print("录音结束...")
        # 在新线程中处理音频
        threading.Thread(target=process_audio).start()

def main():
    global status_indicator
    try:
        # 初始化状态指示器
        status_indicator = StatusIndicator()
        print("\n=== SenseVoice 语音识别助手 ===")
        print("正在初始化...")
        
        # 显示加载中状态
        status_indicator.set_color('yellow')
        status_indicator.root.update()
        
        # 创建录音流
        stream = sd.InputStream(
            channels=1,
            samplerate=SAMPLE_RATE,
            callback=callback,
            blocksize=8000
        )
        
        with stream:
            # 显示启动完成状态
            status_indicator.set_color('green')
            status_indicator.root.update()
            
            print("程序已在后台启动运行")
            print("1. 按住F8开始录音")
            print("2. 松开F8结束录音并进行识别")
            print("3. 按F7退出程序")
            print("-" * 50)
            
            keyboard.on_press_key("F8", lambda _: start_recording())
            keyboard.on_release_key("F8", lambda _: stop_recording())
            # keyboard.wait("F7")

            while True:
                try:
                    status_indicator.root.update()
                    if keyboard.is_pressed('F7'):
                        break
                except tk.TclError:
                    break
                time.sleep(0.1)
    
    except Exception as e:
        print(f"程序发生错误: {str(e)}")
    finally:
        if status_indicator:
            status_indicator.root.destroy()
        print("程序已退出")

if __name__ == "__main__":
    main()

