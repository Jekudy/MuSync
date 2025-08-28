# 🔒 MuSync Security Guide

## Обзор безопасности

MuSync следует принципу минимальных привилегий и безопасного хранения секретов. Все токены и ключи хранятся вне репозитория кода.

## 🎯 Spotify Scopes

### Требуемые scopes

Базовый набор (плейлисты):

- `playlist-read-private` - чтение приватных плейлистов пользователя
- `playlist-modify-public` - создание и изменение публичных плейлистов
- `playlist-modify-private` - создание и изменение приватных плейлистов

### Обоснование scopes

| Scope | Зачем нужен | Альтернативы |
|-------|-------------|--------------|
| `playlist-read-private` | Чтение приватных плейлистов из источника | Нет - без этого не можем читать приватные плейлисты |
| `playlist-modify-public` | Создание публичных плейлистов в Spotify | Можно ограничить только `playlist-modify-private` |
| `playlist-modify-private` | Создание приватных плейлистов в Spotify | Можно ограничить только `playlist-modify-public` |

Дополнительные scopes для миграции лайков:

- `user-library-read` - чтение библиотеки/лайков
- `user-library-modify` - добавление в "Понравившиеся треки"

Примечание: эти права запрашиваются только если вы планируете переносить лайки в Liked Songs.

## 🔐 Хранение секретов

### Структура файлов

```
~/.musync/
├── .env                    # Переменные окружения (client secrets)
└── tokens.json            # OAuth токены (access/refresh tokens)
```

### Переменные окружения (.env)

```bash
# Spotify OAuth App credentials
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:3000/callback

# Yandex Music token (опционально, можно хранить в tokens.json)
YANDEX_TOKEN=your_yandex_token_here
```

### OAuth токены (tokens.json)

```json
{
  "spotify": {
    "access_token": "BQABC123...",
    "refresh_token": "AQABC123..."
  },
  "yandex": {
    "access_token": "y0_AgAAAAA..."
  }
}
```

## 🛡️ Безопасность файлов

### .gitignore

Следующие файлы НЕ коммитятся в репозиторий:

```
# Secrets
.env
tokens.json
*.token
*.secret

# Config directories
~/.musync/
.musync/

# Logs (могут содержать секреты)
*.log
logs/

# Temporary files
*.tmp
*.temp
```

### Права доступа

Рекомендуемые права доступа для файлов с секретами:

```bash
# Создание директории с правильными правами
mkdir -p ~/.musync
chmod 700 ~/.musync

# Файлы с секретами
chmod 600 ~/.musync/.env
chmod 600 ~/.musync/tokens.json
```

## 🔍 Валидация конфигурации

### Проверка scopes

```python
from app.crosscutting.config import get_secret_manager

manager = get_secret_manager()

# Проверить минимальные scopes
scopes = "playlist-read-private playlist-modify-public playlist-modify-private"
is_valid = manager.validate_spotify_scopes(scopes)

# Получить недостающие scopes
missing = manager.get_missing_spotify_scopes("playlist-read-private")
# Вернёт: ['playlist-modify-public', 'playlist-modify-private']
```

### Проверка конфигурации

```python
# Получить статус конфигурации
summary = manager.get_config_summary()
print(summary)

# Результат:
{
    'config_dir': '/home/user/.musync',
    'tokens_file': '/home/user/.musync/tokens.json',
    'env_file': '/home/user/.musync/.env',
    'validation': {
        'spotify_client_id': True,
        'spotify_client_secret': True,
        'spotify_redirect_uri': True,
        'yandex_token': True,
        'spotify_tokens': True
    },
    'spotify_scopes': ['playlist-read-private', 'playlist-modify-public', 'playlist-modify-private'],
    'has_spotify_tokens': True,
    'has_yandex_token': True
}
```

## 🚨 Рекомендации по безопасности

### 1. Регулярная ротация токенов

- Spotify access tokens истекают через 1 час
- Refresh tokens можно отозвать в Spotify Dashboard
- Yandex tokens можно обновить в настройках аккаунта

### 2. Мониторинг доступа

- Регулярно проверяйте активные сессии в Spotify
- Мониторьте логи приложения на подозрительную активность
- Используйте структурированное логирование (маскирование секретов)

### 3. Ограничение доступа к файлам

- Храните секреты только на доверенных машинах
- Не передавайте файлы с секретами по незащищённым каналам
- Используйте шифрование диска для дополнительной защиты

### 4. Разработка

- Никогда не коммитьте секреты в git
- Используйте .env.example для документации переменных
- Тестируйте с mock-данными, не с реальными токенами

## 🔧 Настройка Spotify OAuth App

### 1. Создание приложения

1. Перейдите в [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Создайте новое приложение
3. Запишите Client ID и Client Secret

### 2. Настройка Redirect URI

В настройках приложения добавьте:
```
http://localhost:3000/callback
```

### 3. Рекомендуемые scopes

Выбирайте набор под задачу:

- Только плейлисты:
```
playlist-read-private playlist-modify-public playlist-modify-private
```

- Плейлисты + лайки:
```
user-library-read user-library-modify playlist-read-private playlist-modify-public playlist-modify-private
```

## 🧪 Smoke-тест безопасности

Для проверки работы с минимальными scopes:

```bash
# Запустить smoke-тест
python3 -m pytest app/tests/crosscutting/test_config.py::TestSecuritySmoke::test_minimal_scopes_work
```

Тест проверяет:
- ✅ Работу с минимальными scopes
- ✅ Валидацию конфигурации
- ✅ Безопасное хранение секретов
- ✅ Отсутствие лишних прав доступа
