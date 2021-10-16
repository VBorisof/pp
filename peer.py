import threading
import socket
import time
import random
import sys
import select
import numpy
import cv2
import pickle
import math
import sys
from PIL import Image, ImageQt
from PyQt6 import QtGui
from PyQt6.QtWidgets import (
    QApplication, QWidget,
    QHBoxLayout, QVBoxLayout,
    QPushButton,
    QLabel, QLineEdit,
)


def debug(message):
    is_debug = False
    if is_debug:
        print(f"[DEBUG] {message}")


class ConnectionInfo:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def to_string(self):
        return f"{self.ip}:{self.port}"


class Peer(QWidget):
    def __init__(self):
        super().__init__()
        self.initUi()
        self.max_size = 65000

    def connect(self):
        self.my_connection = ConnectionInfo(
            self.my_ip_line.text(),
            int(self.my_port_line.text())
        )
        self.peer_connection = ConnectionInfo(
            self.peer_ip_line.text(),
            int(self.peer_port_line.text())
        )
        print(f"FROM {self.my_connection.to_string()}")
        print(f"TO   {self.peer_connection.to_string()}")
        print(f"\n    ! ASSUMING DEFAULT(0) VIDEO FEED !\n")

        self.is_video_feed = True
        self.is_listening = True
        self.feed_thread = threading.Thread(target=lambda: self.start_video_feed(0))
        self.listen_thread = threading.Thread(target=self.feed_listen)

        self.feed_thread.start()
        self.listen_thread.start()

    def feed_listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.my_connection.ip, self.my_connection.port))
        while self.is_listening:
            ready = select.select([sock], [], [], 1)
            if ready[0]:
                data, addr = sock.recvfrom(self.max_size)
                if len(data) < 100:
                    frame_info = pickle.loads(data)

                    if frame_info:
                        num_packs = frame_info["packs"]

                        for i in range(num_packs):
                            data, addr = sock.recvfrom(self.max_size)

                            if i == 0:
                                buffer = data
                            else:
                                buffer += data

                        frame = numpy.frombuffer(buffer, dtype=numpy.uint8)
                        frame = frame.reshape(frame.shape[0], 1)
                        frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
                        frame = cv2.flip(frame, 1)

                        if frame is not None and type(frame) == numpy.ndarray:
                            img = Image.fromarray(frame, mode="RGB")
                            qt_img = ImageQt.ImageQt(img)
                            self.peer_video_label.setPixmap(
                                QtGui.QPixmap.fromImage(qt_img)
                            )
                            debug("Got data...")

    def start_video_feed(self, video_index):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        video = cv2.VideoCapture(video_index)
        if not video.isOpened():
            print("[!] Unable to open video feed.")
            return

        frame_ok, frame = video.read()
        while self.is_video_feed:
            retval, buffer = cv2.imencode(".jpg", frame)

            if retval:
                buffer = buffer.tobytes()
                buffer_size = len(buffer)

                num_packs = 1
                if buffer_size > self.max_size:
                    num_packs = math.ceil(buffer_size/self.max_size)

                frame_info = {"packs": num_packs}
                sock.sendto(
                    pickle.dumps(frame_info),
                    (self.peer_connection.ip, self.peer_connection.port)
                )

                debug(f"NUM FRAMES: {num_packs}")

                left = 0
                right = self.max_size
                for i in range(num_packs):
                    debug(f"Left: {left}")
                    debug(f"Right: {right}")

                    data = buffer[left:right]
                    left = right
                    right += self.max_size

                    sock.sendto(
                        data,
                        (self.peer_connection.ip, self.peer_connection.port)
                    )

            frame_ok, frame = video.read()

    def quit(self):
        print("Bye!")
        self.feed_thread.join()
        self.listen_thread.join()
        QApplication.instance().quit()

    def initUi(self):
        self.setGeometry(0, 0, 1000, 600)
        self.setWindowTitle("PP")

        self.my_ip_label = QLabel(self)
        self.my_ip_label.setText("Your ip:")
        self.my_ip_line = QLineEdit(self)
        my_ip_hbox = QHBoxLayout()
        my_ip_hbox.addStretch(1)
        my_ip_hbox.addWidget(self.my_ip_label)
        my_ip_hbox.addWidget(self.my_ip_line)

        self.my_port_label = QLabel(self)
        self.my_port_label.setText("Your port:")
        self.my_port_line = QLineEdit(self)
        my_port_hbox = QHBoxLayout()
        my_port_hbox.addStretch(1)
        my_port_hbox.addWidget(self.my_port_label)
        my_port_hbox.addWidget(self.my_port_line)

        self.peer_ip_label = QLabel(self)
        self.peer_ip_label.setText("Peer ip:")
        self.peer_ip_line = QLineEdit(self)
        peer_ip_hbox = QHBoxLayout()
        peer_ip_hbox.addStretch(1)
        peer_ip_hbox.addWidget(self.peer_ip_label)
        peer_ip_hbox.addWidget(self.peer_ip_line)

        self.peer_port_label = QLabel(self)
        self.peer_port_label.setText("Peer port:")
        self.peer_port_line = QLineEdit(self)
        peer_port_hbox = QHBoxLayout()
        peer_port_hbox.addStretch(1)
        peer_port_hbox.addWidget(self.peer_port_label)
        peer_port_hbox.addWidget(self.peer_port_line)

        self.connect_button = QPushButton("GO", self)
        self.connect_button.clicked.connect(self.connect)

        self.quit_button = QPushButton("Quit", self)
        self.quit_button.clicked.connect(self.quit)

        buttons_hbox = QHBoxLayout()
        buttons_hbox.addStretch(1)
        buttons_hbox.addWidget(self.connect_button)
        buttons_hbox.addWidget(self.quit_button)

        config_vbox = QVBoxLayout()
        config_vbox.addStretch(10)
        config_vbox.addLayout(my_ip_hbox)
        config_vbox.addLayout(my_port_hbox)
        config_vbox.addLayout(peer_ip_hbox)
        config_vbox.addLayout(peer_port_hbox)
        config_vbox.addLayout(buttons_hbox)

        self.peer_video_label = QLabel(self)
        self.peer_video_label.setGeometry(0, 0, 800, 600)
        viewport_vbox = QVBoxLayout()

        main_layout = QHBoxLayout()
        main_layout.addLayout(viewport_vbox)
        main_layout.addLayout(config_vbox)

        self.setLayout(main_layout)
        self.show()


def main():
    app = QApplication(sys.argv)
    w = Peer()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()

