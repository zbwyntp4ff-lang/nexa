# NEXA AI
**NEXA AI** — универсальная AI-платформа. Реализованы:
- **PART 1/5 — Foundation + Backend + Model Gateway**: backend на FastAPI, единый
  интерфейс провайдеров моделей (Model Gateway), конфигурация, логирование,
  обработка ошибок и тесты.
- **PART 2/5 — Memory + Tools + Agent**: модель-независимая память (Short-Term,
  Conversation, Long-Term, User Preferences), реестр инструментов с песочницей
  файловой системы, и агентский цикл (Planner → Tool Selector → Executor →
  Verifier) с защитой от бесконечных циклов.
- **PART 3/5 — Web + Vision + Multimodal Architecture**: веб-поиск/fetch/extract
  с защитой от SSRF, интерфейс Vision (+ рабочая mock-реализация и опциональная
  реальная через OpenAI), архитектура обработки документов (PDF/DOCX/TXT/CSV/JSON),
  интерфейс генерации изображений (без фейковой генерации), интерфейсы голоса
  (STT/TTS, реализация — TODO).
- **PART 4/5 — Frontend + NEXA UI**: отдельное frontend-приложение
  (`frontend/`, Next.js + TypeScript + Tailwind + shadcn/ui) — сайдбар,
  чат с Markdown/кодом/таблицами/tool-результатами, режимы
  (Chat/Agent/Code реально подключены к backend; Research/Create/Vision —
  "Coming Soon"), Projects, Settings, Light/Dark/System-тема, responsive-вёрстка,
  реальные статусы, доступность, unit- и E2E-тесты.
