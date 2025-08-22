#!/usr/bin/env python3
"""
Получение токена Spotify через OAuth
"""

import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Загружаем переменные окружения
load_dotenv()

def get_spotify_token():
    """Получает токен Spotify через OAuth"""
    
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')
    
    if not all([client_id, client_secret, redirect_uri]):
        print("❌ Не все ключи Spotify найдены в .env файле")
        return None
    
    print("🔐 Получение токена Spotify...")
    print("📱 Откроется браузер для авторизации")
    print("✅ После авторизации токен будет сохранен автоматически")
    print()
    
    try:
        # Создаем Spotify клиент с OAuth
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-library-read user-library-modify playlist-read-private playlist-modify-private playlist-modify-public",
            cache_path=".spotify_token_cache"  # Сохраняем токен в файл
        ))
        
        # Получаем информацию о пользователе (это запустит OAuth)
        user = sp.current_user()
        
        print(f"✅ Авторизация успешна!")
        print(f"👤 Пользователь: {user['display_name']}")
        print(f"📧 Email: {user.get('email', 'не указан')}")
        
        # Токен автоматически сохранен в .spotify_token_cache
        print("💾 Токен сохранен в .spotify_token_cache")
        
        return sp
        
    except Exception as e:
        print(f"❌ Ошибка при получении токена: {e}")
        return None

if __name__ == "__main__":
    print("🎵 Получение токена Spotify")
    print("=" * 40)
    
    sp = get_spotify_token()
    
    if sp:
        print("\n🎉 Токен получен и готов к использованию!")
        print("🚀 Можно запускать тесты: python3 test_spotify.py")
    else:
        print("\n❌ Не удалось получить токен")
