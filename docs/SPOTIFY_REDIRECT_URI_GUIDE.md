# Spotify Redirect URI и OAuth Scopes — Практическое руководство

## Проблема

Spotify может отклонить `http://localhost:3000/callback` с сообщением "This redirect URI is not secure" или при несовпадении значения с настройками в Spotify Dashboard.

## Решение

1) Выберите Redirect URI из списка ниже и добавьте его в Spotify Dashboard.
2) Убедитесь, что переменная окружения `SPOTIFY_REDIRECT_URI` совпадает в точности.
3) Проверьте минимально необходимые scopes.

### Вариант 1: HTTPS localhost
```
https://localhost:3000/callback
```

### Вариант 2: IP адрес localhost
```
http://127.0.0.1:3000/callback
```

### Вариант 3: Другой порт
```
http://localhost:8080/callback
http://localhost:5000/callback
http://localhost:4000/callback
```

### Вариант 4: IP адрес с другим портом
```
http://127.0.0.1:8080/callback
http://127.0.0.1:5000/callback
```

## Пошаговая инструкция

1. Выберите URI из списка выше.
2. Добавьте его в настройках приложения Spotify (Dashboard → App → Redirect URIs → Add → Save).
3. Обновите `.env` значением `SPOTIFY_REDIRECT_URI` (точное совпадение).
4. Проверьте и сохраните минимальные scopes (см. ниже).
5. Протестируйте подключение.

## Пример обновления .env

```env
# Если выбрали вариант 2
SPOTIFY_REDIRECT_URI=http://127.0.0.1:3000/callback

# Если выбрали вариант 3
SPOTIFY_REDIRECT_URI=http://localhost:8080/callback
```

## Минимальные OAuth scopes для МуSync (Итер.1)

Для чтения собственных плейлистов источника и создания/модификации целевого плейлиста в Spotify:

- `playlist-read-private` — чтение приватных плейлистов пользователя (если потребуется просмотр target‑плейлистов).
- `playlist-modify-private` — создание/редактирование приватных плейлистов.
- (опционально) `playlist-modify-public` — если целевой плейлист будет публичным.

Список scopes в Dashboard должен соответствовать тому, что запрашивает ваше приложение.

## Тестирование

После изменения URI запустите:
```bash
python test_spotify.py
```

## Если ничего не работает

1. **Попробуйте все варианты** из списка выше
2. **Убедитесь**, что URI точно совпадает в Spotify Dashboard и .env файле
3. **Проверьте**, что приложение активно в Spotify Developer Dashboard
4. **Создайте новое приложение** с другим названием

## Примечание

Для локальной разработки любой из этих URI подходит. В продакшене используйте реальный домен с HTTPS и зафиксируйте Redirect URI в настройках приложения.