> Реализованы Части 1–4.
## Архитектура
```
app/
├── main.py              # точка входа FastAPI, регистрация роутов и обработчиков ошибок
├── core/
│   ├── nexa_core.py      # NexaCore — оркестрация чата, валидация, логирование, таймауты
│   ├── logging_config.py # настройка логирования + редактирование секретов
│   ├── secrets.py        # общие паттерны/утилиты обнаружения секретов (логи + память)
│   └── paths.py          # PROJECT_ROOT и разрешение относительных путей конфигурации
├── api/
│   ├── deps.py           # dependency injection (NexaCore, MemoryManager, Agent)
│   └── routes/
│       ├── health.py     # GET /health
│       ├── status.py     # GET /api/v1/status
│       ├── model.py      # GET /api/v1/model
│       ├── chat.py       # POST /api/v1/chat
│       ├── memory.py     # GET/POST/DELETE /api/v1/memory[/{id}]
│       └── agent.py      # POST /api/v1/agent (Part 4 addition, exposes Part 2's Agent over HTTP)
├── models/
│   ├── chat.py           # ChatMessage, ChatRequest, ChatResponse
│   ├── errors.py         # доменные исключения (NexaError и наследники)
│   ├── status.py         # HealthResponse, StatusResponse, ModelInfoResponse, ErrorResponse
│   ├── memory_api.py     # request/response модели для /api/v1/memory
│   └── agent_api.py      # request/response модели для /api/v1/agent
├── providers/
│   ├── base.py            # интерфейс AIProvider (generate/stream/health_check)
│   ├── mock.py            # MockProvider — работает без интернета и ключей
│   ├── openai_provider.py    # OpenAIProvider (использует OpenAI SDK)
│   ├── anthropic_provider.py # AnthropicProvider (использует Anthropic SDK)
│   ├── local_provider.py     # LocalProvider — HTTP-адаптер к локальному серверу (Ollama-совместимый)
│   └── factory.py         # ProviderFactory — выбор провайдера по конфигурации
├── memory/                 # Part 2 — модель-независимая память
│   ├── models.py           # MemoryItem, MemoryType
│   ├── store.py            # MemoryStore (интерфейс), LocalMemoryStore (JSON), InMemoryStore
│   ├── vector_store.py     # VectorMemoryStore — подготовленный интерфейс для будущей vector DB
│   └── manager.py          # MemoryManager: save/search/get/delete/clear + защита от секретов
├── tools/                  # Part 2 — инструменты агента
│   ├── base.py             # интерфейс Tool (name/description/input_schema/permissions/execute)
│   ├── sandbox.py          # resolve_safe_path — защита от path traversal
│   ├── calculator.py       # CalculatorTool (безопасный разбор через ast, без eval)
│   ├── current_time.py     # CurrentTimeTool
│   ├── file_read.py        # FileReadTool (только внутри песочницы)
│   ├── file_write.py       # FileWriteTool (только внутри песочницы)
│   ├── directory_list.py   # DirectoryListTool (только внутри песочницы)
│   └── registry.py         # ToolRegistry: register/unregister/get/list/execute
├── agent/                  # Part 2 — агентский цикл
│   ├── models.py           # AgentTask, AgentStep, AgentState, AgentResult, PlannedAction
│   ├── planner.py          # Planner (интерфейс) + RuleBasedPlanner
│   ├── tool_selector.py    # ToolSelector — резолвинг инструмента + проверка permissions
│   ├── executor.py         # Executor — запуск инструмента (или dry-run симуляция)
│   ├── verifier.py         # Verifier — проверка результата (напр. перечитывает файл)
│   └── agent.py            # Agent — основной цикл с MAX_STEPS/TIMEOUT/ERROR_LIMIT/CANCELLATION
├── web/                    # Part 3 — веб-исследование
│   ├── models.py           # SearchResult, PageDocument
│   ├── security.py         # validate_url — защита от SSRF (private IP/localhost/file://)
│   ├── search_provider.py  # SearchProvider, MockSearchProvider, HttpSearchProvider, Factory
│   ├── page_fetcher.py     # PageFetcher — timeout/max size/safe redirects
│   ├── content_extractor.py # ContentExtractor — HTML -> (title, text)
│   ├── source_manager.py   # SourceManager — дедупликация источников
│   └── research_tool.py    # ResearchTool (Tool из Part 2): search/fetch/extract/sources
├── vision/                 # Part 3 — понимание изображений
│   ├── models.py           # VisionAnalysisResult
│   ├── base.py             # интерфейс VisionProvider
│   ├── mock.py             # MockVisionProvider (работает офлайн)
│   ├── openai_provider.py  # OpenAIVisionProvider (требует OPENAI_API_KEY)
│   └── factory.py          # VisionProviderFactory
├── documents/               # Part 3 — обработка документов
│   ├── models.py            # ParsedDocument
│   ├── base.py              # интерфейс DocumentParser
│   ├── txt_parser.py / csv_parser.py / json_parser.py  # stdlib-only, полностью рабочие
│   ├── pdf_parser.py        # через pypdf
│   ├── docx_parser.py       # через python-docx
│   └── processor.py         # DocumentProcessor — диспетчер по расширению файла
├── image_generation/        # Part 3 — генерация изображений (архитектура)
│   ├── models.py             # ImageGenerationResult
│   ├── base.py                # интерфейс ImageGenerationProvider (generate/edit)
│   ├── not_configured.py     # NotConfiguredImageGenerationProvider (по умолчанию)
│   ├── openai_provider.py    # OpenAIImageGenerationProvider (опционально, требует API)
│   └── factory.py             # ImageGenerationProviderFactory
├── voice/                    # Part 3 — интерфейсы голоса (реализация — TODO)
│   ├── models.py              # TranscriptionResult, SynthesisResult
│   ├── base.py                 # SpeechToTextProvider, TextToSpeechProvider
│   ├── not_configured.py      # реализации по умолчанию ("не настроено")
│   └── factory.py              # фабрики (пока всегда возвращают "не настроено")
├── config/
│   └── settings.py        # Settings (pydantic-settings), чтение .env
└── services/               # зарезервировано для последующих частей проекта
scripts/
├── demo_agent.py           # демо: "Посчитай 25 * 37 и сохрани результат в файл."
└── demo_research.py        # демо: реальный веб-поиск + fetch + extract (ResearchTool)
frontend/                   # Part 4 — отдельное frontend-приложение (Next.js/TS/Tailwind/shadcn)
├── src/app/                # App Router: layout.tsx, page.tsx, globals.css (NEXA-тема)
├── src/components/
│   ├── layout/               # AppShell, Header, Sidebar (desktop) + mobile drawer
│   ├── chat/                  # Conversation, Message, Composer, ModeSelector,
│   │                            StatusIndicator, MarkdownMessage, ToolResultList
│   ├── settings/                # SettingsDialog + 7 секций
│   ├── projects/                 # ProjectPanel
│   └── theme/                     # ThemeProvider/ThemeToggle (next-themes)
├── src/lib/api.ts            # HTTP-клиент к backend (без API-ключей)
├── src/store/                 # Zustand: chat-store, ui-store (localStorage)
├── src/test/                   # Vitest + React Testing Library
└── e2e/                         # Playwright
```
### Ключевые принципы
- **NEXA Core не зависит от конкретного провайдера.** `NexaCore` работает только с
  абстракцией `AIProvider` (см. `app/providers/base.py`). Конкретную реализацию
  подставляет `ProviderFactory` на основании конфигурации (`AI_PROVIDER`).
