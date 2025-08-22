# Spotify Redirect URI - Альтернативные варианты

## Проблема

Spotify может отклонить `http://localhost:3000/callback` с сообщением "This redirect URI is not secure".

## Решение

Используйте один из этих альтернативных Redirect URI:

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

1. **Выберите URI** из списка выше
2. **Добавьте его** в настройках приложения Spotify
3. **Обновите .env файл** с выбранным URI
4. **Протестируйте** подключение

## Пример обновления .env

```env
# Если выбрали вариант 2
SPOTIFY_REDIRECT_URI=http://127.0.0.1:3000/callback

# Если выбрали вариант 3
SPOTIFY_REDIRECT_URI=http://localhost:8080/callback
```

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

Для локальной разработки любой из этих URI подходит. В продакшене нужно будет использовать реальный домен.
