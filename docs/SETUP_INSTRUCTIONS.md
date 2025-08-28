# Пошаговые инструкции по получению ключей и токенов

## Обзор

Для работы сервиса синхронизации музыки между Яндекс.Музыкой и Spotify необходимо получить следующие ключи:

1. **Spotify API** (официальный):
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET` 
   - `SPOTIFY_REDIRECT_URI`

2. **Яндекс.Музыка** (неофициальный API):
   - `YANDEX_MUSIC_TOKEN`

---

## 1. Получение Spotify API ключей

### Шаг 1: Регистрация в Spotify Developer Dashboard

1. Перейдите на [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications)
2. Войдите в свой аккаунт Spotify (или создайте новый)
3. Нажмите **"Create an App"**

### Шаг 2: Создание приложения

1. Заполните форму создания приложения:
   - **App name**: `MuSync` (или любое другое название)
   - **App description**: `Music synchronization service between Yandex.Music and Spotify`
   - **Website**: `https://github.com/your-username/musync` (или любой URL)
   - **Redirect URI**: `https://localhost:3000/callback` (важно!)
   - **API/SDKs**: оставьте пустым
   - **What are you building?**: выберите "Web app"

2. Нажмите **"Save"**

### Шаг 3: Получение ключей

После создания приложения вы увидите:

- **Client ID** - скопируйте его в `SPOTIFY_CLIENT_ID`
- **Client Secret** - нажмите "Show Client Secret" и скопируйте в `SPOTIFY_CLIENT_SECRET`

### Шаг 4: Настройка Redirect URI

1. В настройках приложения найдите раздел **"Redirect URIs"**
2. Добавьте: `https://localhost:3000/callback`
3. Нажмите **"Add"** и **"Save"**

**Примечание**: Если `https://localhost:3000/callback` тоже не принимается, используйте один из этих вариантов:
- `http://127.0.0.1:3000/callback`
- `http://localhost:8080/callback`
- `http://localhost:5000/callback`

### Шаг 5: Проверка настроек

Убедитесь, что у вас есть:
- ✅ Client ID
- ✅ Client Secret  
- ✅ Redirect URI: `https://localhost:3000/callback` (или другой принятый URI)

---

## 2. OAuth авторизация Spotify с корректными scopes

Для миграции лайков необходимы права на библиотеку пользователя: `user-library-read user-library-modify`.

Вариант A. Локальный OAuth helper (рекомендуется):

```bash
python3 spotify_oauth_server.py
# Откроется URL авторизации с нужными scopes:
# user-library-read user-library-modify playlist-read-private playlist-modify-private playlist-modify-public
```

Вариант B. HTTP интерфейс (если поднимаете web-сервис):

```bash
# Получить auth_url через HTTP endpoint сервиса (в ответе будут нужные scopes)
curl http://localhost:3000/auth/spotify
```

После авторизации убедитесь, что сохранённые токены содержат перечисленные scopes. При изменении scopes требуется переавторизация.

---

## 3. Получение токена Яндекс.Музыки

### Метод 1: Через OAuth авторизацию (рекомендуемый)

1. Откройте ссылку: [https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d](https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d)
2. Войдите в аккаунт Яндекса
3. Нажмите "Разрешить"
4. В адресной строке найдите фрагмент: `access_token=y0_AgAAAAA...&token_type=bearer&expires_in=...`
5. Скопируйте значение после `access_token=` до символа `&`

**Важно**: Если страница мгновенно редиректит:
- Откройте ссылку в режиме инкогнито
- Или нажмите Esc сразу после "Разрешить"
- Или попробуйте другой браузер

### Метод 2: Через браузерное расширение

1. Установите расширение "Yandex Music Token" из магазина браузера
2. Откройте music.yandex.ru и войдите в аккаунт
3. Кликните по иконке расширения - оно покажет токен

### Метод 3: Через браузер (ручной способ)

#### Шаг 1: Открытие Яндекс.Музыки