- **Провайдер выбирается через конфигурацию**, без изменений кода:
  `AI_PROVIDER=mock|openai|anthropic|local` (в будущем — `nexa`).
- **Секреты никогда не хранятся в коде.** API-ключи читаются только из переменных
  окружения (`.env`), не логируются и маскируются даже при выводе объекта настроек
  (`Settings.masked_dict()`), а лог-фильтр `SecretRedactionFilter` дополнительно
  вычищает похожие на ключи строки из любых логов.
- **Ошибки не показывают пользователю stack trace.** Все доменные ошибки — это
  подклассы `NexaError`, которые единый обработчик в `app/main.py` превращает в
  компактный JSON (`{"error": "...", "message": "..."}`) с подходящим HTTP-статусом.
  Любое непойманное исключение превращается в generic `500 Internal Server Error`.
## Memory (Part 2)
`MemoryManager` — единая точка входа для сохранения/поиска памяти, полностью
независимая от конкретного AI-провайдера. Поддерживает 4 типа памяти
(`MemoryType`): `short_term`, `conversation`, `long_term`, `user_preference`.
- **Хранилище (MVP)**: `LocalMemoryStore` — JSON-файл на диске (путь задаётся
  `MEMORY_STORE_PATH`), потокобезопасен в рамках одного процесса. Для тестов
  доступен `InMemoryStore` (не пишет на диск).
- **Интерфейс `MemoryStore`**: `save() / get() / search() / delete() / clear()`
  — любая новая реализация (например, векторная БД) просто реализует этот же
  интерфейс, и ничего в остальном коде менять не нужно.
- **Подготовка к vector database**: `app/memory/vector_store.py` определяет
  `VectorMemoryStore` (наследник `MemoryStore`) и `Embedder` — контракт для
  будущей семантической памяти. Сейчас не используется (`NotImplementedError`),
  это только зарезервированная точка расширения.
- **Защита секретов**: `MemoryManager.save()` отклоняет контент/метаданные,
  похожие на API-ключи, пароли или токены (`SecretInMemoryError`, `400`), используя
  общий детектор секретов `app/core/secrets.py` (тот же, что и в логировании).
## Tools (Part 2)
`Tool` — единый интерфейс инструмента (`name`, `description`, `input_schema`,
`permissions`, `execute()`). `ToolRegistry` регистрирует, находит и выполняет
инструменты (`register / unregister / get / list / execute`), нормализуя любые
неожиданные исключения инструмента в `ToolExecutionError`.
Встроенные инструменты:
| Инструмент | permissions | Описание |
|---|---|---|
| `calculator` | `compute` | Безопасный разбор арифметики через `ast` (без `eval`, защита от инъекций) |
| `current_time` | `time` | Текущее время в UTC (ISO 8601) |
| `file_read` | `filesystem:read` | Чтение текстового файла из песочницы |
| `file_write` | `filesystem:write` | Запись текстового файла в песочницу |
| `directory_list` | `filesystem:read` | Список файлов/папок в песочнице |
**Песочница файловой системы.** `file_read` / `file_write` / `directory_list`
работают только внутри каталога `AGENT_WORKSPACE_DIR` (по умолчанию
`agent_workspace/` в корне проекта). `app/tools/sandbox.py::resolve_safe_path`
нормализует любой путь (относительный, абсолютный, с `..`) и гарантированно не
позволяет выйти за пределы песочницы — попытка обхода (`../../etc/passwd` и
т.п.) возвращает `PathTraversalError` вместо доступа к реальному файлу.
Произвольный shell намеренно **не** добавлен.
## Agent (Part 2)
Архитектура агентского цикла:
```
User -> Agent -> Planner -> (Model, зарезервировано) -> Tool Selector -> Tool
      -> Observation -> Verifier -> [повтор цикла] -> Final Answer
```
- **`Planner`** — абстрактный интерфейс; `RuleBasedPlanner` — детерминированный
  MVP-планировщик на основе распознавания паттернов в тексте задачи (без
  вызова какой-либо модели, полностью тестируемый). Между Planner и Tool
  Selector архитектурно зарезервирован шаг "Model" — в будущей части сюда
  можно подключить `AIProvider` из Part 1 для свободного планирования через LLM,
  не меняя цикл `Agent`.
