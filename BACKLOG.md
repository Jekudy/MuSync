# BACKLOG — Итерация 1 (MVP CLI: Яндекс → Spotify)

## Эпик: надёжный перенос собственных и подписных плейлистов Яндекс → Spotify

Ниже — подробные этапы с DoR/DoD, зависимостями и ожидаемыми артефактами. Основано на `PRD.md` (v3) и `README.md`.

### Политика артефактов и токенов (MVP)

- Артефакты (отчёты, чекпойнты, метрики, логи, acceptance CSV):
  - Базовая директория по умолчанию: `~/.local/share/musync` (Linux), `~/Library/Application Support/MuSync` (macOS), `%APPDATA%/MuSync` (Windows). Переопределяется `MUSYNC_DATA_DIR`.
  - Структура: `reports/`, `checkpoints/`, `metrics/`, `logs/`, `acceptance/`.
  - Именование файлов: `<jobId>__<snapshotHash>__<yyyyMMdd-HHmmss>.json` (для отчётов/метрик), `<jobId>__<playlistId>__batch-<n>.json` (чекпойнты).
  - Retention: 7 дней для чекпойнтов, 30 дней для отчётов/метрик/логов. Авто‑очистка при запуске.
- Токены и секреты:
  - Отдельный файл вне репозитория: по умолчанию `~/.config/musync/tokens.json` (переопределяется `MUSYNC_TOKENS_FILE`).
  - Формат JSON:
    - `spotify`: `{ access_token, refresh_token, expires_at }`
    - `yandex`: `{ oauth_token }`
  - Файл создаётся инструментами OAuth и не коммитится; права доступа 600.
- Таймауты по умолчанию: 90с для коротких CLI‑команд/тестов; долгоживущие сервисы без таймаута.

### 1. Порты и домен

- Задача 1.1: Определить и зафиксировать контракт `MusicProvider` (read/search/add, playlists)
  - DoR:
    - Описаны бизнес‑сущности (`Playlist`, `Track`, `UserOwnedFlag`) и операции: чтение собственных плейлистов, поиск треков, создание/разрешение плейлиста, батчевое добавление треков.
    - Решена стратегия нормализации тайтла/артистов/длительности для матчинга (описана в `ARCHITECTURE_MVP.md`).
    - Подготовлены контрактные тесты (заглушки провайдера и общий тест‑сьют).
  - DoD:
    - Интерфейс порта размещён в домене; нет провайдер‑специфичных типов в domain.
    - Контрактные тесты для «псевдо‑провайдера» зелёные.
    - Документация порта отражена в `ARCHITECTURE_MVP.md` (кратко) и ссылка из `README.md`.
  - Место в архитектуре: `app/domain` (порт и сущности), `app/application` (use‑cases, оркестрация).
  - Вход/выход (контракты):
    - Сущности:
      - `Track { sourceId: str, title: str, artists: list[str], durationMs: int, isrc?: str, album?: str }`
      - `Playlist { id: str, name: str, ownerId: str, isOwned: bool }`
    - Порт `MusicProvider` (сокр.): `list_owned_playlists() -> Iterable[Playlist]`, `list_tracks(playlistId) -> Iterable[Track]`,
      `find_track_candidates(track: Track, topK=3) -> list[Candidate{uri, confidence, reason}]`,
      `resolve_or_create_playlist(name) -> Playlist`, `add_tracks_batch(playlistId, trackUris: list[str]) -> AddResult{added, duplicates, errors}`.
    - Ошибки: `RateLimited{retryAfterMs}`, `TemporaryFailure`, `PermanentFailure`, `NotFound`.
  - Тесты:
    - Unit (domain): нормализация строк, толеранс длительности, построение ключа трека (см. 1.2), маппинг ошибок.
    - Contract: стабильность сигнатур/полей, пагинация как Iterable, корректная семантика пустых ответов.

