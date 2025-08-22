#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к Spotify API
"""

import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

def test_spotify_connection():
    """Тестирует подключение к Spotify API"""
    
    # Получаем ключи из переменных окружения
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')
    
    # Проверяем наличие ключей
    if not client_id or not client_secret:
        print("❌ Ошибка: SPOTIFY_CLIENT_ID или SPOTIFY_CLIENT_SECRET не найдены в .env файле")
        print("📝 Убедитесь, что вы создали .env файл с правильными ключами")
        return False
    
    if not redirect_uri:
        print("❌ Ошибка: SPOTIFY_REDIRECT_URI не найден в .env файле")
        print("💡 Попробуйте один из этих URI:")
        print("   - https://localhost:3000/callback")
        print("   - http://127.0.0.1:3000/callback")
        print("   - http://localhost:8080/callback")
        return False
    
    print("🔑 Ключи Spotify найдены:")
    print(f"   Client ID: {client_id[:10]}...")
    print(f"   Redirect URI: {redirect_uri}")
    print()
    
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
    except ImportError:
        print("❌ Ошибка: библиотека spotipy не установлена")
        print("📦 Установите: pip install spotipy python-dotenv")
        return False
    
    try:
        print("🔐 Инициализация Spotify API...")
        
        # Создаем Spotify клиент с необходимыми scopes
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-library-read user-library-modify playlist-read-private playlist-modify-private playlist-modify-public"
        ))
        
        print("✅ Spotify клиент создан успешно!")
        
        # Тестируем подключение
        print("👤 Получение информации о пользователе...")
        user = sp.current_user()
        
        print(f"✅ Подключение к Spotify API успешно!")
        print(f"   Пользователь: {user['display_name']}")
        print(f"   Email: {user.get('email', 'не указан')}")
        print(f"   Страна: {user.get('country', 'не указана')}")
        print(f"   Тип аккаунта: {user.get('product', 'не указан')}")
        
        # Тестируем получение плейлистов
        print("\n📋 Получение плейлистов...")
        playlists = sp.current_user_playlists(limit=5)
        print(f"✅ Найдено плейлистов: {playlists['total']}")
        
        if playlists['items']:
            print("   Последние плейлисты:")
            for playlist in playlists['items'][:3]:
                print(f"   - {playlist['name']} ({playlist['tracks']['total']} треков)")
        
        # Тестируем получение лайков
        print("\n❤️ Получение лайков...")
        liked_tracks = sp.current_user_saved_tracks(limit=5)
        print(f"✅ Найдено лайков: {liked_tracks['total']}")
        
        if liked_tracks['items']:
            print("   Последние лайки:")
            for item in liked_tracks['items'][:3]:
                track = item['track']
                artists = ", ".join([artist['name'] for artist in track['artists']])
                print(f"   - {track['name']} - {artists}")
        
        print("\n🎉 Все тесты Spotify API пройдены успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при подключении к Spotify API: {e}")
        print("\n🔧 Возможные решения:")
        print("   1. Проверьте правильность Client ID и Client Secret")
        print("   2. Убедитесь, что Redirect URI настроен правильно")
        print("   3. Проверьте, что приложение активно в Spotify Developer Dashboard")
        print("   4. Убедитесь, что у вас есть аккаунт Spotify")
        return False

def main():
    """Главная функция"""
    print("🎵 Тестирование Spotify API")
    print("=" * 40)
    
    success = test_spotify_connection()
    
    print("\n" + "=" * 40)
    if success:
        print("✅ Spotify API готов к работе!")
        print("🚀 Можно переходить к разработке сервиса синхронизации")
    else:
        print("❌ Spotify API не настроен")
        print("📖 Следуйте инструкциям в docs/SETUP_INSTRUCTIONS.md")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