- **`ToolSelector`** — резолвит имя инструмента в конкретный `Tool` и проверяет
  разрешённые `permissions` (`ToolPermissionError` при нарушении).
- **`Executor`** — выполняет вызов инструмента через `ToolRegistry` (или
  симулирует его в режиме `dry_run`, не производя побочных эффектов).
- **`Verifier`** — проверяет результат шага; для `file_write` дополнительно
  перечитывает файл и сверяет содержимое.
Защита от бесконечных циклов и зависаний:
| Параметр | Переменная окружения | По умолчанию |
|---|---|---|
| `MAX_STEPS` | `AGENT_MAX_STEPS` | `10` |
| `TIMEOUT` | `AGENT_TIMEOUT_SECONDS` | `30` |
| `ERROR_LIMIT` | `AGENT_ERROR_LIMIT` | `3` |
| `CANCELLATION` | передаётся как `asyncio.Event` в `Agent.run(task, cancel_event=...)` | — |
`AgentTask(dry_run=True)` прогоняет весь план (Calculator → FileWrite → …) без
каких-либо реальных побочных эффектов — полезно для предпросмотра плана агента.
### Демо-задача
```bash
source .venv/bin/activate
python scripts/demo_agent.py             # реальный запуск
python scripts/demo_agent.py --dry-run   # симуляция без побочных эффектов
```
Задача: *«Посчитай 25 * 37 и сохрани результат в файл.»* Агент: выбирает
`calculator` → получает `925` → выбирает `file_write` → записывает `925` в
`agent_workspace/result.txt` → `Verifier` перечитывает файл и подтверждает
содержимое → возвращает финальный ответ.
## Web Research (Part 3)
**Полностью рабочая** цепочка `search → fetch → extract → sources`:
- **`SearchProvider`** — интерфейс; `MockSearchProvider` (по умолчанию, офлайн,
  детерминированный) и `HttpSearchProvider` — универсальный адаптер к любому
  JSON-based search API (`SEARCH_API_URL` + опционально `SEARCH_API_KEY`).
  NEXA намеренно **не** содержит скрейпер конкретной поисковой системы — это
  нарушало бы "не обходи ограничения сайтов".
- **`PageFetcher`** — реально скачивает страницу через `httpx` (проверено
  живым запросом к `example.com`, см. `scripts/demo_research.py`).
- **`ContentExtractor`** — превращает HTML в `(title, text)` без стороннего
  HTML/JS-движка (только `html.parser` из stdlib — скрипты/стили никогда не
  исполняются, только текст).
- **`SourceManager`** — дедуплицирует источники по URL и по `content_hash`.
- **`ResearchTool`** — реализует интерфейс `Tool` из Part 2 (`search()` /
  `fetch()` / `extract()` + `execute()`, возвращающий `sources`).