- Задача 1.2: Спроектировать идемпотентность (ключ `(userId, source, target, snapshotHash)`, checkpoint)
  - DoR:
    - ADR‑0001 «Идемпотентность» согласован (`docs/adr/0001-idempotency.md`).
    - Выбран носитель состояния для MVP (локальный файл/директория с JSON чекпойнтами и отчётами).
    - Описан формат `snapshotHash` и границы окна повторного запуска.
  - DoD:
    - Повторный запуск с тем же `snapshotHash` не создаёт дублей (0 дублей по отчёту и факту в Spotify).
    - Чекпойнты позволяют возобновить с середины батча; юнит‑тесты зелёные.
    - Включён ключ идемпотентности в структурированные логи и имя файла отчёта.
  - Место в архитектуре: `app/application` (политики), `app/crosscutting` (хранилище чекпойнтов/отчётов).
  - Вход/выход (контракты):
    - `snapshotHash = sha256(sorted([trackKey(...) for all tracks in snapshot]))`.
    - `trackKey = isrc || normalize(title)+"::"+normalize(artists_joined)+"::"+round(durationMs, 2000ms)`.
    - Чекпойнт: `{ jobId, playlistId, batchIndex, addedUris: list[str], updatedAt }`.
  - Тесты:
    - Unit: стабильность `snapshotHash` при перестановке треков; толеранс длительности ±2с; нормализация строк (скобки/feat./пунктуация/регистр).
    - Unit: корректное возобновление из чекпойнта при частичной записи.
    - E2E: второй запуск с тем же `snapshotHash` → 0 дублей; корректные метрики `write_success_rate`.

- Задача 1.3: Определить формат JSON‑отчёта и схему метрик
  - DoR:
    - Согласована структура отчёта: по плейлистам и трекам, причины `not_found`, `confidence`, агрегированный summary.
    - Согласованы метрики: `match_rate`, `write_success_rate`, `retry_count`, `rl_wait_ms`, `duration_ms`.
  - DoD:
    - Генерируется один JSON‑отчёт на jobId и snapshot с полным содержимым.
    - Метрики выводятся структурированно (stdout/файл) и доступны для чтения e2e‑тестами.
  - Место в архитектуре: `app/crosscutting` (репортинг/метрики).
  - Вход/выход (контракты):
    - Header: `{ jobId, startedAt, finishedAt, source, target, snapshotHash, dryRun }`.
    - Per‑playlist: `{ playlistId, name, totals {tracks, matched, added, duplicates, errors} }`.
    - Per‑track: `{ sourceTrackId, status: matched|added|skipped_duplicate|not_found|ambiguous|error|rl_deferred|skipped_dry_run, confidence: [0..1], reason?, candidates?: top3[{uri, confidence}] }`.
    - Метрики: пер‑job и пер‑батч; формат JSON‑lines или JSON‑файл.
  - Тесты:
    - Unit: сериализация/валидация схемы; наличие обяз. полей; агрегаты сходятся с деталями.
    - E2E: отчёт генерируется в `reports/` с корректным именованием; метрики читаемы тестами.

### 2. Адаптеры провайдеров

- Задача 2.1: Яндекс.Музыка — чтение собственных плейлистов и треков, учёт ограничений API ✅
  - DoR:
    - Есть действующий OAuth‑токен Яндекс.Музыки (переменная окружения в `.env`).
    - Подготовлены тест‑аккаунты и контрольный плейлист для acceptance.
    - Зафиксированы лимиты/ограничения API и стратегия пагинации/ретраев.
  - DoD:
    - Адаптер реализует порт `MusicProvider` для операций чтения; возвращает все плейлисты пользователя (собственные и подписные), помечая `isOwned` при наличии сигнала.
    - Контрактные тесты зелёные; обработаны пагинация, временные ошибки, backoff.
    - Секреты не логируются; чувствительные поля маскируются.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/infrastructure/providers/yandex.py`
  - **Тесты:** `app/tests/infrastructure/providers/test_yandex_provider.py`
  - **Результат:** 12/12 тестов зелёные
  - Место в архитектуре: `app/infrastructure/providers/yandex`.
  - Вход/выход (контракты):
    - Вход: `oauth_token` из `tokens.json`.
    - Выход: `Playlist` и `Track` как доменные сущности.
    - Определение владения: если доступен `ownerId` — устанавливаем `isOwned = (ownerId == currentUserId)`; переносим все плейлисты.
  - Тесты:
    - Contract: пагинация (многостраничные плейлисты), пустые результаты, неполные метаданные, 5xx/429 → ретраи.
    - Unit: маппинг из DTO SDK в доменные `Track/Playlist`.
    - NFR: базовый backoff под 429.

- Задача 2.2: Spotify — поиск/создание/разрешение плейлиста; добавление треков батчами (≤100) ✅
  - DoR:
    - Настроены `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` в `.env` (смотри `README.md` и `docs/SPOTIFY_REDIRECT_URI_GUIDE.md`).
    - Получение пользовательского токена отлажено (скрипты `spotify_oauth_server.py`, `get_spotify_token.py`, `exchange_spotify_token.py`).
    - Scopes: `playlist-read-private`, `playlist-modify-private` (+`playlist-modify-public` — опционально).
  - DoD:
    - Адаптер реализует поиск треков и плейлистов, создание/разрешение плейлиста, добавление треков батчами с уважением 429 и `retry-after`.
    - Контрактные тесты зелёные; нет дублей при повторном запуске (в связке с идемпотентностью).
    - Логи структурированы, без секретов; соответствуют требованиям PRD.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/infrastructure/providers/spotify.py`
  - **Тесты:** `app/tests/infrastructure/providers/test_spotify_provider.py`
  - **Результат:** 18/18 тестов зелёные
  - Место в архитектуре: `app/infrastructure/providers/spotify`.
  - Вход/выход (контракты):
    - Вход: OAuth токены Spotify из `tokens.json`; параметры поиска `market=from_token`, `include_external=audio`.
    - Разрешение плейлиста: по имени; дефолт приватности — `private`; имя целевого — `<name>` (без суффикса).
    - Добавление: батчами по ≤100 URI; результат — `{added, duplicates, errors}`.
  - Тесты:
    - Contract: уважение `retry-after` при 429 (ждём и повторяем), семантика частичной записи, отсутствие дублей при повторе батча.
    - Unit: построение поисковых запросов (ISRC→exact→fuzzy), нормализация и оценка confidence.
    - Integration (с моками API): создание/разрешение плейлиста, добавление батчей, обработка 5xx.

