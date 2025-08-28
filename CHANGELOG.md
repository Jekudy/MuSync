# Changelog

Все значимые изменения в проекте MuSync будут документироваться в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Добавлено
- Базовая архитектура MVP
- Документация по настройке
- CI/CD pipeline с GitHub Actions
- Pre-commit hooks для качества кода
- Тесты для Spotify и Yandex Music API

### Изменено
- Настройка Git репозитория
- Конфигурация проекта

### Исправлено
- Настройка .gitignore для исключения токенов

## v0.1.0 - Initial CLI MVP

- Providers: Yandex (read) and Spotify (search/playlist/add batch)
- Application: Matching (ISRC→exact→fuzzy), batching, retries/backoff, checkpointing, dry-run
- Interfaces: CLI (transfer/list) and minimal HTTP (health, OAuth callback)
- Cross-cutting: structured logging, metrics, reporting
- Idempotency: snapshotHash, per-batch checkpoints
- Testing: unit, contract, integration, E2E; gating with timeouts; coverage ~92%
- Artifacts policy: reports/, checkpoints/, metrics/, logs/; tokens outside repo

Notes:
- E2E acceptance dataset and simple E2E are green; legacy E2E suite partially adapted to new pipeline API.
- Use scripts/prepare_release.py to build release artifacts and manifest.

## [0.1.0] - 2024-01-XX

### Добавлено
- Инициализация проекта MuSync
- Базовая структура для синхронизации музыки
- Документация по архитектуре
- Инструкции по настройке API ключей
- Тестовые скрипты для проверки подключения

---

## Рекомендации по версионированию

### MAJOR.MINOR.PATCH

- **MAJOR**: Несовместимые изменения API
- **MINOR**: Новая функциональность с обратной совместимостью  
- **PATCH**: Исправления ошибок с обратной совместимостью

### Типы изменений

- **Добавлено**: Новая функциональность
- **Изменено**: Изменения в существующей функциональности
- **Устарело**: Функциональность, которая будет удалена
- **Удалено**: Удаленная функциональность
- **Исправлено**: Исправления ошибок
- **Безопасность**: Исправления уязвимостей
