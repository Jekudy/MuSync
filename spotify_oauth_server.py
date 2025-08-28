#!/usr/bin/env python3
"""
Локальный сервер для обработки Spotify OAuth callback
"""

import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import webbrowser
from dotenv import load_dotenv
from urllib.parse import urlencode

# Загружаем переменные окружения
load_dotenv()


class SpotifyOAuthHandler(BaseHTTPRequestHandler):
    """Обработчик OAuth callback от Spotify"""

    def do_GET(self):
        """Обрабатывает GET запрос с кодом авторизации"""
        parsed_url = urlparse(self.path)

        if parsed_url.path == '/callback':
            # Получаем параметры из URL
            params = parse_qs(parsed_url.query)

            # Проверяем наличие кода
            if 'code' in params:
                code = params['code'][0]
                print(f"✅ Получен код авторизации: {code[:20]}...")

                # Сохраняем код во временный файл
                with open('.spotify_code', 'w') as f:
                    f.write(code)

                # Отправляем успешный ответ
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()

                html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Авторизация Spotify успешна!</title>
                    <meta charset="utf-8">
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                        .success { color: #28a745; font-size: 24px; }
                    </style>
                </head>
                <body>
                    <div class="success">
                        <h1>✅ Авторизация Spotify успешна!</h1>
                        <p>Код авторизации получен и сохранен.</p>
                        <p>Можете закрыть эту страницу и вернуться в терминал.</p>
                    </div>
                </body>
                </html>
                """

                self.wfile.write(html.encode('utf-8'))

                # Останавливаем сервер
                self.server.should_stop = True

            else:
                # Ошибка - нет кода
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()

                html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Ошибка авторизации</title>
                    <meta charset="utf-8">
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                        .error { color: #dc3545; font-size: 24px; }
                    </style>
                </head>
                <body>
                    <div class="error">
                        <h1>❌ Ошибка авторизации</h1>
                        <p>Код авторизации не получен.</p>
                        <p>Попробуйте еще раз.</p>
                    </div>
                </body>
                </html>
                """

                self.wfile.write(html.encode('utf-8'))
        else:
            # Неизвестный путь
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def log_message(self, format, *args):
        """Отключаем логирование"""
        pass


def start_oauth_server():
    """Запускает OAuth сервер"""
    server = HTTPServer(('127.0.0.1', 8080), SpotifyOAuthHandler)
    server.should_stop = False

    print("🌐 OAuth сервер запущен на http://127.0.0.1:8080")
    print("📱 Ожидание авторизации Spotify...")

    try:
        while not server.should_stop:
            server.handle_request()
    except KeyboardInterrupt:
        print("\n🛑 Сервер остановлен пользователем")

    server.shutdown()
    print("✅ OAuth сервер остановлен")


def get_spotify_auth_url():
    """Генерирует URL для авторизации Spotify"""
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')

    if not client_id or not redirect_uri:
        print("❌ Ошибка: SPOTIFY_CLIENT_ID или "
              "SPOTIFY_REDIRECT_URI не найдены")
        return None

    # Scopes for likes + playlist creation/modification
    scopes = [
        'user-read-private',
        'user-library-read',
        'user-library-modify',
        'playlist-read-private',
        'playlist-modify-private',
        'playlist-modify-public',
    ]

    params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': ' '.join(scopes),
        'show_dialog': 'true',
    }

    return 'https://accounts.spotify.com/authorize?' + urlencode(params)


def main():
    """Главная функция"""
    print("🎵 Spotify OAuth авторизация")
    print("=" * 40)

    # Генерируем URL для авторизации
    auth_url = get_spotify_auth_url()
    if not auth_url:
        return 1

    print(f"🔗 URL для авторизации: {auth_url}")
    print()

    # Запускаем сервер
    import threading
    server_thread = threading.Thread(target=start_oauth_server)
    server_thread.daemon = True
    server_thread.start()

    # Даем серверу время запуститься
    import time
    time.sleep(1)

    # Открываем браузер
    print("🌐 Открываю браузер для авторизации...")
    webbrowser.open(auth_url)

    # Ждем завершения
    server_thread.join()

    # Проверяем, получили ли мы код
    if os.path.exists('.spotify_code'):
        with open('.spotify_code', 'r') as f:
            code = f.read().strip()

        print(f"✅ Код авторизации получен: {code[:20]}...")

        # Удаляем временный файл
        os.remove('.spotify_code')

        print("🚀 Теперь можно обменять код на токен!")
        return 0
    else:
        print("❌ Код авторизации не получен")
        return 1


if __name__ == "__main__":
    sys.exit(main())
