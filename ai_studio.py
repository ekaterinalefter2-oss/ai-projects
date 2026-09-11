"""
AI Studio — единое окно поверх Claude / GPT / Gemini.

Идея: ты пишешь задачу и выбираешь режим, система сама решает,
какие модели подключить, и показывает один финальный результат,
а внизу — какие модели участвовали и примерная стоимость запроса.

ai_team.py (терминальная версия-цепочка) не трогаем — это контрольный
рабочий вариант. Это отдельный, новый файл.

Запуск:
    source venv/bin/activate
    streamlit run ai_studio.py
"""

import os
import time
import streamlit as st
from dotenv import load_dotenv
from anthropic import Anthropic
from openai import OpenAI
from google import genai

load_dotenv(".env")

st.set_page_config(page_title="AI Studio", page_icon="🧠", layout="centered")


def get_secret(name):
    """Берёт значение сначала из Streamlit Secrets (облако), потом из .env (локально)."""
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name)


# ---------------------------------------------------------------------------
# Простой пароль на вход — задаётся секретом APP_PASSWORD
# (локально: в .env, в облаке: в Secrets на share.streamlit.io)
# ---------------------------------------------------------------------------

def check_password():
    def password_entered():
        if st.session_state.get("password_input") == get_secret("APP_PASSWORD"):
            st.session_state["authenticated"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["authenticated"] = False

    if st.session_state.get("authenticated"):
        return True

    st.text_input("Пароль", type="password", on_change=password_entered, key="password_input")
    if st.session_state.get("authenticated") is False:
        st.error("Неверный пароль")
    return False


if not get_secret("APP_PASSWORD"):
    st.warning(
        "APP_PASSWORD не задан — вход открыт для всех, у кого есть ссылка. "
        "Добавьте APP_PASSWORD в .env (локально) или в Secrets (в облаке)."
    )
elif not check_password():
    st.stop()

# ---------------------------------------------------------------------------
# Клиенты
# ---------------------------------------------------------------------------

anthropic_client = Anthropic(api_key=get_secret("ANTHROPIC_API_KEY"), timeout=120.0)
openai_client = OpenAI(api_key=get_secret("OPENAI_API_KEY"))
gemini_client = genai.Client(api_key=get_secret("GEMINI_API_KEY"))

CLAUDE_MODEL = "claude-sonnet-4-5"       # как в ai_team.py — проверенно рабочий
CLAUDE_FAST_MODEL = "claude-haiku-4-5-20251001"  # для режима "Быстро"
GPT_MODEL = "gpt-5.6"
GEMINI_MODEL = "gemini-3.6-flash"

# ---------------------------------------------------------------------------
# ПРИМЕРНЫЕ цены за 1 млн токенов (USD). Это ОЦЕНКА для ориентира, не точный
# биллинг — реальные цены смотрите на сайтах провайдеров и обновляйте здесь.
# ---------------------------------------------------------------------------
PRICING = {
    "claude": {"in": 3.0, "out": 15.0},
    "claude_fast": {"in": 1.0, "out": 5.0},
    "gpt": {"in": 0.5, "out": 1.5},
    "gemini": {"in": 0.1, "out": 0.4},
}


def estimate_cost(in_tokens, out_tokens, rates):
    return (in_tokens / 1_000_000) * rates["in"] + (out_tokens / 1_000_000) * rates["out"]


def get_anthropic_usage(resp):
    try:
        return resp.usage.input_tokens, resp.usage.output_tokens
    except Exception:
        return 0, 0


def get_openai_usage(resp):
    try:
        u = resp.usage
        in_tok = getattr(u, "input_tokens", None) or getattr(u, "prompt_tokens", 0)
        out_tok = getattr(u, "output_tokens", None) or getattr(u, "completion_tokens", 0)
        return in_tok, out_tok
    except Exception:
        return 0, 0


def get_gemini_usage(resp):
    try:
        u = resp.usage_metadata
        return u.prompt_token_count, u.candidates_token_count
    except Exception:
        return 0, 0


# ---------------------------------------------------------------------------
# Вызовы моделей
# ---------------------------------------------------------------------------

def call_claude(prompt, model=CLAUDE_MODEL, max_tokens=800):
    resp = anthropic_client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text
    in_tok, out_tok = get_anthropic_usage(resp)
    return text, in_tok, out_tok


def call_gpt(prompt, model=GPT_MODEL):
    resp = openai_client.responses.create(model=model, input=prompt)
    text = resp.output_text
    in_tok, out_tok = get_openai_usage(resp)
    return text, in_tok, out_tok


def call_gemini(prompt, model=GEMINI_MODEL):
    resp = gemini_client.models.generate_content(model=model, contents=prompt)
    text = resp.text
    in_tok, out_tok = get_gemini_usage(resp)
    return text, in_tok, out_tok


# ---------------------------------------------------------------------------
# Режимы работы. Каждый возвращает (финальный_текст, использованные_модели,
# итоговая_примерная_стоимость, разбивка_по_моделям)
# ---------------------------------------------------------------------------

def mode_quick(task):
    text, in_tok, out_tok = call_claude(task, model=CLAUDE_FAST_MODEL, max_tokens=600)
    cost = estimate_cost(in_tok, out_tok, PRICING["claude_fast"])
    return text, ["Claude (быстрая модель)"], cost, {"Claude": cost}


def mode_deep(task):
    breakdown = {}

    claude_text, c_in, c_out = call_claude(
        f"Ты генератор сильных идей и концепций.\n"
        f"Разбери задачу пользователя и предложи сильное решение.\n\nЗадача:\n{task}"
    )
    breakdown["Claude"] = estimate_cost(c_in, c_out, PRICING["claude"])

    gpt_text, g_in, g_out = call_gpt(
        f"Ты продуктовый стратег и редактор.\n"
        f"Возьми идею Claude ниже, усиль её, убери слабые места, "
        f"добавь структуру, практические шаги и конкретику.\n\n"
        f"Исходная задача:\n{task}\n\nОтвет Claude:\n{claude_text}"
    )
    breakdown["GPT"] = estimate_cost(g_in, g_out, PRICING["gpt"])

    gemini_text, m_in, m_out = call_gemini(
        f"Ты независимый критик и финальный редактор.\n\n"
        f"Исходная задача:\n{task}\n\nОтвет Claude:\n{claude_text}\n\nОтвет GPT:\n{gpt_text}\n\n"
        f"Найди слабые места, противоречия и лишнее. "
        f"После критики дай финальную улучшенную версию решения."
    )
    breakdown["Gemini"] = estimate_cost(m_in, m_out, PRICING["gemini"])

    total = sum(breakdown.values())
    return gemini_text, ["Claude", "GPT", "Gemini"], total, breakdown


def mode_product(task):
    breakdown = {}

    claude_text, c_in, c_out = call_claude(
        f"Ты продуктовый визионер. Предложи концепцию продукта и позиционирование "
        f"для следующей задачи:\n\n{task}"
    )
    breakdown["Claude"] = estimate_cost(c_in, c_out, PRICING["claude"])

    gpt_text, g_in, g_out = call_gpt(
        f"Ты продуктовый менеджер. На основе концепции ниже составь структурированную "
        f"спецификацию продукта: целевой пользователь, ключевые фичи, объём MVP, "
        f"дорожная карта на первые 3 шага.\n\nЗадача:\n{task}\n\nКонцепция от Claude:\n{claude_text}"
    )
    breakdown["GPT"] = estimate_cost(g_in, g_out, PRICING["gpt"])

    gemini_text, m_in, m_out = call_gemini(
        f"Ты независимый критик-инвестор. Проверь спецификацию продукта ниже на слабые места, "
        f"нереалистичные допущения и риски. Дай финальную улучшенную версию спецификации.\n\n"
        f"Задача:\n{task}\n\nСпецификация:\n{gpt_text}"
    )
    breakdown["Gemini"] = estimate_cost(m_in, m_out, PRICING["gemini"])

    total = sum(breakdown.values())
    return gemini_text, ["Claude", "GPT", "Gemini"], total, breakdown


def mode_content(task):
    breakdown = {}

    claude_text, c_in, c_out = call_claude(
        f"Ты хороший копирайтер. Напиши черновик текста по задаче ниже.\n\nЗадача:\n{task}"
    )
    breakdown["Claude"] = estimate_cost(c_in, c_out, PRICING["claude"])

    gpt_text, g_in, g_out = call_gpt(
        f"Ты редактор. Отполируй текст ниже: улучши стиль, убери канцелярит и повторы, "
        f"сохрани смысл.\n\nЗадача:\n{task}\n\nЧерновик:\n{claude_text}"
    )
    breakdown["GPT"] = estimate_cost(g_in, g_out, PRICING["gpt"])

    total = sum(breakdown.values())
    return gpt_text, ["Claude", "GPT"], total, breakdown


MODES = {
    "⚡ Быстро": mode_quick,
    "🔍 Глубокий анализ": mode_deep,
    "🚀 Создать продукт": mode_product,
    "✍️ Контент": mode_content,
}

# ---------------------------------------------------------------------------
# Интерфейс
# ---------------------------------------------------------------------------

st.title("🧠 AI Studio")
st.caption("Одно окно — Claude, GPT и Gemini работают вместе за кулисами")

task = st.text_area("Что нужно сделать?", height=120, placeholder="Опишите задачу...")
mode_label = st.radio("Режим", list(MODES.keys()), horizontal=True)

if st.button("Выполнить", type="primary", disabled=not task.strip()):
    with st.spinner(f"Работаю в режиме «{mode_label}»..."):
        start = time.time()
        try:
            result_text, models_used, total_cost, breakdown = MODES[mode_label](task)
        except Exception as e:
            st.error(f"Ошибка при обращении к модели: {e}")
            st.stop()
        elapsed = time.time() - start

    st.markdown("### Результат")
    st.write(result_text)

    st.divider()
    checks = "  ".join(f"{m} ✓" for m in models_used)
    st.markdown(f"**Модели:** {checks}")
    st.markdown(f"**Примерная стоимость запроса:** ≈ ${total_cost:.4f}  ·  время: {elapsed:.1f}с")
    with st.expander("Разбивка по моделям"):
        for name, cost in breakdown.items():
            st.write(f"{name}: ≈ ${cost:.4f}")
    st.caption("Стоимость — грубая оценка по примерным тарифам в коде (PRICING), не точный счёт провайдера.")
