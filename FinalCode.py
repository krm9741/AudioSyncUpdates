import traceback
import sys
import time
import socket
import audioop
import json
import subprocess

from threading import Thread
from six.moves import queue

import pyaudio
import os
import re
import requests
from datetime import datetime

os.chdir("/opt/FinalCode")
SETTINGS_FILE = "/opt/FinalCode/display_settings.json"

from PyQt5.QtWidgets import (
    QColorDialog,
    QApplication,
    QSizePolicy,
    QHBoxLayout,
    QMainWindow,
    QVBoxLayout,
    QLabel,
    QWidget,
    QDesktopWidget,
    QScrollArea,
    QGraphicsOpacityEffect,
    QPushButton,
    QListWidget,
    QLineEdit,
    QMessageBox,
    QDialog
)

from PyQt5.QtCore import (
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    Qt,
    pyqtSignal
)

from PyQt5.QtGui import (
    QFont,
    QPixmap
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize

from google.cloud import speech
from google.oauth2 import service_account

try:
    from RPi import GPIO

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    button = 17
    led = 5

    GPIO.setup(button, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(led, GPIO.OUT)

    GPIO_AVAILABLE = True

except Exception:

    GPIO_AVAILABLE = False

    class FakeGPIO:

        BCM = None
        OUT = None
        IN = None
        PUD_DOWN = None

        def setmode(self, *args):
            pass

        def setwarnings(self, *args):
            pass

        def setup(self, *args, **kwargs):
            pass

        def input(self, *args):
            return False

        def output(self, *args):
            pass

    GPIO = FakeGPIO()


credentials = service_account.Credentials.from_service_account_file(
    "/opt/FinalCode/audiasync-project-050825-de67120821a2.json"
)

client = speech.SpeechClient(
    credentials=credentials,
    client_options={"api_endpoint": "speech.googleapis.com"}
)


def get_mac_address():
    try:
        print("Getting MAC Address",flush=True)
        output = subprocess.check_output("ifconfig", shell=True, text=True)
        mac_address = re.search(r"ether\s([0-9a-fA-F:]+)", output).group(1)
        return mac_address
    except subprocess.CalledProcessError:
        return "Error: Unable to run ifconfig command."
    except AttributeError:
        return "Error: MAC address not found in ifconfig output."
mac=get_mac_address()
mac = mac.replace(":", "-")
print(mac,flush=True)

inactivityduration = 30

def get_local_expiry():

    try:
        print("Getting Expiry data from Local",flush=True)

        with open(
            "/opt/FinalCode/subscription.json",
            "r"
        ) as f:

            data = json.load(f)

            return data["expiry"]

    except:

        return None

class ClickableLabel(QLabel):

    clicked = pyqtSignal()

    def mousePressEvent(self, event):

        self.clicked.emit()

        super().mousePressEvent(event)



class WifiDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setWindowTitle("WiFi Settings")

        self.setGeometry(300, 100, 500, 600)

        layout = QVBoxLayout()

        title = QLabel("Available WiFi Networks")

        title.setFont(QFont("Arial", 20))

        title.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)

        self.network_list = QListWidget()

        self.network_list.setStyleSheet("""
            background-color: black;
            color: white;
            font-size: 18px;
        """)

        layout.addWidget(self.network_list)

        self.password = QLineEdit()

        self.password.setPlaceholderText(
            "Enter WiFi Password"
        )

        self.password.setEchoMode(
            QLineEdit.Password
        )

        self.password.setStyleSheet("""
            font-size:18px;
            padding:10px;
        """)

        layout.addWidget(self.password)

        self.refresh_btn = QPushButton(
            "Refresh Networks"
        )

        self.connect_btn = QPushButton(
            "Connect WiFi"
        )

        button_style = """
            QPushButton{
                background-color:#222;
                color:white;
                font-size:18px;
                padding:15px;
                border-radius:10px;
            }

            QPushButton:hover{
                background-color:#444;
            }
        """

        self.refresh_btn.setStyleSheet(
            button_style
        )

        self.connect_btn.setStyleSheet(
            button_style
        )

        layout.addWidget(self.refresh_btn)

        layout.addWidget(self.connect_btn)

        self.setLayout(layout)

        self.refresh_btn.clicked.connect(
            self.scan_wifi
        )

        self.connect_btn.clicked.connect(
            self.connect_wifi
        )

        self.scan_wifi()

    def scan_wifi(self):

        self.network_list.clear()

        try:

            result = subprocess.check_output(
                [
                    "nmcli",
                    "-t",
                    "-f",
                    "SSID",
                    "dev",
                    "wifi"
                ],
                universal_newlines=True
            )

            networks = list(
                set(
                    result.strip().split("\n")
                )
            )

            networks.sort()

            for wifi in networks:

                if wifi.strip():

                    self.network_list.addItem(
                        wifi
                    )

        except Exception as e:

            QMessageBox.warning(
                self,
                "Error",
                str(e)
            )

    def connect_wifi(self):

        item = self.network_list.currentItem()

        if not item:

            QMessageBox.warning(
                self,
                "Error",
                "Please Select WiFi"
            )

            return

        ssid = item.text()

        password = self.password.text()

        try:

            subprocess.check_call([
                "nmcli",
                "dev",
                "wifi",
                "connect",
                ssid,
                "password",
                password
            ])

            QMessageBox.information(
                self,
                "Success",
                f"Connected to {ssid}"
            )

            self.accept()

        except Exception as e:

            QMessageBox.warning(
                self,
                "Connection Failed",
                str(e)
            )


class SetupPasswordDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setWindowTitle("Setup Access")
        self.setFixedSize(350, 180)

        layout = QVBoxLayout()

        title = QLabel("Enter Setup Password")
        title.setAlignment(Qt.AlignCenter)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)

        login_btn = QPushButton("Login")

        layout.addWidget(title)
        layout.addWidget(self.password_edit)
        layout.addWidget(login_btn)

        self.setLayout(layout)

        login_btn.clicked.connect(
            self.validate_password
        )

    def validate_password(self):

        SETUP_PASSWORD = "1234"

        if self.password_edit.text() == SETUP_PASSWORD:
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Access Denied",
                "Wrong Password"
            )

class SetupMenuDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.parent_window = parent

        self.setWindowTitle("Setup")
        self.setFixedSize(450, 250)

        layout = QVBoxLayout()

        title = QLabel("Setup Options")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 18))

        layout.addWidget(title)

        button_layout = QHBoxLayout()

        wifi_btn = QPushButton()
        text_btn = QPushButton()
        bg_btn = QPushButton()

        wifi_btn.setIcon(QIcon("/opt/FinalCode/WifiSetupIcon.png"))
        text_btn.setIcon(QIcon("/opt/FinalCode/TextColorIcon.png"))
        bg_btn.setIcon(QIcon("/opt/FinalCode/BackgroundColorIcon.png"))

        wifi_btn.setIconSize(QSize(80, 80))
        text_btn.setIconSize(QSize(80, 80))
        bg_btn.setIconSize(QSize(80, 80))

        wifi_btn.setFixedSize(120, 120)
        text_btn.setFixedSize(120, 120)
        bg_btn.setFixedSize(120, 120)

        button_layout.addWidget(wifi_btn)
        button_layout.addWidget(text_btn)
        button_layout.addWidget(bg_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        wifi_btn.clicked.connect(self.open_wifi)
        text_btn.clicked.connect(self.change_text_color)
        bg_btn.clicked.connect(self.change_background_color) 

    def open_wifi(self):

        wifi_dialog = WifiDialog(self)
        wifi_dialog.exec_()

    def change_text_color(self):

        color = QColorDialog.getColor()

        if color.isValid():

            self.parent_window.text_color = color.name()

            self.parent_window.apply_colors()
            self.parent_window.save_settings()

    def change_background_color(self):

        color = QColorDialog.getColor()

        if color.isValid():

            self.parent_window.background_color = color.name()

            self.parent_window.apply_colors()
            self.parent_window.save_settings()
            
class SpeechToTextApp(QMainWindow):

    text_signal = pyqtSignal(str)

    def __init__(self):

        super().__init__()

        self.voice_detected_time = 0
        self.voice_active = False
        self.load_settings()
        self.labels = []
        self._rate = 16000
        self._chunk = int(self._rate / 10)

        self.closed = True
        self._is_listening = False

        self._last_audio_time = time.time()

        self._buff = queue.Queue()

        self._is_connected = 0

        self.text_signal.connect(self.append_text)

        self.setWindowTitle("Real-Time Speech-to-Text")

        screen_rect = QDesktopWidget().screenGeometry()

        self.setGeometry(
            0,
            0,
            screen_rect.width(),
            screen_rect.height()
        )
        
        self.init_main_ui()
        self.subscription_retry_timer = QTimer(self)

        self.subscription_retry_timer.timeout.connect(
            self.retry_subscription_check
        )

    def load_settings(self):

        try:

            with open(SETTINGS_FILE, "r") as f:

                settings = json.load(f)

                self.text_color = settings.get(
                    "text_color",
                    "white"
                )

                self.background_color = settings.get(
                    "background_color",
                    "black"
                )

        except Exception:

            self.text_color = "white"
            self.background_color = "black"
    def apply_colors(self):
        self.container.setStyleSheet(f"""
            background-color: {self.background_color};
            color: {self.text_color};
        """)

        self.label.setStyleSheet(f"""
            color: {self.text_color};
            background-color: transparent;
        """)


    def save_settings(self):

        try:

            settings = {
                "text_color": self.text_color,
                "background_color": self.background_color
            }

            with open(SETTINGS_FILE, "w") as f:

                json.dump(
                    settings,
                    f,
                    indent=4
                )

        except Exception as e:

            print("Settings Save Error:", e,flush=True)

    def init_main_ui(self):

        self.label = QLabel(
            "Checking Subscription...",
            self
        )

        self.label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.label.setWordWrap(True)

        font = QFont("Arial", 30)

        self.label.setFont(font)

        self._internet_timer = QTimer(self)

        self._internet_timer.timeout.connect(
            self._check_internet_status
        )

        self._internet_timer.start(2000)

        self.image_paths = [
            '/opt/FinalCode/AudiaSyncIcon.png',
            '/opt/FinalCode/MicIcon.png',
            '/opt/FinalCode/MonitorDIsplayIcon.png',
            '/opt/FinalCode/WifiTransmittingIcon.png',
            '/opt/FinalCode/Setupicon.png'
        ]

        scroll_area = QScrollArea(self)

        scroll_area.setWidgetResizable(True)

        scroll_area.setWidget(self.label)

        layout = QVBoxLayout()

        Hlayout = QHBoxLayout()

        for path in self.image_paths:

            if path == '/opt/FinalCode/Setupicon.png':
                label = ClickableLabel()
                label.clicked.connect(self.open_setup_dialog)

            else:

                label = QLabel()
            pixmap = QPixmap(path)
            label.setPixmap(
                pixmap.scaled(
                    130,
                    130,
                    Qt.KeepAspectRatio
                )
            )
            label.setAlignment(Qt.AlignCenter)
            opacity_effect = QGraphicsOpacityEffect()
            label.setGraphicsEffect(opacity_effect)
            animation = QPropertyAnimation(
                opacity_effect,
                b"opacity"
            )

            animation.setDuration(200)
            animation.setStartValue(1.0)
            animation.setEndValue(0.0)
            animation.setEasingCurve(QEasingCurve.InOutQuad)
            self.labels.append(label)
            Hlayout.addWidget(label)

        layout.addLayout(Hlayout, stretch=2)
        layout.addWidget(scroll_area, stretch=8)
        self.container = QWidget(self)
        self.container.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        self.container.setLayout(layout)

        #self.container.setStyleSheet("""
        #    background-color: black;
        #    color: white;
        #""")

        self.setCentralWidget(self.container)

        self._timer = QTimer(self)

        self._timer.timeout.connect(
            self._check_inactivity
        )


        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self._rate,
            language_code="en-US",
            enable_automatic_punctuation=True,
        )

        self.streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=False
        )

        QTimer.singleShot(1000,
        self.verify_subscription_on_startup)

        self.apply_colors()
    
    def open_setup_dialog(self):

        password_dialog = SetupPasswordDialog(self)

        if password_dialog.exec_() == QDialog.Accepted:

            setup_dialog = SetupMenuDialog(self)

            setup_dialog.exec_()

    def open_wifi_dialog(self):

        dialog = WifiDialog(self)

        dialog.exec_()
    
    def is_system_ready(self):

        return (
            self._is_connected and
            self.subscription_status == 1
        )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:

            if not self.is_system_ready():

                print(
                    "[BLOCKED] Internet/Subscription check not complete",
                    flush=True
                )

                return

            print("[INFO] Keyboard Trigger Pressed", flush=True)

            self.start_audio_stream()

        super().keyPressEvent(event)

    def wait_for_trigger(self):
        GPIO.output(led,True)
        time.sleep(1)
        GPIO.output(led,False)
        time.sleep(1)
        if GPIO.input(button):

            if not self.is_system_ready():

                print(
                    "[BLOCKED] Internet/Subscription check not complete",
                    flush=True
                )

                return

            self.start_audio_stream()

            return

        QTimer.singleShot(100, self.wait_for_trigger)

    def start_audio_stream(self):
        if not self._is_connected:

            print(
                "[BLOCKED] No Internet",
                flush=True
            )

            return

        if self.subscription_status != 1:

            print(
                "[BLOCKED] Subscription Invalid",
                flush=True
            )

            return

        if self._is_listening:
            return

        while not self._buff.empty():

            try:
                self._buff.get_nowait()

            except:
                break

        self.setup_audio()

        self._is_listening = True

        self._last_audio_time = time.time()
        
        if not self._timer.isActive():
            self._timer.start(1000)


        self.listen_thread = Thread(
            target=self.start_listening
        )

        self.listen_thread.daemon = True

        self.listen_thread.start()

        print("[INFO] Listening Started",flush=True)

    def setup_audio(self):

        self._audio_interface = pyaudio.PyAudio()

        print("\n========== AUDIO DEVICES ==========\n",flush=True)

        for i in range(
            self._audio_interface.get_device_count()
        ):

            info = self._audio_interface.get_device_info_by_index(i)

            print(i, info["name"])

        print("\n===================================\n",flush=True)

        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._rate,
            input=True,
            input_device_index=1,
            frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )

        self.closed = False

    def teardown_audio(self):
        
        self._timer.stop()

        try:

            self._audio_stream.stop_stream()

            self._audio_stream.close()

            self._audio_interface.terminate()

        except Exception as e:

            print("Teardown error:", e,flush=True)

        self.closed = True

        self._is_listening = False

        try:
            self._buff.put_nowait(None)

        except:
            pass

    def _fill_buffer(
        self,
        in_data,
        frame_count,
        time_info,
        status_flags
    ):

        if not self._is_listening:
            return (None, pyaudio.paContinue)

        rms = audioop.rms(in_data, 2)

        RMS_THRESHOLD = 1100

        if rms > RMS_THRESHOLD:

            self.voice_detected_time = time.time()

            if not self.voice_active:

                self.voice_active = True

                print("[VOICE DETECTED]",flush=True)

                self.on_audio_detected()

            self._last_audio_time = time.time()

        else:

            if time.time() - self.voice_detected_time > 1.5:

                self.voice_active = False

                new_pixmap = QPixmap("/opt/FinalCode/MicIcon.png")

                self.labels[1].setPixmap(
                    new_pixmap.scaled(
                        130,
                        130,
                        Qt.KeepAspectRatio
                    )
                )

        self._buff.put(in_data)

        return (None, pyaudio.paContinue)

    def is_connected(
        self,
        host="8.8.8.8",
        port=53,
        timeout=2
    ):

        try:

            socket.setdefaulttimeout(timeout)

            socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            ).connect((host, port))

            return True

        except:
            return False

    def _check_internet_status(self):

        connected = self.is_connected()

        self._is_connected = 1

        pixmap_path = (
            "/opt/FinalCode/WifiTransmittingIcon.png"
            if connected
            else
            "/opt/FinalCode/WifiDisconnectedIcon.png"
        )

        new_pixmap = QPixmap(pixmap_path)

        self.labels[3].setPixmap(
            new_pixmap.scaled(
                130,
                130,
                Qt.KeepAspectRatio
            )
        )
    def update_expiry_from_github(self):

        if not self.is_connected():
            print("No Internet",flush=True)
            return False

        try:

            url = (
                "https://raw.githubusercontent.com/"
                "krm9741/AudioSyncUpdates/main/subscriptions/"
                f"{mac}.json"
                f"?t={int(time.time())}"
            )

            print("Downloading:", url,flush=True)

            response = requests.get(
            url,
            timeout=10,
            headers={
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            },
            verify=True
            )

            print("Status:", response.status_code,flush=True)
            print("Content:", response.text,flush=True)

            if response.status_code != 200:
                return False

            data = response.json()

            print("Data Received:", data,flush=True)

            with open(
                "/opt/FinalCode/subscription.json",
                "w"
            ) as f:

                json.dump(
                    data,
                    f,
                    indent=4
                )
            response.close()
            return True
        except Exception as e:

            print("Git Error:", e)
            return False
            
    def checkforsubscription(self):

        expiry_str = get_local_expiry()

        if not expiry_str:
            self.update_expiry_from_github()
            expiry_str = get_local_expiry()

            if not expiry_str:
                return 3

        today = datetime.now().date()
        expiry_date = datetime.strptime(
            expiry_str,
            "%Y-%m-%d"
        ).date()

        # Still valid locally
        if today <= expiry_date:
            return 1

        print("Local expiry reached",flush=True)

        # Check online once
        self.update_expiry_from_github()

        expiry_str = get_local_expiry()

        if not expiry_str:
            return 2

        expiry_date = datetime.strptime(
            expiry_str,
            "%Y-%m-%d"
        ).date()

        if today <= expiry_date:
            return 1
        return 2
        
        
    def retry_subscription_check(self):

        print("Checking GitHub for subscription update...")

        # Force fresh download from GitHub
        self.update_expiry_from_github()

        result = self.checkforsubscription()

        if result == 1:

            print("Subscription Updated Successfully")

            self.subscription_verified = True

            self.subscription_retry_timer.stop()

            if not self._timer.isActive():
                self._timer.start(1000)

            self.label.setText(
                "Subscription Verified.\n\n"
                "Press Button To Start Service "
                "Welcome to AudioSync..."
            )

            self.wait_for_trigger()

        elif result == 2:

            print("Subscription still expired")

        else:

            print("Machine not registered")
        
    def verify_subscription_on_startup(self):
        self.label.setText(
            "Checking Subscription..."
        )

        QApplication.processEvents()

        result = self.checkforsubscription()

        if result == 1:

            self.label.setText(
                "Subscription Verified.\n\n"
                "Press Button To Start Service "
                "Welcome to AudioSync..."
            )
            self.subscription_status = 1

            print("Subscription Verified",flush=True)
            pixmap_path = (
            "/opt/FinalCode/AudiaSyncIcon.png")
            new_pixmap = QPixmap(pixmap_path)

            self.labels[0].setPixmap(
                new_pixmap.scaled(
                    130,
                    130,
                    Qt.KeepAspectRatio
                )
            )
            if not self._timer.isActive():
                self._timer.start(1000)

        elif result == 2:

            self.subscription_status = 0
            self.label.setText(
                "Subscription Expired.\n\n"
                "Please Re-Subscribe For Further Usage."
            )
            pixmap_path = (
            "/opt/FinalCode/ExpiredAudiaSyncIcon.png"
            )
            new_pixmap = QPixmap(pixmap_path)

            self.labels[0].setPixmap(
                new_pixmap.scaled(
                    130,
                    130,
                    Qt.KeepAspectRatio
                )
            )

            print("Subscription Expired",flush=True)
            
            if not self.subscription_retry_timer.isActive():

                self.subscription_retry_timer.start(60000)

                print("Retry timer activated")

        else:

            self.subscription_status = 0
            self.label.setText(
                "Machine Not Registered.\n\n"
                "Please Contact Support."
            )
            pixmap_path = (
            "/opt/FinalCode/ExpiredAudiaSyncIcon.png"
            )
            new_pixmap = QPixmap(pixmap_path)

            self.labels[0].setPixmap(
                new_pixmap.scaled(
                    130,
                    130,
                    Qt.KeepAspectRatio
                )
            )

            print("Machine Not Registered",flush=True)
        #self.subscription_status = result
    
        
    def _check_inactivity(self):
        
        if not self._is_listening:
            return

        global inactivityduration

        elapsed = time.time() - self._last_audio_time

        print(
            f"[DEBUG] No Audio Time: {elapsed:.2f} sec",flush=True
        )

        if self._is_listening and elapsed > inactivityduration:

            self.text_signal.emit(
                "No speech detected for 5 minutes.")

            self.text_signal.emit(
                "Listening stopped.Press Button To Start Service Welcome to AudioSync...!")
            print("[INFO] Auto Stop Listening",flush=True)

            self.teardown_audio()

            QTimer.singleShot(
                1000,
                self.wait_for_trigger
            )

    def generator(self):

        while not self.closed:

            try:
                chunk = self._buff.get(timeout=1.0)

            except queue.Empty:

                continue

            if chunk is None:
                return

            yield chunk

    def listen_print_loop(self, responses):

        for response in responses:
            if not response.results:
                continue
            result = response.results[0]
            if not result.alternatives:
                continue
            print("Voice Found",flush=True)
            self._last_audio_time = time.time()
            if(self.subscription_status  == 1):
                transcript = result.alternatives[0].transcript
                print("Voice Converting to Text",flush=True)
                if result.is_final:
                    #current_text = self.label.text()
                    #self.label.setText(current_text+"\n"+f"{transcript}")
                    print(f"{transcript}")
                    self.append_text(f"{transcript}")
                    print("Txt printed")
                    new_pixmap = QPixmap("/opt/FinalCode/MicIcon.png")
                    self.labels[1].setPixmap(new_pixmap.scaled(130, 130, Qt.KeepAspectRatio))
                else:
                    self.append_text(f"{transcript}")
                    print(f"Interim: {transcript}",flush=True)
            elif(self.subscription_status  == 2):
                self.append_text("Please re subscribe for further usage")
            else:
                self.append_text("Please register machine for further usage")

    def start_listening(self):

        while not self.closed:

            if not self._is_connected:

                self.text_signal.emit(
                    "[INFO] Internet Offline..."
                )

                time.sleep(1)

                continue

            try:

                audio_generator = self.generator()

                requests = (
                    speech.StreamingRecognizeRequest(
                        audio_content=chunk
                    )
                    for chunk in audio_generator
                )

                responses = client.streaming_recognize(
                    self.streaming_config,
                    requests
                )

                self.listen_print_loop(responses)

            except Exception:

                import traceback

                traceback.print_exc()

                time.sleep(1)

    def on_audio_detected(self):

        new_pixmap = QPixmap("/opt/FinalCode/MicBlue.png")

        self.labels[1].setPixmap(
            new_pixmap.scaled(
                130,
                130,
                Qt.KeepAspectRatio
            )
        )

    def append_text(self, new_text):

        if len(new_text) != 0:

            current_text = self.label.text()

            updated_text = (
                current_text
                + "\n"
                + new_text
            )

            self.label.setText(updated_text)

            QTimer.singleShot(
                0,
                self.scroll_to_bottom)

    def scroll_to_bottom(self):

        scroll_area = self.findChild(QScrollArea)

        if scroll_area:

            scroll_area.verticalScrollBar().setValue(
                scroll_area.verticalScrollBar().maximum()
            )
    



if __name__ == "__main__":

    try:

        app = QApplication(sys.argv)

        window = SpeechToTextApp()

        window.show()

        sys.exit(app.exec_())

    except Exception:

        traceback.print_exc()

        input("Press Enter...")

