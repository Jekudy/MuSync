# 🎵 MuSync - Синхронизация музыки между Яндекс.Музыкой и Spotify

Сервис для синхронизации избранных треков и плейлистов между Яндекс.Музыкой и Spotify.

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Получение ключей API

Следуйте подробным инструкциям в [docs/SETUP_INSTRUCTIONS.md](docs/SETUP_INSTRUCTIONS.md):

- **Spotify API**: Client ID, Client Secret, Redirect URI
- **Яндекс.Музыка**: OAuth токен

**Важно**: Для Spotify используйте один из этих Redirect URI:
- `https://localhost:3000/callback`
- `http://127.0.0.1:3000/callback`
- `http://localhost:8080/callback`

### 3. Настройка окружения

```bash
# Скопируйте пример файла окружения
cp env.example .env

# Отредактируйте .env файл, добавив ваши ключи
nano .env
```

### 4. Проверка подключения

```bash
# Тест Spotify API
python test_spotify.py

# Тест Яндекс.Музыка API
python test_yandex.py
```

### 5. Запуск синхронизации

#### Использование CLI (рекомендуется)

```bash
# Синхронизация всех плейлистов из Яндекс.Музыки в Spotify
python musync_cli.py transfer --source yandex --target spotify

# Dry-run режим для предварительного просмотра (без изменений)
python musync_cli.py transfer --source yandex --target spotify --dry-run

# Синхронизация с custom job ID
python musync_cli.py transfer --source yandex --target spotify --job-id my_sync_001

# Просмотр доступных плейлистов
python musync_cli.py list --provider yandex
python musync_cli.py list --provider spotify

# Миграция лайков: Яндекс → Spotify Liked Songs
# Требуются scopes: user-library-read user-library-modify
# Dry‑run (без изменений):
python musync_cli.py likes --source yandex --target spotify --mode saved --dry-run

# Реальный запуск (добавит в "Понравившиеся треки" Spotify):
python musync_cli.py likes --source yandex --target spotify --mode saved

# Альтернатива: сохранить лайки в новый/существующий плейлист Spotify
python musync_cli.py likes --source yandex --target spotify --mode playlist --playlist-name "Liked from Yandex"
```

#### Альтернативные способы запуска

```bash
# Используйте существующие скрипты для обратной совместимости
python exchange_spotify_token.py

# Тестирование API подключений
python test_spotify.py
python test_yandex.py
```

## 📋 Возможности

- ✅ Синхронизация избранных треков (лайков) в Liked Songs Spotify или в плейлист
- ✅ Синхронизация плейлистов
- ✅ Умный матчинг треков по ISRC и метаданным
- ✅ **Dry-run режим** для безопасного тестирования
- ✅ Инкрементальная синхронизация с чекпойнтами
- ✅ Обработка ошибок и экспоненциальный backoff
- ✅ CLI интерфейс с множеством опций
- ✅ Подробные логи и JSON-отчёты
- ✅ Безопасное хранение токенов

## 🔧 Dry-run режим

Dry-run режим позволяет протестировать синхронизацию без внесения реальных изменений:

```bash
# Предварительный просмотр синхронизации
python musync_cli.py transfer --source yandex --target spotify --dry-run

# Результат покажет:
# - Сколько треков будет найдено
# - Сколько треков будет добавлено
# - Какие треки не будут найдены
# - Полную статистику без рисков
```

**Преимущества:**
- Безопасное тестирование настроек
- Предварительная оценка качества матчинга
- Проверка API подключений
- Отладка без побочных эффектов

## 🔄 Rollback режим

Rollback режим обеспечивает дополнительную безопасность при проблемах:

```bash
# Принудительный dry-run через переменную окружения
export MUSYNC_ROLLBACK=1
python musync_cli.py transfer --source yandex --target spotify

# Или используйте удобный скрипт-обёртку
python scripts/rollback.py --source yandex --target spotify
```

**Когда использовать:**
- При подозрении на проблемы с API
- После обновления конфигурации
- Для безопасного тестирования в продакшене
- При отладке сложных сценариев

**Особенности:**
- Автоматически включает dry-run режим
- Логирует предупреждение о rollback
- Не изменяет состояние в целевых сервисах
- Позволяет получить полный отчёт без рисков

## 🏗️ Архитектура

Проект следует архитектуре из [ARCHITECTURE_MVP.md](ARCHITECTURE_MVP.md):

```
app/
├── domain/           # Бизнес-сущности
├── application/      # Use cases
├── infrastructure/   # API клиенты
├── interfaces/       # CLI/Web интерфейсы
└── crosscutting/     # Логирование, конфиг
```

## 🔧 Разработка

### Установка для разработки

```bash
# Клонирование репозитория
git clone <repository-url>
cd MuSync

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt

# Установка pre-commit hooks
pre-commit install
```

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=app

# Специфичные тесты
pytest tests/test_sync.py
```

### Линтинг и форматирование

```bash
# Форматирование кода
black app/ tests/

# Проверка стиля
flake8 app/ tests/

# Проверка типов
mypy app/
```

## 📖 Документация

- [Инструкции по настройке](docs/SETUP_INSTRUCTIONS.md)
- [Архитектура MVP](ARCHITECTURE_MVP.md)
- [Руководство по разработке](CURSOR_DEVELOPMENT_GUIDE.md)
- [Методология shared code](SHARED_CODE_MIXIN_METHODOLOGY.md)

## 🔒 Безопасность

- Токены хранятся в переменных окружения
- Файл `.env` добавлен в `.gitignore`
- Используются минимально необходимые scopes API
- Все запросы логируются для отладки

## 🐛 Устранение неполадок

### Частые проблемы

1. **"Spotify API не работает"**
   - Проверьте правильность Client ID и Client Secret
   - Убедитесь, что Redirect URI настроен правильно
   - Если лайки не добавляются, убедитесь, что вы авторизовались с расширенными правами: `user-library-read user-library-modify`

4. **"Скрипт висит и не завершается"**
   - Политика: короткие команды запускаем через таймаут-обёртку; долгие сервисы запускаем как есть.
   - Пример (короткая задача с таймаутом 90с):
     ```bash
     python3 -m scripts.run_with_timeout --timeout 90 -- python3 spotify_oauth_server.py
     ```

2. **"Яндекс.Музыка API не работает"**
   - Проверьте, что токен не истёк
   - Получите новый токен через `yandex-music-token`

3. **"Треки не находятся"**
   - Некоторые треки могут отсутствовать в Spotify
   - Проверьте отчёт о не найденных треках
   - Для лайков используйте `--dry-run`, чтобы увидеть, сколько треков будет найдено/пропущено

### Логи

Логи сохраняются в `logs/` директории:
- `sync.log` - основные операции синхронизации
- `errors.log` - ошибки и исключения

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

MIT License - см. файл [LICENSE](LICENSE)

## ⚠️ Отказ от ответственности

Этот проект использует неофициальный API Яндекс.Музыки. Используйте на свой страх и риск. Соблюдайте условия использования сервисов.

## 🆘 Поддержка

Если у вас возникли проблемы:

1. Проверьте раздел "Устранение неполадок"
2. Создайте issue в репозитории
3. Опишите проблему и приложите логи

---

**Удачной синхронизации! 🎵**