### 3. Пайплайн переноса

- Задача 3.1: Матчинг (ISRC → exact(title+artist+duration±2s) → fuzzy) ✅
  - DoR:
    - Определены пороги для exact/fuzzy и стратегия нормализации (регистры, скобки, feat., спецсимволы).
    - Подготовлен acceptance датасет для оценки качества.
  - DoD:
    - Достигается `match_rate ≥ 90%` на acceptance, `false match ≤ 2%` (из отчёта).
    - В отчёте присутствуют причины `not_found` и `confidence` для explainability.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/application/matching.py`
  - **Тесты:** `app/tests/application/test_matching.py`, `app/tests/application/test_matching_integration.py`
  - **Результат:** 20/20 тестов зелёные
  - Место в архитектуре: `app/application/matching`.
  - Вход/выход (контракты):
    - Вход: `Track` из источника, top‑k кандидаты из Spotify адаптера.
    - Выход: лучший кандидат `{uri, confidence}` или `not_found/ambiguous`.
  - Тесты:
    - Unit: при наличии ISRC → exact 1.0; exact по (title+artists+duration±2s) ≥ 0.95; fuzzy ≥ threshold (напр. 0.85).
    - Unit: негативные сценарии (перестановка артистов, скобки/feat., длительность на границе толеранса).
    - Acceptance: на эталонном CSV ≥ 90% match‑rate, ≤ 2% false match.

- Задача 3.2: Батчинг, ретраи/backoff, чекпойнты ✅
  - DoR:
    - Выбран размер батча (≤100), стратегия ретраев и backoff с учётом `retry-after`.
    - Определён формат чекпойнта (плейлист, индекс батча, список уже записанных треков).
  - DoD:
    - При сбое после частичной записи корректно продолжаем без дублей.
    - Юнит‑тесты симулируют ошибки и подтверждают восстановление.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/application/pipeline.py`
  - **Тесты:** `app/tests/application/test_transfer_pipeline.py`
  - **Результат:** 14/14 тестов зелёные
  - Место в архитектуре: `app/application/pipeline`.
  - Вход/выход (контракты):
    - Вход: список пар `{sourceTrack, matchedUri}`.
    - Выход: по‑батчевые результаты и чекпойнт‑артефакты в `checkpoints/`.
  - Тесты:
    - Unit: разделение по 100; при падении после частичной вставки повтор → дозапись без дублей.
    - Integration: 429/5xx → экспоненциальный backoff с уважением `retry-after`.

