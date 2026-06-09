##New Code
import traceback
import sys
import time
import socket
import audioop
import subprocess

from threading import Thread
from six.moves import queue

import pyaudio
import os

os.chdir("/home/ITK/30052025")

from PyQt5.QtWidgets import (
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
    QPixmap,
    QMovie
)

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
    "/home/ITK/30052025/audiasync-project-050825-de67120821a2.json"
)

client = speech.SpeechClient(
    credentials=credentials,
    client_options={"api_endpoint": "speech.googleapis.com"}
)

inactivityduration = 30

# ===================== ADD THIS CLASS BEFORE WifiDialog =====================

class ClickableLabel(QLabel):

    clicked = pyqtSignal()

    def mousePressEvent(self, event):

        self.clicked.emit()

        super().mousePressEvent(event)

# =========================================================
# WIFI DIALOG
# =========================================================

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



# =========================================================
# MAIN APPLICATION
# =========================================================

class SpeechToTextApp(QMainWindow):

    text_signal = pyqtSignal(str)

    def __init__(self):

        super().__init__()

        self.voice_detected_time = 0
        self.voice_active = False

        self.labels = []

        self._rate = 16000
        self._chunk = int(self._rate / 10)

        self.closed = True
        self._is_listening = False

        self._last_audio_time = time.time()

        self._buff = queue.Queue()

        self._is_connected = True

        self.text_signal.connect(self.append_text)

        self.setWindowTitle("Real-Time Speech-to-Text")

        screen_rect = QDesktopWidget().screenGeometry()

        self.setGeometry(
            0,
            0,
            screen_rect.width(),
            screen_rect.height()
        )

        self.splash_label = QLabel(self)

        self.splash_label.setAlignment(Qt.AlignCenter)

        self.splash_movie = QMovie("/home/ITK/30052025/AudiaSyncIcon.gif")

        self.splash_movie.setScaledSize(screen_rect.size())

        self.splash_label.setMovie(self.splash_movie)

        self.splash_label.setGeometry(
            0,
            0,
            screen_rect.width(),
            screen_rect.height()
        )

        self.splash_movie.start()

        self.splash_label.show()

        self.splash_duration = 10000

        QTimer.singleShot(
            self.splash_duration,
            self.init_main_ui
        )

        self.splash_movie.finished.connect(
            self.init_main_ui
        )

    def init_main_ui(self):

        self.splash_label.hide()

        self.label = QLabel(
            "Press Button To Start Service Welcome to AudioSync ...",
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
            '/home/ITK/30052025/AudiaSyncIcon.png',
            '/home/ITK/30052025/MicIcon.png',
            '/home/ITK/30052025/MonitorDIsplayIcon.png',
            '/home/ITK/30052025/WifiTransmittingIcon.png'
        ]

        scroll_area = QScrollArea(self)

        scroll_area.setWidgetResizable(True)

        scroll_area.setWidget(self.label)

        layout = QVBoxLayout()

        Hlayout = QHBoxLayout()

        for path in self.image_paths:

            label = QLabel()
            if path == '/home/ITK/30052025/WifiTransmittingIcon.png':
                label = ClickableLabel()
                label.clicked.connect(self.open_wifi_dialog)
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

        self.container.setStyleSheet("""
            background-color: black;
            color: white;
        """)

        self.setCentralWidget(self.container)

        self._timer = QTimer(self)

        self._timer.timeout.connect(
            self._check_inactivity
        )

        self._timer.start(1000)

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

        QTimer.singleShot(1000, self.wait_for_trigger)

    # =========================================================
    # OPEN WIFI WINDOW
    # =========================================================

    def open_wifi_dialog(self):

        dialog = WifiDialog(self)

        dialog.exec_()

    def keyPressEvent(self, event):

        if event.key() == Qt.Key_Space:

            print("[INFO] Keyboard Trigger Pressed")

            self.text_signal.emit(
                "[INFO] Listening Started From Keyboard..."
            )

            self.start_audio_stream()

        super().keyPressEvent(event)

    def wait_for_trigger(self):

        if GPIO.input(button):

            print("[INFO] Trigger Pressed")

            self.text_signal.emit(
                "[INFO] Listening Started..."
            )

            self.start_audio_stream()

            return

        QTimer.singleShot(100, self.wait_for_trigger)

    def start_audio_stream(self):

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

        self.listen_thread = Thread(
            target=self.start_listening
        )

        self.listen_thread.daemon = True

        self.listen_thread.start()

        print("[INFO] Listening Started")

    def setup_audio(self):

        self._audio_interface = pyaudio.PyAudio()

        print("\n========== AUDIO DEVICES ==========\n")

        for i in range(
            self._audio_interface.get_device_count()
        ):

            info = self._audio_interface.get_device_info_by_index(i)

            print(i, info["name"])

        print("\n===================================\n")

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

        try:

            self._audio_stream.stop_stream()

            self._audio_stream.close()

            self._audio_interface.terminate()

        except Exception as e:

            print("Teardown error:", e)

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

                print("[VOICE DETECTED]")

                self.on_audio_detected()

            self._last_audio_time = time.time()

        else:

            if time.time() - self.voice_detected_time > 1.5:

                self.voice_active = False

                new_pixmap = QPixmap("/home/ITK/30052025/MicIcon.png")

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

        self._is_connected = connected

        pixmap_path = (
            "/home/ITK/30052025/WifiTransmittingIcon.png"
            if connected
            else
            "/home/ITK/30052025/WifiDisconnectedIcon.png"
        )

        new_pixmap = QPixmap(pixmap_path)

        self.labels[3].setPixmap(
            new_pixmap.scaled(
                130,
                130,
                Qt.KeepAspectRatio
            )
        )

    def _check_inactivity(self):

        global inactivityduration

        elapsed = time.time() - self._last_audio_time

        print(
            f"[DEBUG] No Audio Time: {elapsed:.2f} sec"
        )

        if self._is_listening and elapsed > inactivityduration:

            self.text_signal.emit(
                "No speech detected for 5 minutes."
            )

            self.text_signal.emit(
                "Listening stopped.Press Trig To Start Service Welcome to AudioSync Pluto...!"
            )

            print("[INFO] Auto Stop Listening")

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

            transcript = (
                result.alternatives[0].transcript
            )

            if result.is_final:

                print("TRANSCRIPT:", transcript)

                self.text_signal.emit(transcript)

                new_pixmap = QPixmap("/home/ITK/30052025/MicIcon.png")

                self.labels[1].setPixmap(
                    new_pixmap.scaled(
                        130,
                        130,
                        Qt.KeepAspectRatio
                    )
                )

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

        new_pixmap = QPixmap("/home/ITK/30052025/MicBlue.png")

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
                self.scroll_to_bottom
            )

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