### Безопасность (обязательные меры)
| Требование | Реализация |
|---|---|
| timeout | `WEB_FETCH_TIMEOUT_SECONDS` — таймаут `httpx` клиента |
| maximum page size | Потоковое чтение тела ответа с обрывом при превышении `WEB_MAX_PAGE_SIZE_BYTES` (не доверяет заголовку `Content-Length`) |
| maximum results | `WEB_MAX_SEARCH_RESULTS` — верхняя граница числа результатов поиска |
| SSRF protection | `app/web/security.py::validate_url` — проверяется каждый URL и каждый redirect-хоп |
| блокировка localhost | `localhost`, `127.0.0.1`, `::1`, `0.0.0.0` и т.п. блокируются |
| блокировка private network | RFC1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local (`169.254.0.0/16`, включая cloud metadata `169.254.169.254`), reserved/multicast — через `ipaddress.ip_address(...).is_private/.is_loopback/.is_link_local/...` |
| запрет `file://` | Разрешены только схемы `http`/`https` |
| безопасные redirects | Redirect-и обрабатываются вручную (не библиотекой), каждый хоп заново проходит `validate_url`, число хопов ограничено `WEB_MAX_REDIRECTS` |
| DNS rebinding | Хост резолвится, и **все** полученные IP проверяются тем же блок-листом (даже если домен выглядит публичным) |
CAPTCHA и ограничения сайтов **не обходятся** — при `HTTP 4xx/5xx` инструмент
возвращает ошибку, а не пытается притвориться браузером/обойти защиту.
### Демо
```bash
source .venv/bin/activate
python scripts/demo_research.py "NEXA AI platform"
```
Делает реальный HTTP-запрос (через `MockSearchProvider`, который указывает на
`example.com` — стабильный, всегда доступный домен) и показывает результат
полного пайплайна `search → fetch → extract`.
## Vision (Part 3)
Архитектура: `Image -> VisionProvider -> structured analysis`. NEXA **не**
создаёт собственную vision-модель — только абстракцию провайдера, как и в
Model Gateway (Part 1).
- **`VisionProvider`** (`app/vision/base.py`) — интерфейс: `analyze(image: bytes,
  mime_type: str, prompt: str | None) -> VisionAnalysisResult`, `health_check()`.
- **`MockVisionProvider`** — **реально работает без API** (детерминированный,
  офлайн), используется по умолчанию (`VISION_PROVIDER=mock`).
- **`OpenAIVisionProvider`** — **требует `OPENAI_API_KEY`**; отправляет
  изображение как base64 data URI в vision-совместимую модель чата
  (`OPENAI_VISION_MODEL`, по умолчанию `gpt-4o-mini`).
- **`VisionProviderFactory`** — выбор реализации через `VISION_PROVIDER=mock|openai`.
## Documents (Part 3)
Архитектура: любой документ → `DocumentParser` → `ParsedDocument` (структурированный
текст + метаданные). Парсеры **только читают** содержимое — никогда не
выполняют, не `eval`-ят и не запускают код из загруженного файла.
| Формат | Парсер | Статус |
|---|---|---|
| `.txt` / `.md` | `TxtParser` | **работает** (только stdlib) |
| `.csv` | `CsvParser` | **работает** (только stdlib, модуль `csv`) |
| `.json` | `JsonParser` | **работает** (только stdlib, модуль `json`) |
| `.pdf` | `PdfParser` | **работает** (через `pypdf`) |
| `.docx` | `DocxParser` | **работает** (через `python-docx`) |
`DocumentProcessor` диспетчеризует по расширению файла, ограничивает
максимальный размер (`MAX_DOCUMENT_SIZE_BYTES`) и превращает любые сбои парсера
в `DocumentParsingError` (без утечки внутренних деталей библиотек).
## Image Generation (Part 3)
`ImageGenerationProvider` — интерфейс с методами `generate(prompt, **kwargs)`
и `edit(image, prompt, mask=None, **kwargs)`. NEXA **не генерирует
изображения сама** и **не подделывает** результат.
- По умолчанию (`IMAGE_PROVIDER=none`, или `openai` без `OPENAI_API_KEY`)
  используется `NotConfiguredImageGenerationProvider` — оба метода
  корректно поднимают ошибку с текстом ровно:
  **`"Image generation provider is not configured."`**
- Если `IMAGE_PROVIDER=openai` и `OPENAI_API_KEY` заданы — используется
  реальный `OpenAIImageGenerationProvider` (**требует API**, DALL·E/`OPENAI_IMAGE_MODEL`).
