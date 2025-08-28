#!/usr/bin/env python3
"""
Обмен кода авторизации Spotify на access token
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


def exchange_code_for_token(code):
    """Обменивает код авторизации на access token"""

    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')

    if not all([client_id, client_secret, redirect_uri]):
        print("❌ Ошибка: не найдены ключи Spotify в .env")
        return None

    # URL для обмена кода на токен
    token_url = "https://accounts.spotify.com/api/token"

    # Данные для запроса
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }

    # Заголовки
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        print("🔄 Обмен кода на токен...")
        response = requests.post(token_url, data=data, headers=headers)

        if response.status_code == 200:
            token_data = response.json()

            print("✅ Токен получен успешно!")
            print(f"   Access Token: {token_data['access_token'][:20]}...")
            print(f"   Token Type: {token_data['token_type']}")
            print(f"   Expires In: {token_data['expires_in']} секунд")

            if 'refresh_token' in token_data:
                print(
                    f"   Refresh Token: {token_data['refresh_token'][:20]}...")

            return token_data
        else:
            print(f"❌ Ошибка при обмене кода: {response.status_code}")
            print(f"   Ответ: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return None


def save_token_to_env(token_data):
    """Сохраняет токен в .env файл"""

    # Читаем текущий .env
    env_content = ""
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            env_content = f.read()

    # Добавляем или обновляем токены
    lines = env_content.split('\n')
    new_lines = []

    # Флаги для проверки существования
    access_token_exists = False
    refresh_token_exists = False

    for line in lines:
        if line.startswith('SPOTIFY_ACCESS_TOKEN='):
            new_lines.append(
                f"SPOTIFY_ACCESS_TOKEN={token_data['access_token']}")
            access_token_exists = True
        elif line.startswith('SPOTIFY_REFRESH_TOKEN='):
            if 'refresh_token' in token_data:
                new_lines.append(
                    f"SPOTIFY_REFRESH_TOKEN={token_data['refresh_token']}")
            refresh_token_exists = True
        else:
            new_lines.append(line)

    # Добавляем недостающие токены
    if not access_token_exists:
        new_lines.append(f"SPOTIFY_ACCESS_TOKEN={token_data['access_token']}")

    if not refresh_token_exists and 'refresh_token' in token_data:
        new_lines.append(
            f"SPOTIFY_REFRESH_TOKEN={token_data['refresh_token']}")

    # Записываем обратно
    with open('.env', 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    print("✅ Токены сохранены в .env файл")


def main():
    """Главная функция"""
    print("🎵 Обмен кода Spotify на токен")
    print("=" * 40)

    # Проверяем наличие кода
    if not os.path.exists('.spotify_code'):
        print("❌ Файл .spotify_code не найден")
        print("💡 Сначала запустите spotify_oauth_server.py")
        return 1

    # Читаем код
    with open('.spotify_code', 'r') as f:
        code = f.read().strip()

    print(f"🔑 Код авторизации: {code[:20]}...")

    # Обмениваем код на токен
    token_data = exchange_code_for_token(code)

    if token_data:
        # Сохраняем токен
        save_token_to_env(token_data)

        # Удаляем временный файл с кодом
        os.remove('.spotify_code')

        print("\n🎉 Авторизация Spotify завершена успешно!")
        print("🚀 Теперь можно тестировать API")
        return 0
    else:
        print("\n❌ Не удалось получить токен")
        return 1


if __name__ == "__main__":
    sys.exit(main())
