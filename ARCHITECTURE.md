# ARCHITECTURE v3 — MuSync

## 1. Цель архитектуры
Обеспечить перенос плейлистов между музыкальными сервисами надёжно, объяснимо и масштабируемо, сохраняя независимость доменного ядра от инфраструктуры и конкретных провайдеров.

## 2. Принципы
- Hexagonal (Ports & Adapters): домен независим от фреймворков и I/O.
- Stateless воркеры; состояние — вне процесса (БД/ключ‑значение/объектное хранилище).
- 12‑factor: конфиг через ENV, лог‑стримы, один билд — многие развёртывания.
- Testability First: слои и порты проектируются под тесты (юнит/контракты/e2e).
- Observability: структурированные логи, метрики, трассировка.

## 3. Слои
1) Domain (чистый код): сущности, значения, политики и инварианты.
2) Application (use cases): оркестрация доменной логики, батчинг, ретраи, дедлайны.
3) Adapters (infrastructure): провайдеры (Spotify, Яндекс, далее Apple/YouTube), хранилища, очереди, секреты, метрики.
4) Interfaces (delivery): CLI и минимальный HTTP (health, OAuth callback).

## 4. Порты (ключевые контракты)
- MusicProvider: readPlaylists(), readTracks(playlistId), searchTrack(query|isrc), createOrResolvePlaylist(name, visibility), addTracks(playlistId, trackIds, batch).
- StorageAdapter: saveCheckpoint(jobId, batchIdx, state), loadCheckpoint(jobId), saveReport(jobId, json).
- Reporter: append(event), finalize(summary).
- SecretsManager: get(name), set(name, value), rotate(name).
- QueueAdapter (Итер.3): enqueue(job), ack(jobId), retry(jobId, delay).
- MetricsAdapter: increment(name, tags), observe(name, value, tags), time(name, fn).
- Clock/Deadline: now(), withTimeout(deadline, fn).

## 5. DDD модель (сжатая)
- Playlist: id, name, ownerType, visibility.
- Track: id, title, artists[], durationMs, isrc?, album.
- MatchCandidate: trackId?, confidence, reason.
- MatchResult: sourceTrack, targetTrack?, stage, confidence, reason.
- TransferJob: jobId, userId, source, target, snapshotHash, createdAt.
- BatchCheckpoint: jobId, batchIdx, stage, cursor, attempts.

## 6. Ключевые политики
### 6.1 Идемпотентность
Ключ: (userId, source, target, snapshotHash). snapshotHash вычисляется из детерминированного списка исходных треков (нормализованное название, артисты, длительность, ISRC при наличии). Повторный запуск с тем же ключом не создаёт дублей; выполняется reconcile на уровне батча.

### 6.2 Матчинг (конфигурируемый pipeline)
Последовательность: ISRC → exact(title+artist+duration±2s) → fuzzy(нормализация+левенштейн). Пороги и нормализация — в конфиге. Логируются top‑k кандидатов и причина not_found.

### 6.3 Rate limiting / Retries / Backoff
Единый модуль RL уважает `retry-after` провайдеров. Ретраи — экспоненциальный backoff с джиттером, предельные попытки на батч. Дедлайны на операцию и на джобу. Circuit breaker (Итер.3).

## 7. Потоки данных (высокоуровневые)
1) OAuth (Spotify): интерфейс HTTP принимает callback, сохраняет токен в SecretsManager (или внешнее безопасное хранилище).
2) Transfer (CLI/джоба):
   - Скан исходных плейлистов (Яндекс) → построение снапшота → расчёт snapshotHash.
   - Для каждого плейлиста: батчевый матчинг → батчевое добавление в целевой плейлист.
   - Чекпойнт после каждого батча; отчёт и метрики по завершении.

## 8. Конфигурация и секреты
ENV переменные: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, YANDEX_MUSIC_TOKEN, LOG_LEVEL, SYNC_BATCH_SIZE, MAX_RETRIES, RETRY_DELAY, DEBUG, ENVIRONMENT. Секреты не логируются; маскирование по шаблонам.

## 9. Наблюдаемость
- Логи: корреляция по jobId; события этапов (scan/match/write), причины ошибок.
- Метрики: match_rate, write_success_rate, retry_count, rl_wait_ms, duration_ms, not_found_count.
- Трассировка: спаны per batch и per provider‑call.

## 10. Безопасность
- Минимальные scopes Spotify: обязательные playlist-read-private, playlist-modify-private; опционально playlist-modify-public (если целевой плейлист публичный). Токены хранятся вне кода; ротация по расписанию.

## 11. Масштабирование (Итер.3)
- Очередь задач и пул воркеров; горизонтальное масштабирование.
- Изоляция tenant‑ов по ключам/пространствам; квоты и дросселирование.
- P95 ≤ 2 мин при 100 параллельных задачах.

## 12. Таксономия ошибок
- Retriable: сетевые, 5xx провайдеров, 429 (с уважением retry-after).
- Non‑retriable: 4xx (неправильные данные/скоупы), валидация домена.
- Partial success: фиксация в отчёте, продолжение пайплайна.

## 13. Портируемость и деплой
- Контейнеры; внешние БД/очереди/секреты; независимость от облака.
- Один образ — разные окружения; конфиг через ENV.

## 14. Связанные документы
- PRD v3: docs/PRD.md
- ADR: docs/adr/*
- TEST PLAN: TEST_PLAN.md