## Voice (Part 3, интерфейсы)
`SpeechToTextProvider.transcribe()` и `TextToSpeechProvider.synthesize()` —
интерфейсы подготовлены. Реализация оставлена как **TODO**, как и разрешено
условием задачи: по умолчанию используются `NotConfiguredSpeechToTextProvider` /
`NotConfiguredTextToSpeechProvider`, которые сразу и понятно сообщают об
отсутствии настроенного сервиса, а не подделывают транскрипцию/аудио.
## Frontend (Part 4)
Отдельное приложение в `frontend/` (Next.js + TypeScript + Tailwind CSS +
shadcn/ui) — собственная визуальная идентичность NEXA (фиолетово-голубой
градиент, tagline *«Think. Create. Act.»*), полностью отделённая от backend
слоем HTTP: frontend никогда не хранит API-ключи, только вызывает
`app/api/routes/*` этого backend. Подробная документация — в
`frontend/README.md`.
### Layout и возможности
- **Sidebar** (desktop — постоянный, mobile/tablet — Drawer через
  hamburger-меню): New Chat, поиск по истории, Recent Chats (rename/delete),
  Projects, Settings, Profile.
- **Чат**: Markdown (таблицы, списки, ссылки, изображения), синтаксис-хайлайт
  кода с кнопкой Copy, tool-результаты Agent-режима, действия
  Copy/Retry/Regenerate/Edit/Stop.
- **Input**: `Ask NEXA...`, `Enter` = отправить, `Shift+Enter` = новая
  строка, drag & drop файлов, кнопки Attachment/Image/Voice/Send/Stop.
- **Режимы** (`Chat`/`Agent`/`Code`/`Research`/`Create`/`Vision`) — единое
  приложение: **Chat/Agent/Code реально подключены** к backend
  (`POST /api/v1/chat`, `POST /api/v1/agent`); **Research/Create/Vision**
  показывают "Coming Soon" — никакая функция не имитируется.
- **Projects**: conversations, files (метаданные), memory (реально через
  `/api/v1/memory`, с тегом `project_id`), instructions.
- **Settings**: General, Appearance (Light/Dark/System, сохраняется в
  `localStorage`), Models (живой статус из `/api/v1/status` + `/api/v1/model`),
  Memory (полный CRUD через `/api/v1/memory`), Privacy, Tools
  (документация реальных инструментов агента), About.
- **Статусы**: `Online`/`Offline` (реальный опрос `/health`), `Thinking`
  (Chat/Code запрос в полёте), `Using tool` (Agent запрос в полёте),
  `Error` (реальный сбой запроса) — `Researching`/`Generating` зарезервированы
  для Research/Create, когда они получат backend-эндпоинт.
- **Responsive**: desktop/laptop (постоянный sidebar) → tablet/mobile
  (drawer), перенос длинного текста, горизонтальный scroll для code-блоков.
- **Доступность**: семантический HTML (`header`/`main`/`aside`/`nav`),
  `aria-label` на все icon-only кнопки, видимые focus-ring везде (проверено
  Tab/Shift+Tab), диалоги (Settings/Projects/Alert) с focus-trap и
  закрытием по `Escape` "из коробки" (Base UI).
