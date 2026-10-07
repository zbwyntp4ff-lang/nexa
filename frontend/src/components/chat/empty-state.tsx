import { Bot, Code2, Compass, Eye, MessageCircle, Sparkles } from "lucide-react";
import { NexaOrb } from "@/components/common/nexa-orb";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { MODE_GRADIENT } from "@/lib/mode-theme";
import type { AppMode } from "@/lib/types";

const SUGGESTIONS_EN: Record<AppMode, string[]> = {
  chat: [
    "Explain how NEXA's Model Gateway works",
    "Summarize the tradeoffs of REST vs. GraphQL",
    "Plan a multi-step agent workflow for a research brief",
    "Draft a clean TypeScript API client with retries",
  ],
  agent: [
    "Calculate 25 * 37 and save the result to a file",
    "List the files in my workspace, then tell me the current time",
    "Create a checklist and write it into notes.txt",
    "Organize a short research + summary agent run",
  ],
  code: [
    "Write a Python function that reverses a linked list",
    "Review this function for edge cases and suggest a fix",
    "Refactor this React component for clarity",
    "Add unit tests for a retry helper",
  ],
  research: [
    "What's the latest stable version of Python, with sources?",
    "Compare the top 3 vector databases right now",
    "Find recent papers on retrieval-augmented generation",
    "Summarize current LLM evaluation benchmarks",
  ],
  create: [
    "A minimalist logo for an AI assistant called NEXA",
    "A cozy reading nook, warm lighting, isometric illustration",
    "Abstract nebula wallpaper in violet and teal",
    "Product shot of a glass orb on dark glass",
  ],
  vision: [
    "Describe what's in this image",
    "Extract the text from this screenshot",
    "Identify UI issues in this mockup",
    "Summarize the chart in this photo",
  ],
};

const SUGGESTIONS_RU: Record<AppMode, string[]> = {
  chat: [
    "Объясни, как работает Model Gateway в NEXA",
    "Сравни REST и GraphQL — плюсы и минусы",
    "Спланируй агентский workflow для исследовательского брифа",
    "Набросай чистый TypeScript API-клиент с ретраями",
  ],
  agent: [
    "Посчитай 25 * 37 и сохрани результат в файл",
    "Покажи список файлов в рабочей папке и текущее время",
    "Создай чеклист и запиши его в notes.txt",
    "Собери короткий research + summary прогон агента",
  ],
  code: [
    "Напиши функцию на Python для разворота связного списка",
    "Проверь эту функцию на edge-кейсы и предложи исправление",
    "Отрефактори этот React-компонент для ясности",
    "Добавь unit-тесты для helper с retry",
  ],
  research: [
    "Какая последняя версия Python, со ссылками на источники?",
    "Сравни топ-3 векторные базы данных прямо сейчас",
    "Найди свежие статьи про retrieval-augmented generation",
    "Кратко опиши текущие бенчмарки оценки LLM",
  ],
  create: [
    "Минималистичный логотип для AI-ассистента NEXA",
    "Уютный уголок для чтения, тёплый свет, изометрия",
    "Абстрактная nebulа в фиолетовом и бирюзовом",
    "Предметный кадр стеклянного орба на тёмном стекле",
  ],
  vision: [
    "Опиши, что изображено на этой картинке",
    "Извлеки текст с этого скриншота",
    "Найди UI-проблемы в этом макете",
    "Суммируй график на этом фото",
  ],
};

const ICONS: Record<AppMode, typeof MessageCircle> = {
  chat: MessageCircle,
  agent: Bot,
  code: Code2,
  research: Compass,
  create: Sparkles,
  vision: Eye,
};

export function EmptyState({
  mode = "chat",
  onSuggestionClick,
}: {
  mode?: AppMode;
  onSuggestionClick: (text: string) => void;
}) {
  const t = useT();
  const isRu = t("sidebar.settings") === "Настройки";
  const suggestions = (isRu ? SUGGESTIONS_RU : SUGGESTIONS_EN)[mode];
  const Icon = ICONS[mode];
  return (
    <div key={mode} className="flex h-full flex-col items-center justify-center gap-7 px-6 py-10 text-center nexa-slide-up">
      {mode === "chat" ? (
        <NexaOrb className="size-32" />
      ) : (
        <div
          key={`icon-${mode}`}
          className={cn(
            "nexa-pop-in flex size-24 items-center justify-center rounded-full shadow-lg ring-1 ring-white/20",
            MODE_GRADIENT[mode]
          )}
        >
          <Icon className="size-10 text-white" aria-hidden="true" />
        </div>
      )}
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          {mode === "chat" ? t("chat.emptyTitle") : t(`mode.${mode}`)}
        </h1>
        <p className="text-sm font-medium text-muted-foreground">
          {mode === "chat" ? t("chat.emptyTagline") : t(`mode.${mode}.desc`)}
        </p>
      </div>
      <div className="grid w-full max-w-2xl grid-cols-1 gap-2.5 sm:grid-cols-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSuggestionClick(suggestion)}
            className="nexa-glass rounded-2xl px-4 py-3.5 text-left text-sm text-muted-foreground transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
