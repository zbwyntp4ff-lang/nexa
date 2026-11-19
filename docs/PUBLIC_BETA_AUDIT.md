# НЕХА — аудит безопасности и готовности к публичной бете

**Дата обновления:** 19 ноября 2026 года  
**Основная ветка:** `main`  
**Последнее объединение:** PR #5, commit `0d180f2e798eba1b49b6f226473ba73fb7448d7d`  
**Продолжение работ:** PR #28 — <https://github.com/zbwyntp4ff-lang/nexa/pull/28>, пока открыт и не объединён.

## Текущий статус

PR #5 объединён в `main`. Его Python, Electron, frontend, npm/pip audit и Docker build/smoke проверки прошли на проверенных коммитах до объединения.

PR #28 добавляет долговечные ownership manifests для image attachments и video jobs. На момент этого обновления CI PR #28:
- Python tests — успешно;
- Electron IPC/packaging — успешно;
- Frontend tests/build и production npm audit — успешно;
- Docker build/smoke — выполняется.

Пока PR #28 не объединён, его изменения не входят в `main`.

**НЕХА не объявляется готовой к публичному запуску.** Автоматические тесты и code review не заменяют реальное staging-тестирование, инфраструктурную настройку и независимый penetration test.

## Что уже исправлено в PR #5

- Cookie-based authentication, CSRF Origin checks и same-host Electron UI/API cookies.
- OAuth fail-closed при отсутствующем подтверждении email.
- Device-login bearer tokens исключены из постоянного auth JSON; user-bound device/passkey записи очищаются при удалении аккаунта.
- Workflow approvals ограничены владельцем.
- Изоляция agent workspace, memory, plugins, attachments и video jobs по user_id.
- Контекст агента сбрасывается через `finally` в том числе при исключениях и отмене.
- Новые plugin secrets шифруются AES-256-GCM; старый NEXA1 поддерживается только для чтения.
- Auth/memory/plugin JSON stores работают с атомарной записью и fail-closed при повреждении.
- Writable Electron data/database/credentials/workspaces перемещены в userData; существующие локальные файлы мигрируются.
- Docker runtime очищен от dev-зависимостей.

## Дополнительные исправления PR #28 — проверка ещё идёт

- Image attachment manifests хранят ownership и ограниченные metadata; после рестарта проверяются ID, TTL, размер, тип и реальная сигнатура файла.
- Orphaned image files удаляются при старте attachment manager.
- Document attachments остаются намеренно временными: extracted text/chunks in-memory, исходные файлы удаляются после parsing.
- Video job owner/status manifest записывается атомарно с ограниченными правами файла.
- Завершённые локальные видео и их ACL восстанавливаются после рестарта; незавершённые jobs помечаются failed.
- Motion prompts, image descriptions, provider error details и подписанные remote URLs не сохраняются в video manifest.
- Повреждённый video manifest не перезаписывается автоматически.
- Account wipe удаляет записи video jobs и принадлежащие пользователю отслеживаемые локальные видео.

## Что осталось до публичной беты

### P1 — Внешний rate limiting

Встроенные API/auth лимитеры работают в памяти одного процесса и сбрасываются при рестарте. Нужен доверенный CDN/WAF или reverse proxy с ограничениями по IP и отдельными лимитами для:
- `/api/v1/auth/login`;
- регистрации и восстановления пароля;
- ресурсоёмких AI/video/upload endpoints;
- общего `/api/*`.

Нельзя доверять произвольному `X-Forwarded-For`. Реальный IP должен устанавливаться только от явно доверенных proxy ranges. Инструкция: `docs/EDGE_RATE_LIMITING.md`.

### P1 — Однопроцессный режим и постоянное хранилище

Текущие JSON stores и in-memory queues не дают транзакционной координации между несколькими worker-процессами или репликами. До внедрения общей транзакционной БД, распределённых очередей и shared rate limiting запускать только один экземпляр приложения и один API worker. Persistent volume обязателен для JSON stores, SQLite, image attachments и videos.

### P1 — Staging

На отдельном production-like staging, без реальных пользователей, проверить:
- регистрацию, email verification, login/logout, session renewal;
- OAuth Google/GitHub/Apple и device login;
- изоляцию двух пользователей для memory, plugins, agent workspace, images, videos и account wipe;
- restart во время загрузки документа, image upload и video generation;
- истечение TTL и удаление orphaned media;
- восстановление из backup;
- HTTPS, Secure/HttpOnly/SameSite cookies, CORS, CSRF, trusted proxy headers и edge limits;
- SMTP delivery, named AI provider, timeout/error handling и kill switch.

### P1 — Production secrets и эксплуатация

До регистрации должны быть настроены и проверены в secret manager:
- `TOKENS_ENFORCE=true`;
- `AUTH_COOKIE_SECURE=true` за HTTPS;
- `AUTH_SKIP_EMAIL_VERIFICATION=false`;
- `AUTH_BOOTSTRAP_FIRST_OWNER=false` с явным owner allow-list;
- SMTP host/credentials/from;
- production AI provider key и конкретная модель;
- точные HTTPS origins для CORS/Auth/Billing;
- persistent disk или managed database;
- резервные копии с проверенным восстановлением;
- мониторинг, алерты, логирование без секретов и процедура реагирования на инциденты.

### P2 — Миграция существующих desktop данных

На копии реальных данных проверить перенос Electron userData, legacy memory/plugin records, workspaces и OAuth credentials. Не назначать старые unscoped данные новому аккаунту автоматически без проверки владельца.

## Границы аудита

- PR #5: code-level review и автоматические проверки критических изменений auth, OAuth, CSRF, SSRF/DNS pinning, sandbox paths, per-user isolation, plugin secrets, account wipe и Electron packaging.
- PR #28: review и CI для durable media manifests; результаты CI перечислены выше и могут измениться до merge.
- npm и pip audits проверяют известные advisory на момент запуска, но не доказывают отсутствие всех уязвимостей.
- Не проводился внешний penetration test, независимый security assessment или live production validation.
- Не создавались cloud resources, домены, DNS records и production secrets; платные сервисы не подключались.

## Решение

**NO-GO для открытой публичной регистрации до завершения PR #28, edge rate limiting, staging smoke/acceptance, backup restore и независимой проверки.** Текущая работа — подготовка к staging, не production launch.