### Запуск вместе с backend
```bash
# Терминал 1 — backend
source .venv/bin/activate && uvicorn app.main:app --reload --port 8420
# Терминал 2 — frontend
cd frontend && npm install && cp .env.example .env.local && npm run dev -- -p 4820
```
Откройте `http://localhost:4820` (используйте тот же hostname, с которым
запущен `next dev` — см. `frontend/README.md` про `allowedDevOrigins`).
### Тесты frontend
```bash
cd frontend
npm run test      # Vitest + React Testing Library: 51 тестов
npm run e2e       # Playwright (свой dev-сервер, backend мокается через route())
npm run build     # production-сборка
```
## Установка
Требуется Python 3.12+.
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # включает requirements.txt + pytest
cp .env.example .env                  # при необходимости отредактируйте ключи
```
## Запуск
```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8420
```
По умолчанию (`AI_PROVIDER=mock`) сервер работает **без каких-либо API-ключей** —
`MockProvider` детерминированно "эхо"-отвечает на сообщения, что удобно для
разработки и тестов.
Проверка:
```bash
curl http://127.0.0.1:8420/health
curl http://127.0.0.1:8420/api/v1/status
curl http://127.0.0.1:8420/api/v1/model
curl -X POST http://127.0.0.1:8420/api/v1/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Привет, NEXA!"}'
```
## Конфигурация
Все настройки задаются через переменные окружения / файл `.env` (см. `.env.example`):
| Переменная | Назначение | По умолчанию |
|---|---|---|
| `AI_PROVIDER` | `mock` \| `openai` \| `anthropic` \| `local` | `mock` |
| `OPENAI_API_KEY` | Ключ OpenAI API (требуется для `AI_PROVIDER=openai`) | — |
| `OPENAI_MODEL` | Модель OpenAI | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | Ключ Anthropic API (требуется для `AI_PROVIDER=anthropic`) | — |
| `ANTHROPIC_MODEL` | Модель Anthropic | `claude-3-5-sonnet-latest` |
| `LOCAL_MODEL_URL` | URL локального инференс-сервера (требуется для `AI_PROVIDER=local`) | `http://localhost:11434` |
| `LOCAL_MODEL_NAME` | Имя локальной модели | `llama3` |
| `MAX_MESSAGE_LENGTH` | Максимальная длина сообщения пользователя | `4000` |
| `REQUEST_TIMEOUT_SECONDS` | Таймаут запроса к провайдеру | `30` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `MEMORY_STORE_PATH` | Путь к JSON-файлу локального хранилища памяти | `data/memory_store.json` |
| `MEMORY_SEARCH_LIMIT` | Лимит результатов поиска по памяти по умолчанию | `10` |
| `AGENT_WORKSPACE_DIR` | Песочница для `file_read`/`file_write`/`directory_list` | `agent_workspace` |
| `MAX_FILE_READ_BYTES` | Максимальный размер файла, который можно прочитать | `1000000` |
| `AGENT_MAX_STEPS` | Максимум шагов агента за один запуск | `10` |
| `AGENT_TIMEOUT_SECONDS` | Таймаут одного запуска агента | `30` |
| `AGENT_ERROR_LIMIT` | Максимум неудачных шагов подряд перед остановкой | `3` |
| `WEB_SEARCH_PROVIDER` | `mock` \| `http` | `mock` |
| `SEARCH_API_URL` / `SEARCH_API_KEY` | Эндпоинт/ключ для `http`-поиска (требуется для `WEB_SEARCH_PROVIDER=http`) | — |
| `WEB_FETCH_TIMEOUT_SECONDS` | Таймаут загрузки страницы | `10` |
| `WEB_MAX_PAGE_SIZE_BYTES` | Максимальный размер загружаемой страницы | `2000000` |
| `WEB_MAX_SEARCH_RESULTS` | Максимум результатов поиска | `5` |
| `WEB_MAX_REDIRECTS` | Максимум redirect-хопов при загрузке страницы | `3` |
| `VISION_PROVIDER` | `mock` \| `openai` | `mock` |
| `OPENAI_VISION_MODEL` | Vision-модель OpenAI (требуется для `VISION_PROVIDER=openai`) | `gpt-4o-mini` |
| `MAX_DOCUMENT_SIZE_BYTES` | Максимальный размер обрабатываемого документа | `10000000` |
| `IMAGE_PROVIDER` | `none` \| `openai` | `none` |
| `OPENAI_IMAGE_MODEL` | Модель генерации изображений (требуется для `IMAGE_PROVIDER=openai`) | `dall-e-3` |
| `STT_PROVIDER` / `TTS_PROVIDER` | Зарезервировано (реализация — TODO) | `none` |
| `CORS_ALLOWED_ORIGINS` | Разрешённые origin для отдельного frontend-приложения (Part 4), через запятую | `http://localhost:3000,http://127.0.0.1:3000,http://localhost:4820,http://127.0.0.1:4820` |
API-ключи **никогда** не должны попадать в код или в git — `.env` уже добавлен в
`.gitignore`. Каталоги `agent_workspace/` и `data/` (создаются автоматически во
время выполнения) также исключены из git.
