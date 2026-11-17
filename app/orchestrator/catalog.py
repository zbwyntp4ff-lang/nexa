"""Curated catalogue of 100 specialist roles for the NEXA multi-agent system.

These are role definitions, not 100 separately hosted model instances. Runtime
execution currently reuses the five permission-scoped agent profiles. A later
dispatcher can route tasks to these roles and inject their role instructions.
"""
from __future__ import annotations

AGENT_CATALOG: list[dict[str, object]] = [
  {
    "id": "reasoning-01",
    "name": "Логический аналитик",
    "category": "reasoning",
    "category_name": "Интеллект и анализ",
    "description": "Разбирает аргументы, выявляет логические ошибки и противоречия.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "reasoning-02",
    "name": "Критический мыслитель",
    "category": "reasoning",
    "category_name": "Интеллект и анализ",
    "description": "Проверяет предположения, слабые места и альтернативные объяснения.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "reasoning-03",
    "name": "Системный аналитик",
    "category": "reasoning",
    "category_name": "Интеллект и анализ",
    "description": "Рассматривает сложные задачи как взаимосвязанные системы.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "reasoning-04",
    "name": "Стратег решений",
    "category": "reasoning",
    "category_name": "Интеллект и анализ",
    "description": "Сравнивает варианты и строит обоснованные планы действий.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "reasoning-05",
    "name": "Решатель задач",
    "category": "reasoning",
    "category_name": "Интеллект и анализ",
    "description": "Декомпозирует сложные задачи и последовательно ищет решение.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "reasoning-06",
    "name": "Аналитик рисков",
    "category": "reasoning",
    "category_name": "Интеллект и анализ",
    "description": "Выявляет риски, оценивает вероятность и последствия.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "reasoning-07",
    "name": "Эксперт по аргументации",
    "category": "reasoning",
    "category_name": "Интеллект и анализ",
    "description": "Строит доказательные позиции и проверяет силу аргументов.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "reasoning-08",
    "name": "Аналитик сценариев",
    "category": "reasoning",
    "category_name": "Интеллект и анализ",
    "description": "Моделирует вероятные сценарии и последствия решений.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "reasoning-09",
    "name": "Оптимизатор процессов",
    "category": "reasoning",
    "category_name": "Интеллект и анализ",
    "description": "Находит узкие места и способы повысить эффективность.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "reasoning-10",
    "name": "Синтезатор идей",
    "category": "reasoning",
    "category_name": "Интеллект и анализ",
    "description": "Объединяет разрозненные идеи в целостные концепции.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "coding-01",
    "name": "Python-разработчик",
    "category": "coding",
    "category_name": "Программирование",
    "description": "Пишет, анализирует и оптимизирует код на Python.",
    "execution_profile": "coding",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "coding-02",
    "name": "Frontend-разработчик",
    "category": "coding",
    "category_name": "Программирование",
    "description": "Создаёт интерфейсы на React, Next.js, HTML и CSS.",
    "execution_profile": "coding",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "coding-03",
    "name": "Backend-разработчик",
    "category": "coding",
    "category_name": "Программирование",
    "description": "Проектирует API, серверную логику и интеграции.",
    "execution_profile": "coding",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "coding-04",
    "name": "Full-stack-разработчик",
    "category": "coding",
    "category_name": "Программирование",
    "description": "Связывает frontend, backend и хранилища данных.",
    "execution_profile": "coding",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "coding-05",
    "name": "Инженер баз данных",
    "category": "coding",
    "category_name": "Программирование",
    "description": "Проектирует схемы, запросы, индексы и миграции.",
    "execution_profile": "coding",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "coding-06",
    "name": "DevOps-инженер",
    "category": "coding",
    "category_name": "Программирование",
    "description": "Работает с CI/CD, контейнерами, деплоем и инфраструктурой.",
    "execution_profile": "coding",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "coding-07",
    "name": "Тестировщик ПО",
    "category": "coding",
    "category_name": "Программирование",
    "description": "Создаёт тест-кейсы, автоматизацию и проверки регрессий.",
    "execution_profile": "coding",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "coding-08",
    "name": "Охотник за ошибками",
    "category": "coding",
    "category_name": "Программирование",
    "description": "Находит причины сбоев и предлагает точечные исправления.",
    "execution_profile": "coding",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "coding-09",
    "name": "Архитектор ПО",
    "category": "coding",
    "category_name": "Программирование",
    "description": "Проектирует структуру приложений и границы компонентов.",
    "execution_profile": "coding",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "coding-10",
    "name": "Инженер безопасности кода",
    "category": "coding",
    "category_name": "Программирование",
    "description": "Проверяет код на уязвимости и небезопасные практики.",
    "execution_profile": "coding",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "research-01",
    "name": "Веб-исследователь",
    "category": "research",
    "category_name": "Исследования и поиск",
    "description": "Ищет информацию в интернете и собирает подтверждённые источники.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "research-02",
    "name": "Проверяющий источники",
    "category": "research",
    "category_name": "Исследования и поиск",
    "description": "Оценивает надёжность, дату и происхождение источников.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "research-03",
    "name": "Аналитик рынка",
    "category": "research",
    "category_name": "Исследования и поиск",
    "description": "Изучает рынок, сегменты, спрос и конкурентную среду.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "research-04",
    "name": "Аналитик конкурентов",
    "category": "research",
    "category_name": "Исследования и поиск",
    "description": "Сравнивает продукты, позиционирование и публичные предложения.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "research-05",
    "name": "Сборщик данных",
    "category": "research",
    "category_name": "Исследования и поиск",
    "description": "Собирает и структурирует данные из разрешённых источников.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "research-06",
    "name": "Научный обозреватель",
    "category": "research",
    "category_name": "Исследования и поиск",
    "description": "Находит научные публикации и кратко разбирает результаты.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "research-07",
    "name": "Фактчекер",
    "category": "research",
    "category_name": "Исследования и поиск",
    "description": "Проверяет конкретные утверждения и отмечает неопределённость.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "research-08",
    "name": "Хронолог",
    "category": "research",
    "category_name": "Исследования и поиск",
    "description": "Восстанавливает последовательность событий и дат.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "research-09",
    "name": "Сравнительный аналитик",
    "category": "research",
    "category_name": "Исследования и поиск",
    "description": "Сопоставляет варианты по заданным критериям.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "research-10",
    "name": "Обзорщик литературы",
    "category": "research",
    "category_name": "Исследования и поиск",
    "description": "Сводит исследования и показывает совпадения и разногласия.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "business-01",
    "name": "Бизнес-стратег",
    "category": "business",
    "category_name": "Бизнес и управление",
    "description": "Формирует стратегию продукта, компании и выхода на рынок.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "business-02",
    "name": "Финансовый аналитик",
    "category": "business",
    "category_name": "Бизнес и управление",
    "description": "Считает бюджеты, себестоимость, маржинальность и сценарии.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "business-03",
    "name": "Маркетолог",
    "category": "business",
    "category_name": "Бизнес и управление",
    "description": "Разрабатывает маркетинговые гипотезы и кампании.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "business-04",
    "name": "Бренд-стратег",
    "category": "business",
    "category_name": "Бизнес и управление",
    "description": "Формирует позиционирование, ценности и архитектуру бренда.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "business-05",
    "name": "Продуктовый менеджер",
    "category": "business",
    "category_name": "Бизнес и управление",
    "description": "Приоритизирует функции, метрики и дорожную карту.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "business-06",
    "name": "Аналитик продаж",
    "category": "business",
    "category_name": "Бизнес и управление",
    "description": "Изучает воронку, конверсию и возможности роста.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "business-07",
    "name": "Операционный менеджер",
    "category": "business",
    "category_name": "Бизнес и управление",
    "description": "Оптимизирует ежедневные процессы и ресурсы.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "business-08",
    "name": "Предпринимательский консультант",
    "category": "business",
    "category_name": "Бизнес и управление",
    "description": "Проверяет бизнес-идеи и бизнес-модели.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "business-09",
    "name": "Специалист по ценообразованию",
    "category": "business",
    "category_name": "Бизнес и управление",
    "description": "Сравнивает тарифы, ценность и модели монетизации.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "business-10",
    "name": "Менеджер проектов",
    "category": "business",
    "category_name": "Бизнес и управление",
    "description": "Планирует этапы, сроки, зависимости и контроль исполнения.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "design-01",
    "name": "UI-дизайнер",
    "category": "design",
    "category_name": "Дизайн и визуальные коммуникации",
    "description": "Проектирует интерфейсы и состояния компонентов.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "design-02",
    "name": "UX-исследователь",
    "category": "design",
    "category_name": "Дизайн и визуальные коммуникации",
    "description": "Изучает пользовательские сценарии и точки затруднения.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "design-03",
    "name": "Дизайн-системный архитектор",
    "category": "design",
    "category_name": "Дизайн и визуальные коммуникации",
    "description": "Создаёт токены, компоненты и правила дизайн-системы.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "design-04",
    "name": "Графический дизайнер",
    "category": "design",
    "category_name": "Дизайн и визуальные коммуникации",
    "description": "Разрабатывает визуальные материалы и композиции.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "design-05",
    "name": "Бренд-дизайнер",
    "category": "design",
    "category_name": "Дизайн и визуальные коммуникации",
    "description": "Создаёт визуальную идентичность и правила бренда.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "design-06",
    "name": "Типограф",
    "category": "design",
    "category_name": "Дизайн и визуальные коммуникации",
    "description": "Подбирает шрифтовые пары, иерархию и читаемость.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "design-07",
    "name": "Специалист по доступности",
    "category": "design",
    "category_name": "Дизайн и визуальные коммуникации",
    "description": "Проверяет интерфейсы на доступность и удобство.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "design-08",
    "name": "Арт-директор",
    "category": "design",
    "category_name": "Дизайн и визуальные коммуникации",
    "description": "Определяет визуальное направление и согласованность материалов.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "design-09",
    "name": "Дизайнер презентаций",
    "category": "design",
    "category_name": "Дизайн и визуальные коммуникации",
    "description": "Строит структуру и визуальный язык презентаций.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "design-10",
    "name": "Мобильный UX-дизайнер",
    "category": "design",
    "category_name": "Дизайн и визуальные коммуникации",
    "description": "Проектирует мобильные интерфейсы и жестовые сценарии.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "content-01",
    "name": "Редактор",
    "category": "content",
    "category_name": "Тексты и коммуникации",
    "description": "Улучшает ясность, структуру и точность текстов.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "content-02",
    "name": "Копирайтер",
    "category": "content",
    "category_name": "Тексты и коммуникации",
    "description": "Пишет тексты для сайтов, продуктов и кампаний.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "content-03",
    "name": "Технический писатель",
    "category": "content",
    "category_name": "Тексты и коммуникации",
    "description": "Создаёт документацию, инструкции и руководства.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "content-04",
    "name": "Сценарист",
    "category": "content",
    "category_name": "Тексты и коммуникации",
    "description": "Разрабатывает сценарии видео, роликов и историй.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "content-05",
    "name": "Переводчик",
    "category": "content",
    "category_name": "Тексты и коммуникации",
    "description": "Переводит с сохранением смысла, стиля и терминологии.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "content-06",
    "name": "Литературный редактор",
    "category": "content",
    "category_name": "Тексты и коммуникации",
    "description": "Работает с ритмом, стилем и выразительностью текста.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "content-07",
    "name": "SMM-редактор",
    "category": "content",
    "category_name": "Тексты и коммуникации",
    "description": "Готовит контент-планы и публикации для социальных сетей.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "content-08",
    "name": "Специалист по SEO-контенту",
    "category": "content",
    "category_name": "Тексты и коммуникации",
    "description": "Структурирует материалы с учётом поискового намерения.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "content-09",
    "name": "Коммуникационный стратег",
    "category": "content",
    "category_name": "Тексты и коммуникации",
    "description": "Адаптирует сообщения под аудиторию и канал.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "content-10",
    "name": "Суммаризатор",
    "category": "content",
    "category_name": "Тексты и коммуникации",
    "description": "Сжимает длинные материалы без потери ключевых смыслов.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "science-01",
    "name": "Математик",
    "category": "science",
    "category_name": "Наука и математика",
    "description": "Решает математические задачи и проверяет выводы.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "science-02",
    "name": "Физик",
    "category": "science",
    "category_name": "Наука и математика",
    "description": "Разбирает физические модели, формулы и явления.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "science-03",
    "name": "Химик",
    "category": "science",
    "category_name": "Наука и математика",
    "description": "Объясняет химические процессы и свойства веществ.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "science-04",
    "name": "Биолог",
    "category": "science",
    "category_name": "Наука и математика",
    "description": "Анализирует биологические системы и научные данные.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "science-05",
    "name": "Статистик",
    "category": "science",
    "category_name": "Наука и математика",
    "description": "Выбирает методы анализа и интерпретирует результаты.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "science-06",
    "name": "Аналитик данных",
    "category": "science",
    "category_name": "Наука и математика",
    "description": "Очищает, исследует и визуализирует наборы данных.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "science-07",
    "name": "Специалист по машинному обучению",
    "category": "science",
    "category_name": "Наука и математика",
    "description": "Проектирует ML-подходы и оценивает модели.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "science-08",
    "name": "Исследователь ИИ",
    "category": "science",
    "category_name": "Наука и математика",
    "description": "Изучает архитектуры, методы и ограничения ИИ.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "science-09",
    "name": "Эколог",
    "category": "science",
    "category_name": "Наука и математика",
    "description": "Анализирует экологические процессы и воздействия.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "science-10",
    "name": "Научный методолог",
    "category": "science",
    "category_name": "Наука и математика",
    "description": "Помогает формулировать гипотезы и дизайн экспериментов.",
    "execution_profile": "research",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "education-01",
    "name": "Персональный репетитор",
    "category": "education",
    "category_name": "Обучение и языки",
    "description": "Объясняет темы с учётом уровня и темпа ученика.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "education-02",
    "name": "Тренер по математике",
    "category": "education",
    "category_name": "Обучение и языки",
    "description": "Даёт пошаговые решения и тренировочные задания.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "education-03",
    "name": "Тренер по программированию",
    "category": "education",
    "category_name": "Обучение и языки",
    "description": "Обучает программированию через практические задачи.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "education-04",
    "name": "Преподаватель английского",
    "category": "education",
    "category_name": "Обучение и языки",
    "description": "Помогает развивать грамматику, лексику и разговорную речь.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "education-05",
    "name": "Тренер по русскому языку",
    "category": "education",
    "category_name": "Обучение и языки",
    "description": "Объясняет грамматику, орфографию и пунктуацию.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "education-06",
    "name": "Подготовщик к ОГЭ",
    "category": "education",
    "category_name": "Обучение и языки",
    "description": "Формирует план и разбирает задания уровня ОГЭ.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "education-07",
    "name": "Подготовщик к ЕГЭ",
    "category": "education",
    "category_name": "Обучение и языки",
    "description": "Разбирает экзаменационные задания и критерии.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "education-08",
    "name": "Методист",
    "category": "education",
    "category_name": "Обучение и языки",
    "description": "Строит учебные программы и последовательность тем.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "education-09",
    "name": "Создатель тестов",
    "category": "education",
    "category_name": "Обучение и языки",
    "description": "Готовит контрольные вопросы и проверочные задания.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "education-10",
    "name": "Языковой практик",
    "category": "education",
    "category_name": "Обучение и языки",
    "description": "Проводит диалоги и корректирует языковые ошибки.",
    "execution_profile": "planning",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "engineering-01",
    "name": "Системный инженер",
    "category": "engineering",
    "category_name": "Инженерия и производство",
    "description": "Связывает требования, компоненты и технические ограничения.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "engineering-02",
    "name": "Электроинженер",
    "category": "engineering",
    "category_name": "Инженерия и производство",
    "description": "Разбирает электрические схемы и электронные системы.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "engineering-03",
    "name": "Механический инженер",
    "category": "engineering",
    "category_name": "Инженерия и производство",
    "description": "Анализирует механизмы, нагрузки и конструкции.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "engineering-04",
    "name": "Архитектор зданий",
    "category": "engineering",
    "category_name": "Инженерия и производство",
    "description": "Прорабатывает функциональные и пространственные решения.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "engineering-05",
    "name": "Инженер-конструктор",
    "category": "engineering",
    "category_name": "Инженерия и производство",
    "description": "Разрабатывает конструктивные решения и спецификации.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "engineering-06",
    "name": "Специалист CAD",
    "category": "engineering",
    "category_name": "Инженерия и производство",
    "description": "Помогает с параметрическим и техническим проектированием.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "engineering-07",
    "name": "Инженер материалов",
    "category": "engineering",
    "category_name": "Инженерия и производство",
    "description": "Сравнивает материалы и их эксплуатационные свойства.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "engineering-08",
    "name": "Инженер транспорта",
    "category": "engineering",
    "category_name": "Инженерия и производство",
    "description": "Анализирует транспортные системы и логистику.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "engineering-09",
    "name": "Инженер энергетики",
    "category": "engineering",
    "category_name": "Инженерия и производство",
    "description": "Изучает энергосистемы, нагрузки и эффективность.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "engineering-10",
    "name": "Инженер качества",
    "category": "engineering",
    "category_name": "Инженерия и производство",
    "description": "Формирует критерии приёмки и контрольные процедуры.",
    "execution_profile": "desktop",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "quality-01",
    "name": "Аудитор качества",
    "category": "quality",
    "category_name": "Контроль и безопасность",
    "description": "Проверяет полноту, точность и соответствие требованиям.",
    "execution_profile": "review",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "quality-02",
    "name": "Рецензент кода",
    "category": "quality",
    "category_name": "Контроль и безопасность",
    "description": "Проводит независимое ревью изменений и архитектуры.",
    "execution_profile": "review",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "quality-03",
    "name": "Аналитик приватности",
    "category": "quality",
    "category_name": "Контроль и безопасность",
    "description": "Ищет риски обработки и раскрытия персональных данных.",
    "execution_profile": "review",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "quality-04",
    "name": "Модель угроз",
    "category": "quality",
    "category_name": "Контроль и безопасность",
    "description": "Строит модель угроз и проверяет защитные меры.",
    "execution_profile": "review",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "quality-05",
    "name": "Проверяющий факты",
    "category": "quality",
    "category_name": "Контроль и безопасность",
    "description": "Отделяет подтверждённые сведения от предположений.",
    "execution_profile": "review",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "quality-06",
    "name": "Аналитик соответствия",
    "category": "quality",
    "category_name": "Контроль и безопасность",
    "description": "Сопоставляет решение с заданными правилами и требованиями.",
    "execution_profile": "review",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "quality-07",
    "name": "Тестировщик интерфейсов",
    "category": "quality",
    "category_name": "Контроль и безопасность",
    "description": "Проверяет сценарии, ошибки и доступность UI.",
    "execution_profile": "review",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "quality-08",
    "name": "Аналитик надёжности",
    "category": "quality",
    "category_name": "Контроль и безопасность",
    "description": "Ищет точки отказа и предлагает меры устойчивости.",
    "execution_profile": "review",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "quality-09",
    "name": "Контролёр безопасности инструментов",
    "category": "quality",
    "category_name": "Контроль и безопасность",
    "description": "Проверяет разрешения и потенциально опасные действия.",
    "execution_profile": "review",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  },
  {
    "id": "quality-10",
    "name": "Финальный рецензент",
    "category": "quality",
    "category_name": "Контроль и безопасность",
    "description": "Проводит итоговую проверку результата перед выдачей.",
    "execution_profile": "review",
    "status": "catalog",
    "capabilities": [
      "reasoning",
      "specialized_instructions"
    ]
  }
]

def list_agents() -> list[dict[str, object]]:
    """Return a copy so API consumers cannot mutate the global catalogue."""
    return [dict(agent) for agent in AGENT_CATALOG]

def get_agent(agent_id: str) -> dict[str, object] | None:
    """Find a role by stable ID."""
    return next((dict(agent) for agent in AGENT_CATALOG if agent["id"] == agent_id), None)
