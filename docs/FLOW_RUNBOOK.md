# FLOW RUNBOOK — E2E Operational Guide

Этот документ описывает end‑to‑end флоу выполнения переноса, операционные правила (yellow/red флаги), артефакты, запуск и критерии завершения.

Приоритет документов: `_cursorrules` → `PROJECT_RULES.md` → `docs/PRD.md` → `ARCHITECTURE.md`.

## 1. Назначение и охват

- Режимы переноса:
  - A) Яндекс Лайки → Spotify Liked Songs
  - B) Яндекс Плейлист → Spotify Плейлист (существующий или новый)
- Политика записи: append (в Итер.1). Поддерживается `--dry-run`.

## 2. Входы и выходы

- Входы:
  - Пользовательские токены: Spotify (OAuth), Яндекс.
  - Scopes (см. PRD §6.3):
    - Лайки → Liked Songs: `user-library-read user-library-modify` + playlist‑scopes.
    - Плейлисты: `playlist-read-private playlist-modify-private` (+ `playlist-modify-public` при необходимости).
  - Конфигурация: ENV (`.env`) + CLI флаги.
- Выходы:
  - Записи в Spotify (liked или указанный плейлист).
  - Отчёт: `reports/<jobId>__<snapshotHash>__<ts>.json` (см. `docs/report_schema.json`).
  - Метрики: файл/STDOUT JSON (см. `docs/metrics_schema.json`).
  - Чекпойнты: `checkpoints/<jobId>__<playlistId>__batch-<n>.json` (см. `docs/checkpoint_schema.json`).
  - Плейлист "manual transfer" с непроставленными треками (если включено).

## 3. Предусловия (DoR)

- Валидные токены и Redirect URI; scopes соответствуют сценарию.
- Acceptance CSV/набор готов; ключ идемпотентности согласован.
- Директории артефактов доступны: `reports/`, `checkpoints/`, `artifacts/`.

## 4. Пошаговый флоу (общий каркас)

1) Инициализация
   - Загрузка конфигурации и токенов; проверка scopes. При ошибке scopes/OAuth → RED (abort).
2) Снятие снапшота
   - Источник: лайки или плейлист(ы) Яндекс; формируем детерминированный список треков.
   - Расчёт `snapshotHash` из нормализованных ключей треков (см. `ARCHITECTURE.md` §6.1).
3) Идемпотентность и восстановление
   - Ключ джобы: `(userId, source, target, snapshotHash)`.
   - Проверка чекпойнтов, возобновление с последнего успешного батча.
4) Матчинг
   - Последовательность: ISRC → exact(title+artist+duration±2s) → fuzzy (см. `PRD.md` §6.1; `app/application/matching.py`).
5) Запись
   - Батчи: сначала 10, затем 100, далее по 100 (для likes используем лимит API 50, но внутренняя стратегия деградации сохраняется).
   - Уважать `retry-after`, экспоненциальный backoff с джиттером; дедлайны.
6) Чекпойнты
   - После каждого батча/плейлиста фиксировать прогресс.
7) Отчёт и метрики
   - Формируем подробный JSON‑отчёт; метрики per‑job/per‑batch.

## 5. Специфика режимов

### A) Яндекс Лайки → Spotify Liked Songs

- Scopes: `user-library-read user-library-modify` + playlist‑scopes (для унификации логики).
- Снятие снапшота: загрузить все лайки.
- Запись: API "Save Tracks for Current User" (батч ≤ 50). Внутренний контроль размера батча: 10 → 100 → 100s (ограничение провайдера учитывается при фактических запросах).
- Неперенесённые: складывать в плейлист "manual transfer" (опционально).

### B) Яндекс Плейлист → Spotify Плейлист

- Scopes: `playlist-read-private playlist-modify-private` (+ `playlist-modify-public` опц.).
- Разрешение целевого плейлиста: найти по имени среди owned; при отсутствии — создать.
- Запись: добавление треков батчами по ≤100.

## 6. Yellow / Red флаги

- Yellow (продолжаем, фиксируем в отчёте/метриках):
  - Match‑rate ниже цели (90% на acceptance). Действие: пересмотреть нормализацию/порог fuzzy; не прерывать.
  - Повторные 429. Действие: backoff по `retry-after`, временно уменьшить размер батча.
- Red (остановка и error‑report):
  - Ошибки OAuth/недостаточные scopes.
  - >3 подряд 429 с `retry-after > 60s`.
  - Сбой записи чекпойнтов >3 попыток подряд.
  - Ошибка записи >5% на последних 1000 операций.

## 7. Идемпотентность

- Ключ `(userId, source, target, snapshotHash)`.
- Детерминированные батчи и ключи треков обеспечивают отсутствие дублей при повторном запуске.
- Возобновление с середины батча безопасно (см. `app/application/pipeline.py`).

## 8. Отчёт и метрики

- Отчёт: per‑playlist и per‑track данные, причины `not_found/ambiguous`, confidence, кандидаты top‑k.
- Метрики: `match_rate`, `write_success_rate`, `retry_count`, `rl_wait_ms`, `duration_ms`.

## 9. Команды запуска (CLI)

Примеры:

```bash
# Лайки → Liked Songs, dry‑run
python musync_cli.py migrate --include-likes --dry-run --job-id likes_dry_$(date +%s)

# Плейлист → Плейлист, фактическая запись
python musync_cli.py migrate --only-playlists "My Yandex Playlist" --job-id pl_run_$(date +%s)

# С указанием путей артефактов
python musync_cli.py migrate --report-path reports/ --checkpoint-path checkpoints/ --job-id run_$(date +%s)
```

## 10. Acceptance и DoD

- Acceptance (см. `docs/PRD.md` §12):
  - Match ≥ 90% на acceptance, false ≤ 2%.
  - 0 дублей на повторном запуске с тем же `snapshotHash`.
  - TTS ≤ 5 минут на 10k треков (с учётом RL).
- DoD (см. `PROJECT_RULES.md`):
  - Тесты зелёные; пороги качества соблюдены; отчёт/метрики соответствуют схемам.

---

Источник истинности по приоритету и навигации — `_cursorrules` (Document Navigator).
