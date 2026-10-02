import json
import uuid
import socket
import threading
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')


class HistoryRecord:
    def __init__(self, player_name, line):
        self.name = player_name
        self.line = line


class History:
    def __init__(self, index):
        self.history_list = []
        self.index = index

    def write(self, player, line):
        self.history_list.append(HistoryRecord(player.name, line))

class Player:
    def __init__(self, name, conn, addr):
        self.name = name
        self.conn = conn
        self.status = 1
        self.addr = addr
        self.id = uuid.uuid4().__str__()
        self.story = -1

class Room:
    def __init__(self, size):
        self.size = size
        self.round = -1
        self.status = -1 # -1 - ожидаем 0 - играем 1 - смотрим
        self.id = uuid.uuid4().__str__()
        self.players = {}
        self.histories = []
        self.crn_story = -1
        self.timer = None
        self.lock = threading.RLock()


    def loop(self, server):
        logging.info("Loop called")
        self.lock.acquire()
        logging.info(f"game {self.round} / {self.size}")
        try:
            if self.round > self.size:
                logging.info(f"game ended {self.round} {self.size}")
                self.status = 1
                self.crn_story = 1
            else:
                for player in self.players.values():
                    player.status = 0
                    story = self.get_story(player)
                    if len(story.history_list) != self.round:
                        logging.info("auto rewrite")
                        story.write(player, '...')
                    player.story = player.story + 1 if player.story + 1 <= self.size else 1
                self.round += 1


            # Отменяем текущий таймер перед запуском нового
            if self.timer is not None:
                self.timer.cancel()

            # Запускаем новый таймер только если игра не закончилась
            if self.round <= self.size:
                self.timer = threading.Timer(20, self.loop, args=(server,))
                self.timer.start()
            else:
                self.status = 1
                self.crn_story = 1
            server.broadcast_room(self.id)
        finally:
            self.lock.release()

    def write_line(self, line, addr, server):
        self.lock.acquire()
        try:
            ready = 0
            for player in self.players.values():
                if player.addr == addr:
                    player.status = 1
                    self.get_story(player).write(player, line)
                ready += player.status
        finally:
            self.lock.release()

        if ready == self.size:
            if self.timer is not None:
                self.timer.cancel()
            self.loop(server)

    def add_player(self, player):
        self.lock.acquire()
        self.players[player.id] = player
        self.lock.release()

    def get_crn_story(self):
        for story in self.histories:
            if story.index == self.crn_story:
                return story.history_list
        return [HistoryRecord("Система", "Игра окончена, можете закрывать окно")]

    def get_story(self, player):
        for story in self.histories:
            if story.index == player.story:
                return story
        return None


class Server:
    def __init__(self):
        self.HOST = '127.0.0.1'
        self.PORT = 12346
        self.rooms = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start_room(self, room_id):
        room = self.rooms[room_id]
        if room.status == -1:
            room.status = 0
            room.round = 1
            story_num = 1
            for player in room.players.values():
                room.histories.append(History(story_num))
                player.story = story_num
                story_num += 1
                player.status = 0

            if room.timer is not None:
                room.timer.cancel()

            room.timer = threading.Timer(20, room.loop, args=(self,))
            room.timer.start()
            self.broadcast_room(room_id)

    def broadcast_room(self, room_id):
        try:
            room =  self.rooms[room_id]
            ready = 0
            for player in room.players.values():
                ready += player.status

            for player in room.players.values():
                msg = {"total": room.size, "ready": ready, "status": room.status, "room_id": room.id, "player_status": player.status}
                if room.status == 0:
                    story = room.get_story(player)
                    if story and story.history_list:
                        msg["last_line"] = {"name": story.history_list[-1].name, "line": story.history_list[-1].line}
                elif room.status == 1:
                    story_text = room.get_crn_story()
                    if isinstance(story_text, list):
                        msg["story"] = [{"name": rec.name, "line": rec.line} for rec in story_text]

                # ВАЖНО: убираем indent=4, отправляем компактный JSON
                msg_json = json.dumps(msg) + '\n'
                logging.info(msg_json)
                player.conn.sendall(msg_json.encode('utf-8'))

        except ConnectionResetError as e:
            logging.error("Ошибка отправки", e)
        except Exception as e:
            logging.error("Ошибка в broadcast_room:", e)

    def handle_client(self, conn, addr):
        # create  4 player_name / join player_name id / write id message / next line
        try:
            while True:
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    break
                room = None
                client_request = json.loads(data)
                logging.info("Запрос ", client_request)
                action = client_request.get("action", "")
                if action == 'create':
                    player_name = client_request.get("player_name", "")
                    size = client_request.get("size", "")
                    room = Room(size)
                    player = Player(player_name, conn, addr)
                    room.add_player(player)
                    self.rooms[room.id] = room
                    # Отправляем ответ сразу
                    response = {"room_id": room.id, "status": "created"}
                    conn.sendall((json.dumps(response) + '\n').encode('utf-8'))
                if action == 'join':
                    player_name = client_request.get("player_name", "")
                    room_id = client_request.get("room_id", "")
                    room = self.rooms[room_id]
                    if len(room.players) < room.size:
                        player = Player(player_name, conn, addr)
                        room.add_player(player)
                    if len(room.players) == room.size:
                        threading.Timer(2, function=self.start_room, args=(room_id,)).start()
                if action == 'write':
                    room_id = client_request.get("room_id", "")
                    line = client_request.get("line", "")
                    room = self.rooms[room_id]
                    room.write_line(line, addr, self)
                if action == 'next_story':
                    room_id = client_request.get("room_id", "")
                    room = self.rooms[room_id]
                    room.crn_story += 1
                if room:
                    self.broadcast_room(room.id)

        except Exception as e:
            print("Ошибка в handle_client:", e)
            conn.close()

    def start(self):
        with self.socket:
            self.socket.bind((self.HOST, self.PORT))
            self.socket.listen()
            print(f"[СЕРВЕР ЗАПУЩЕН] {self.HOST}:{self.PORT}")
            while True:
                conn, addr = self.socket.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()

if __name__ == "__main__":
    game_server = Server()
    game_server.start()