- Задача 3.3: Dry‑run режим ✅
  - DoR:
    - Описана семантика `DRY_RUN` и состав отчёта в этом режиме.
  - DoD:
    - В `DRY_RUN` нет изменений состояния на стороне Spotify; формируется полный отчёт и метрики, логи помечены `dry_run=true`.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/application/pipeline.py`
  - **Тесты:** `app/tests/application/test_dry_run.py`
  - **Результат:** 10/10 тестов зелёные
  - Место в архитектуре: `app/application` (условия записи).
  - Вход/выход (контракты):
    - Вход: те же, что для 3.1/3.2.
    - Выход: отчёт с лучшими кандидатами и их URI, без операций записи.
  - Тесты:
    - E2E: запуск с `--dry-run` не вызывает `add_tracks_batch`; отчёт содержит кандидатов и confidence.

### 4. Интерфейсы

- Задача 4.1: CLI команда запуска переноса ✅
  - DoR:
    - Спецификация CLI (команда, флаги `--dry-run`, `--job-id`, выбор плейлистов/likes/all) согласована.
    - Источник конфигурации — `.env` и параметры CLI.
  - DoD:
    - Команды из `README.md` работают; корректные exit codes.
    - Логи структурированы и коррелируют по `jobId`.
    - Короткие вспомогательные команды обёрнуты таймаутом по умолчанию (см. `scripts/run_with_timeout.py`).
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/interfaces/cli.py`, `musync_cli.py`
  - **Тесты:** `app/tests/interfaces/test_cli_simple.py`
  - **Результат:** 7/7 тестов зелёные
  - Место в архитектуре: `app/interfaces/cli`.
  - Вход/выход (контракты):
    - Флаги: `--dry-run`, `--job-id`, `--include-likes`, `--only-playlists=<list>`, `--report-path`, `--checkpoint-path`, `--log-level`.
    - Источники конфигурации: `.env` < CLI.
  - Тесты:
    - Unit: парсинг флагов и приоритет конфигов.
    - E2E: корректные exit‑коды, создание артефактов в нужных каталогах.

- Задача 4.2: HTTP минимальный — health и OAuth callback для Spotify ✅
  - DoR:
    - Выбран порт и маршрут callback; Redirect URI зарегистрирован в приложении Spotify.
  - DoD:
    - `GET /health` возвращает 200 и версию.
    - OAuth callback принимает `code`, обменивает на токен и сохраняет его в отдельный файл токенов (вне репозитория), согласно политике секретов.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/interfaces/http.py`, `http_server.py`
  - **Тесты:** `app/tests/interfaces/test_http.py`
  - **Результат:** 15/15 тестов зелёные
  - Место в архитектуре: `app/interfaces/http`.
  - Вход/выход (контракты):
    - Health: `200 { version, commit? }`.
    - OAuth: вход `code`, выход — запись в `tokens.json` (`spotify` секция).
  - Тесты:
    - Integration: /health 200; /callback happy‑path (заглушка обмена токена), ошибка при недоступности.

### 5. Наблюдаемость и безопасность

- Задача 5.1: Структурированные логи без секретов, корреляция по `jobId` ✅
  - DoR: Настроен логгер, правила маскировки секретов.
  - DoD: Все ключевые этапы логируются; секреты и токены не попадают в логи.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/crosscutting/logging.py`
  - **Тесты:** `app/tests/crosscutting/test_logging.py`
  - **Результат:** 26/26 тестов зелёные
  - Место в архитектуре: `app/crosscutting/logging`.
  - Вход/выход (контракты): JSON‑логи `{ ts, level, jobId, snapshotHash, stage, playlistId?, message, fields... }`.
  - Тесты: маскирование секретов, наличие ключевых полей, корреляция по `jobId`.

- Задача 5.2: Метрики пайплайна ✅
  - DoR: Определён транспорт метрик (stdout/файл), имена согласованы (см. п.1.3).
  - DoD: Метрики доступны в e2e; есть суммарные и поэтапные значения.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/crosscutting/metrics.py`
  - **Тесты:** `app/tests/crosscutting/test_metrics.py`
  - **Результат:** 29/29 тестов зелёные
  - Место в архитектуре: `app/crosscutting/metrics`.
  - Вход/выход (контракты): JSON‑метрики per‑job/per‑batch; имена: `match_rate`, `write_success_rate`, `retry_count`, `rl_wait_ms`, `duration_ms`.
  - Тесты: корректность агрегатов; наличие per‑batch значений при ошибках.

- Задача 5.3: Минимальные scopes и хранение секретов ✅
  - DoR: Подтверждены необходимые scopes Spotify; место хранения токенов вне кода определено.
  - DoD: Проверено, что функционал работает с минимальными scopes; токены не коммитятся, `.env` в `.gitignore`.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/crosscutting/config.py`, `docs/SECURITY_GUIDE.md`
  - **Тесты:** `app/tests/crosscutting/test_config.py`
  - **Результат:** 38/38 тестов зелёные
  - Место в архитектуре: `docs/` (гайд), `app/crosscutting/config`.
  - Вход/выход (контракты): `tokens.json`, `.env`.
  - Тесты: smoke‑тест с минимальным набором scopes.