1. Откройте [music.yandex.ru](https://music.yandex.ru)
2. Войдите в свой аккаунт

#### Шаг 2: Получение токена из cookies

1. Откройте **Developer Tools** (F12)
2. Перейдите на вкладку **Application** (Chrome) или **Storage** (Firefox)
3. В левой панели найдите **Cookies** → **https://music.yandex.ru**
4. Найдите cookie с именем `OAuth` или `access_token`
5. Скопируйте значение в `YANDEX_MUSIC_TOKEN`

### Метод 3: Через мобильное приложение (для продвинутых)

1. Установите приложение Яндекс.Музыка на телефон
2. Войдите в аккаунт
3. Используйте инструменты для перехвата трафика (Charles Proxy, Fiddler)
4. Найдите запросы к API и извлеките токен из заголовков

---

## 4. Управление токенами пользователей

Проект включает систему управления токенами для поддержки нескольких пользователей:

### Автоматическое сохранение токенов

Токены автоматически сохраняются в:
- `.env` - основной файл с переменными окружения
- `user_tokens.json` - файл с токенами пользователей

### Программное управление токенами

```python
from tokens_config import tokens_manager

# Добавить токен пользователя
tokens_manager.add_user_token(
    username="user_name",
    service="yandex",  # или "spotify"
    token="your_token_here",
    description="Описание токена"
)

# Получить токен пользователя
token = tokens_manager.get_user_token("user_name", "yandex")

# Экспорт в .env формат
env_content = tokens_manager.export_to_env_format("user_name")
```

### Структура токенов

- `YANDEX_MUSIC_TOKEN` - основной токен для текущего пользователя
- `USER_<USERNAME>_<SERVICE>_TOKEN` - токены для конкретных пользователей

## 5. Проверка полученных ключей

### Тест Spotify API

Создайте файл `test_spotify.py`:

```python
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Замените на ваши значения
CLIENT_ID = "ваш_client_id"
CLIENT_SECRET = "ваш_client_secret"
REDIRECT_URI = "https://localhost:3000/callback"  # или другой принятый URI

try:
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="user-library-read user-library-modify playlist-read-private playlist-modify-private playlist-modify-public"
    ))
    
    # Тест подключения
    user = sp.current_user()
    print(f"✅ Spotify API работает! Пользователь: {user['display_name']}")
    
except Exception as e:
    print(f"❌ Ошибка Spotify API: {e}")
```

### Тест Яндекс.Музыка API

Создайте файл `test_yandex.py`:

```python
from yandex_music import Client

# Замените на ваш токен
TOKEN = "ваш_yandex_token"

try:
    client = Client(TOKEN).init()
    
    # Тест подключения
    user = client.users_me()
    print(f"✅ Яндекс.Музыка API работает! Пользователь: {user.first_name} {user.last_name}")
    
    # Тест получения лайков
    likes = client.users_likes_tracks()
    print(f"✅ Лайков получено: {len(likes)}")
    
except Exception as e:
    print(f"❌ Ошибка Яндекс.Музыка API: {e}")
```

---

## 6. Создание файла .env

Создайте файл `.env` в корне проекта:

```env
# Spotify API
SPOTIFY_CLIENT_ID=ваш_spotify_client_id
SPOTIFY_CLIENT_SECRET=ваш_spotify_client_secret
SPOTIFY_REDIRECT_URI=https://localhost:3000/callback

# Yandex.Music API
YANDEX_MUSIC_TOKEN=ваш_yandex_music_token

# Дополнительные настройки
LOG_LEVEL=INFO
SYNC_BATCH_SIZE=50
```

---

## 7. Безопасность и рекомендации

### ✅ Что делать:

1. **Храните ключи в .env файле** (не в коде!)
2. **Добавьте .env в .gitignore**
3. **Используйте разные ключи для разработки и продакшена**
4. **Регулярно обновляйте токены** (особенно Яндекс.Музыка)

### ❌ Что НЕ делать:

1. **Не коммитьте ключи в Git**
2. **Не передавайте токены третьим лицам**
3. **Не используйте один токен для нескольких приложений**
4. **Не храните токены в открытом виде**

### 🔄 Обновление токенов

- **Spotify**: токены обновляются автоматически
- **Яндекс.Музыка**: токен может истечь, тогда получите новый через `yandex-music-token`

---

## 8. Устранение неполадок

### Spotify API не работает:

1. Проверьте правильность Client ID и Client Secret
2. Убедитесь, что Redirect URI точно совпадает (попробуйте разные варианты)
3. Проверьте, что приложение создано и активно
4. Убедитесь, что у вас есть аккаунт Spotify Premium (для некоторых функций)
5. Если Redirect URI не принимается, попробуйте: `http://127.0.0.1:3000/callback` или `http://localhost:8080/callback`

### Яндекс.Музыка API не работает:

1. Проверьте правильность токена
2. Убедитесь, что токен не истёк
3. Попробуйте получить новый токен
4. Проверьте, что у вас есть активная подписка Яндекс.Музыка

### Общие проблемы:

1. **Сеть**: проверьте интернет-соединение
2. **Блокировки**: убедитесь, что сервисы доступны в вашем регионе
3. **Лимиты**: не превышайте лимиты API

---

## 9. Следующие шаги

После получения всех ключей:

1. ✅ Проверьте работу API через тестовые скрипты
2. ✅ Создайте файл .env с ключами
3. ✅ Убедитесь, что .env добавлен в .gitignore
4. 🚀 Готовы к разработке сервиса синхронизации!

---

## Поддержка

Если возникли проблемы:

1. Проверьте раздел "Устранение неполадок"
2. Обратитесь к официальной документации:
   - [Spotify Web API](https://developer.spotify.com/documentation/web-api/)
   - [yandex-music library](https://github.com/MarshalX/yandex-music-api)
3. Создайте issue в репозитории проекта
