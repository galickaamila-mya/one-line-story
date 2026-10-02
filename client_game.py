import sys
import json
import socket
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *


class NetworkThread(QThread):
    data_received = pyqtSignal(dict)
    connection_error = pyqtSignal(str)

    def __init__(self, sock):
        super().__init__()
        self.socket = sock
        self.running = True
        self.buffer = ""

    def run(self):
        while self.running:
            try:
                data = self.socket.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    break

                self.buffer += data

                # Ищем полные JSON объекты (разделенные \n)
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    line = line.strip()

                    if line:
                        try:
                            msg = json.loads(line)
                            self.data_received.emit(msg)
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e}")
                            print(f"Problematic line: {line}")

            except ConnectionResetError:
                self.connection_error.emit("Connection lost")
                break
            except Exception as e:
                self.connection_error.emit(str(e))
                break

    def stop(self):
        self.running = False


class NameInputWindow(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Заголовок
        title = QLabel("Добро пожаловать в игру!")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Поле ввода имени
        layout.addSpacing(20)
        name_label = QLabel("Введите ваше имя:")
        name_label.setFont(QFont("Arial", 12))
        layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Игрок")
        self.name_input.setMaxLength(20)
        self.name_input.setFixedWidth(200)
        self.name_input.setFont(QFont("Arial", 12))
        layout.addWidget(self.name_input)

        # Кнопка продолжения
        layout.addSpacing(20)
        self.continue_button = QPushButton("Продолжить")
        self.continue_button.setFixedWidth(150)
        self.continue_button.clicked.connect(self.on_continue)
        layout.addWidget(self.continue_button)

        self.setLayout(layout)
        self.setWindowTitle("Вход в игру")
        self.setFixedSize(400, 250)

    def on_continue(self):
        name = self.name_input.text().strip()
        if name:
            self.main_window.player_name = name
            self.main_window.show_room_window()
        else:
            QMessageBox.warning(self, "Ошибка", "Введите имя!")


class RoomWindow(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Заголовок
        title = QLabel("Выбор комнаты")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(20)

        # Блок подключения
        connect_group = QGroupBox("Подключиться к комнате")
        connect_layout = QVBoxLayout()

        self.room_id_input = QLineEdit()
        self.room_id_input.setPlaceholderText("ID комнаты")
        self.room_id_input.setMaxLength(36)
        connect_layout.addWidget(self.room_id_input)

        self.connect_button = QPushButton("Подключиться")
        self.connect_button.clicked.connect(self.on_connect)
        connect_layout.addWidget(self.connect_button)

        connect_group.setLayout(connect_layout)
        layout.addWidget(connect_group)

        layout.addSpacing(20)

        # Блок создания
        create_group = QGroupBox("Создать новую комнату")
        create_layout = QVBoxLayout()

        size_layout = QHBoxLayout()
        size_label = QLabel("Размер комнаты:")
        size_label.setFont(QFont("Arial", 10))
        size_layout.addWidget(size_label)

        self.size_input = QSpinBox()
        self.size_input.setRange(2, 10)
        self.size_input.setValue(4)
        size_layout.addWidget(self.size_input)
        size_layout.addStretch()

        create_layout.addLayout(size_layout)

        self.create_button = QPushButton("Создать")
        self.create_button.clicked.connect(self.on_create)
        create_layout.addWidget(self.create_button)

        create_group.setLayout(create_layout)
        layout.addWidget(create_group)

        layout.addSpacing(20)

        # Кнопка назад
        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.main_window.show_name_window)
        layout.addWidget(back_button)

        self.setLayout(layout)
        self.setWindowTitle("Выбор комнаты")
        self.setFixedSize(400, 400)

    def on_connect(self):
        room_id = self.room_id_input.text().strip()
        if not room_id:
            QMessageBox.warning(self, "Ошибка", "Введите ID комнаты!")
            return

        self.connect_button.setEnabled(False)
        self.connect_button.setText("Подключение...")
        QApplication.processEvents()

        try:
            self.main_window.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.main_window.socket.connect(('127.0.0.1', 12346))

            message = {
                "action": "join",
                "player_name": self.main_window.player_name,
                "room_id": room_id
            }
            self.main_window.socket.sendall((json.dumps(message) + '\n').encode('utf-8'))

            self.main_window.show_game_window()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось подключиться: {str(e)}")
            self.connect_button.setEnabled(True)
            self.connect_button.setText("Подключиться")

    def on_create(self):
        size = self.size_input.value()

        self.create_button.setEnabled(False)
        self.create_button.setText("Создание...")
        QApplication.processEvents()

        try:
            self.main_window.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.main_window.socket.connect(('127.0.0.1', 12346))

            message = {
                "action": "create",
                "player_name": self.main_window.player_name,
                "size": size
            }
            self.main_window.socket.sendall((json.dumps(message) + '\n').encode('utf-8'))

            self.main_window.show_game_window()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать комнату: {str(e)}")
            self.create_button.setEnabled(True)
            self.create_button.setText("Создать")


class GameWindow(QWidget):

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.game_data = {}
        self.network_thread = None
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()

        # Панель статуса
        self.status_panel = QGroupBox()
        status_layout = QHBoxLayout()

        self.status_label = QLabel("Статус: Сервер не нашел комнату")
        self.players_label = QLabel("Игроки: -")

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.players_label)

        self.status_panel.setLayout(status_layout)
        self.layout.addWidget(self.status_panel)

        # Основная область
        self.story_area = QTextEdit()
        self.story_area.setReadOnly(True)
        self.story_area.setFont(QFont("Arial", 11))
        self.layout.addWidget(self.story_area, 1)

        # Поле ввода (видимо только при статусе 0)
        self.input_group = QGroupBox("Ваша история")
        input_layout = QVBoxLayout()

        self.last_line_label = QLabel("Последняя строка:")
        input_layout.addWidget(self.last_line_label)

        self.input_text = QTextEdit()
        self.input_text.setMaximumHeight(80)
        self.input_text.textChanged.connect(self.on_text_changed)
        input_layout.addWidget(self.input_text)

        self.char_count_label = QLabel("0/100 символов")
        self.char_count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        input_layout.addWidget(self.char_count_label)

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.on_send)
        self.send_button.setEnabled(False)
        input_layout.addWidget(self.send_button)

        self.input_group.setLayout(input_layout)
        self.layout.addWidget(self.input_group)

        # Кнопка "Далее" (видима только при статусе 1)
        self.next_button = QPushButton("Далее")
        self.next_button.clicked.connect(self.on_next)
        self.next_button.setVisible(False)
        self.layout.addWidget(self.next_button)

        self.setLayout(self.layout)
        self.setWindowTitle("Игра")
        self.setMinimumSize(400, 300)

        self.start_network_thread()

    def on_text_changed(self):
        text = self.input_text.toPlainText()
        if len(text) > 100:
            text = text[:100]
            self.input_text.setPlainText(text)
            cursor = self.input_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.input_text.setTextCursor(cursor)

        self.char_count_label.setText(f"{len(text)}/100 символов")

        self.send_button.setEnabled(
            bool(text.strip()) and
            self.game_data.get('player_status', 1) == 0
        )

    def on_send(self):
        text = self.input_text.toPlainText().strip()
        if not text:
            return

        message = {
            "action": "write",
            "room_id": self.game_data.get('room_id'),
            "line": text
        }

        try:
            self.main_window.socket.sendall((json.dumps(message) + '\n').encode('utf-8'))
            self.input_text.clear()
            self.send_button.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось отправить: {str(e)}")

    def on_next(self):
        message = {
            "action": "next_story",
            "room_id": self.game_data.get('room_id')
        }

        try:
            self.main_window.socket.sendall((json.dumps(message) + '\n').encode('utf-8'))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось отправить: {str(e)}")

    def start_network_thread(self):
        if self.main_window.socket:
            self.network_thread = NetworkThread(self.main_window.socket)
            self.network_thread.data_received.connect(self.update_game_state)
            self.network_thread.connection_error.connect(self.on_connection_error)
            self.network_thread.start()

    def update_game_state(self, data):
        self.game_data = data

        status_map = {
            -1: "ожидание игроков",
            0: "игра в процессе",
            1: "просмотр результатов"
        }
        status = data.get('status', -1)
        status_text = status_map.get(status, "неизвестно")
        self.status_label.setText(f"Статус: {status_text}")

        total = data.get('total', 0)
        ready = data.get('ready', 0)
        self.players_label.setText(f"Игроки: {ready}/{total}")


        if status == -1:  # Ожидание игроков
            self.input_group.setVisible(False)
            self.next_button.setVisible(False)
            self.story_area.setText(f"Комната : {data.get('room_id', -1)} \n Ожидаем подключения всех игроков...")

        elif status == 0:  # Игра в процессе
            self.input_group.setVisible(True)
            self.next_button.setVisible(False)

            last_line = data.get('last_line', '')
            last_line_text = ""

            if isinstance(last_line, dict):
                line = last_line.get('line', '')
                last_line_text = f": {line}"
            elif isinstance(last_line, str):
                last_line_text = last_line
            else:
                last_line_text = str(last_line)

            self.last_line_label.setText(f"Последняя строка: {last_line_text}")

            self.last_line_label.setText(f"Последняя строка: {last_line_text}")

            player_status = data.get('player_status', 1)
            self.input_text.setEnabled(player_status == 0)

            has_text = bool(self.input_text.toPlainText().strip())
            self.send_button.setEnabled(player_status == 0 and has_text)

            if player_status == 1:
                self.story_area.setText("Вы уже отправили свой текст. Ждем других игроков...")
            else:
                self.story_area.setText("Продолжите историю...")

        elif status == 1:  # Просмотр результатов
            self.input_group.setVisible(False)
            self.next_button.setVisible(True)

            story = data.get('story', '')
            story_text = ""

            if isinstance(story, list):
                story_text = "\n".join([f"{s.get('name', 'Неизвестно')}: {s.get('line', '')}"
                                        for s in story if isinstance(s, dict)])

            elif isinstance(story, str):
                story_text = story
            else:
                story_text = str(story)

            self.story_area.setText(story_text)
            self.story_area.verticalScrollBar().setValue(0)  # Прокрутка в начало

    def on_connection_error(self, error_msg):
        QMessageBox.critical(self, "Ошибка соединения",
                             f"Потеряно соединение с сервером: {error_msg}")
        self.main_window.show_room_window()

    def closeEvent(self, event):
        if self.network_thread:
            self.network_thread.stop()
            self.network_thread.quit()
            self.network_thread.wait()
        super().closeEvent(event)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.player_name = ""
        self.socket = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.stack = QStackedWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.stack)
        layout.setContentsMargins(0, 0, 0, 0)
        self.central_widget.setLayout(layout)

        # Создаем окна
        self.name_window = NameInputWindow(self)
        self.room_window = RoomWindow(self)
        self.game_window = None

        self.stack.addWidget(self.name_window)
        self.stack.addWidget(self.room_window)

        self.setWindowTitle("Story Game")
        self.show_name_window()

    def show_name_window(self):
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        if self.game_window and self.game_window.network_thread:
            self.game_window.network_thread.stop()
            if self.game_window.network_thread.isRunning():
                self.game_window.network_thread.quit()
                self.game_window.network_thread.wait()

        self.stack.setCurrentWidget(self.name_window)
        self.resize(400, 250)

    def show_room_window(self):
        self.stack.setCurrentWidget(self.room_window)
        self.resize(400, 400)

    def show_game_window(self):
        if self.game_window:
            self.stack.removeWidget(self.game_window)
            self.game_window.deleteLater()

        self.game_window = GameWindow(self)
        self.stack.addWidget(self.game_window)
        self.stack.setCurrentWidget(self.game_window)
        self.resize(600, 500)

    def closeEvent(self, event):
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())