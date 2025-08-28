#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к Яндекс.Музыка API
"""

import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()


def test_yandex_connection():
    """Тестирует подключение к Яндекс.Музыка API"""

    # Получаем токен из переменных окружения
    token = os.getenv('YANDEX_MUSIC_TOKEN')

    # Проверяем наличие токена
    if not token:
        print("❌ Ошибка: YANDEX_MUSIC_TOKEN не найден в .env файле")
        print("📝 Убедитесь, что вы создали .env файл с правильным токеном")
        return False

    print("🔑 Токен Яндекс.Музыка найден:")
    print(f"   Token: {token[:20]}...")
    print()

    try:
        from yandex_music import Client
    except ImportError:
        print("❌ Ошибка: библиотека yandex-music не установлена")
        print("📦 Установите: pip install yandex-music python-dotenv")
        return False

    try:
        print("🔐 Инициализация Яндекс.Музыка API...")

        # Создаем клиент
        client = Client(token).init()

        print("✅ Яндекс.Музыка клиент создан успешно!")

        # Тестируем подключение
        print("👤 Получение информации о пользователе...")
        user = client.users_me()

        print("✅ Подключение к Яндекс.Музыка API успешно!")
        print(f"   Пользователь: {user.first_name} {user.last_name}")
        print(f"   Логин: {user.login}")
        print(f"   Email: {getattr(user, 'email', 'не указан')}")
        print(f"   Страна: {getattr(user, 'country', 'не указана')}")

        # Тестируем получение лайков
        print("\n❤️ Получение лайков...")
        likes = client.users_likes_tracks()
        print(f"✅ Найдено лайков: {len(likes)}")

        if likes:
            print("   Последние лайки:")
            for i, track in enumerate(likes[:3]):
                artists = ", ".join([artist.name for artist in track.artists])
                print(f"   - {track.title} - {artists}")

        # Тестируем получение плейлистов
        print("\n📋 Получение плейлистов...")
        playlists = client.users_playlists_list()
        print(f"✅ Найдено плейлистов: {len(playlists)}")

        if playlists:
            print("   Последние плейлисты:")
            for playlist in playlists[:3]:
                print(f"   - {playlist.title} ({playlist.track_count} треков)")

        # Тестируем получение треков из первого плейлиста (если есть)
        if playlists:
            print(
                f"\n🎵 Получение треков из плейлиста '{playlists[0].title}'...")
            try:
                playlist_tracks = client.users_playlists(
                    playlists[0].kind, user_id=user.uid).fetch_tracks()
                print(
                    f"✅ Получено треков из плейлиста: {len(playlist_tracks)}")

                if playlist_tracks:
                    print("   Первые треки:")
                    for track in playlist_tracks[:3]:
                        artists = ", ".join(
                            [artist.name for artist in track.artists])
                        print(f"   - {track.title} - {artists}")

            except Exception as e:
                print(f"⚠️ Не удалось получить треки плейлиста: {e}")

        print("\n🎉 Все тесты Яндекс.Музыка API пройдены успешно!")
        return True

    except Exception as e:
        print(f"❌ Ошибка при подключении к Яндекс.Музыка API: {e}")
        print("\n🔧 Возможные решения:")
        print("   1. Проверьте правильность токена")
        print("   2. Убедитесь, что токен не истёк")
        print("   3. Попробуйте получить новый токен через yandex-music-token")
        print("   4. Проверьте, что у вас есть активная подписка Яндекс.Музыка")
        print("   5. Убедитесь, что сервис доступен в вашем регионе")
        return False


def main():
    """Главная функция"""
    print("🎵 Тестирование Яндекс.Музыка API")
    print("=" * 40)

    success = test_yandex_connection()

    print("\n" + "=" * 40)
    if success:
        print("✅ Яндекс.Музыка API готов к работе!")
        print("🚀 Можно переходить к разработке сервиса синхронизации")
    else:
        print("❌ Яндекс.Музыка API не настроен")
        print("📖 Следуйте инструкциям в docs/SETUP_INSTRUCTIONS.md")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