### 6. Тестирование

- Задача 6.1: Юнит‑ и контрактные тесты ✅
  - DoR: Подготовлен `TEST_PLAN.md` (юнит/контракты/e2e), фикстуры и мок‑клиенты.
  - DoD: Юнит/контрактные тесты зелёные, покрытие критичных модулей ≥ 80%.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/tests/contracts/test_music_provider_contract.py`, `app/tests/application/test_idempotency.py`
  - **Тесты:** 245/245 тестов зелёные
  - **Результат:** 97% общее покрытие, все критические модули ≥80%
  - Место в архитектуре: `app/tests`.
  - Тесты: см. матрицу выше по задачам; цель — покрытие ≥ 80% в критичных местах (matching, batching, idempotency, adapters).

- Задача 6.2: E2E и acceptance
  - DoR: Набор acceptance плейлистов/треков; заскриптован запуск.
  - DoD: E2E зелёные; соблюдены пороги `match ≥ 90%`, `false ≤ 2%`, `TTS ≤ 5 мин на 10k`.
  - Место в архитектуре: `app/tests/e2e`, артефакты в `acceptance/`.
  - Тесты: сценарии переноса 1‑2 плейлистов, повторный запуск, dry‑run.

- Задача 6.3: Gating и таймауты ✅
  - DoR: Включены таймауты по умолчанию для коротких команд, определены exit‑коды.
  - DoD: Все команды/тесты завершаются автоматически, без зависаний > 1 минуты, корректные exit codes.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `scripts/run_tests_with_gating.py`, `pytest.ini`, `app/tests/interfaces/test_cli_gating.py`, `app/tests/test_timeout_gating.py`
  - **Тесты:** 9/9 gating тестов зелёные, timeout механизмы работают
  - Место в архитектуре: `scripts/`, конфиг тестов.
  - Тесты: провалить внешние вызовы → корректные exit‑коды; таймауты срабатывают.

### 7. Выпуск и откат

- Задача 7.1: Выпуск (release)
  - DoR: Чеклист релиза сформирован, ссылки на отчёты и метрики определены.
  - DoD: Отчёт и метрики соответствуют PRD v3; все тесты зелёные; артефакты сохранены.
  - Артефакты: отчёт, метрики, логи; версия релиза `v0.1.0`.
  - Тесты: smoke‑прогон e2e перед публикацией.

- Задача 7.2: Откат (rollback) ✅
  - DoR: Стратегия отката согласована (включение `DRY_RUN` по умолчанию при проблемах).
  - DoD: Переключение в `DRY_RUN` не изменяет состояние; state неизменяем при dry‑run, подтверждено тестом.
  - **Статус:** ЗАВЕРШЕНА
  - **Файлы:** `app/interfaces/cli.py` (MUSYNC_ROLLBACK), `scripts/rollback.py`
  - **Тесты:** `app/tests/interfaces/test_cli_rollback.py` — форс dry‑run через env; e2e dry‑run подтверждён.

---

Зависимости высокого уровня:
- 2.* зависят от 1.1 (порт), 1.2 (идемпотентность — для полноценных e2e), 1.3 (схема отчёта/метрик).
- 3.* зависят от 2.* (адаптеры) и 1.2 (чекпойнты).
- 4.* можно начинать параллельно после 2.2 (OAuth) и 1.* (порт/форматы).
- 6.* закрывает итерацию; 7.* завершают релизный цикл.

Критерии приемки итерации (см. `PRD.md`):
- Match‑рейт ≥ 90% (acceptance), false match ≤ 2%.
- 0 дублей при повторном запуске с тем же `snapshotHash`.
- TTS ≤ 5 минут на 10k треков (с учётом RL).
- Полный JSON‑отчёт и метрики соответствуют согласованной схеме.
- Тест‑покрытие критичных модулей ≥ 80%; e2e зелёные; нет зависаний > 1 минуты.