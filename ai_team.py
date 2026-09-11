import os
from dotenv import load_dotenv
from anthropic import Anthropic
from openai import OpenAI
from google import genai

load_dotenv(".env")

anthropic_client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    timeout=120.0
)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

user_task = input("Введите задачу: ")

print("\n=== CLAUDE ===")
claude = anthropic_client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=800,
    messages=[
        {
            "role": "user",
            "content": f"""
Ты генератор сильных идей и концепций.
Разбери задачу пользователя и предложи сильное решение.

Задача:
{user_task}
"""
        }
    ]
)

claude_text = claude.content[0].text
print(claude_text)

print("\n=== GPT ===")
gpt = openai_client.responses.create(
    model="gpt-5.6",
    input=f"""
Ты продуктовый стратег и редактор.
Возьми идею Claude ниже, усили её, убери слабые места,
добавь структуру, практические шаги и конкретику.

Исходная задача:
{user_task}

Ответ Claude:
{claude_text}
"""
)

gpt_text = gpt.output_text
print(gpt_text)

print("\n=== GEMINI ===")
gemini = gemini_client.models.generate_content(
    model="gemini-3.6-flash",
    contents=f"""
Ты независимый критик и финальный редактор.

Исходная задача:
{user_task}

Ответ Claude:
{claude_text}

Ответ GPT:
{gpt_text}

Найди слабые места, противоречия и лишнее.
После критики дай финальную улучшенную версию решения.
"""
)

print(gemini.text)

print("\n=== ГОТОВО ===")
