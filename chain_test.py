"""
Тестовый скрипт: связывает две нейросети между собой.

Claude придумывает короткую идею -> её результат передаётся в GPT,
который эту идею развивает дальше.

Перед запуском:
1. Скопируйте .env.example в .env и впишите свои реальные ключи API.
2. Активируйте виртуальное окружение: source venv/bin/activate
3. Запустите: python chain_test.py
"""

import os
from dotenv import load_dotenv
from anthropic import Anthropic
from openai import OpenAI

load_dotenv()  # подхватывает ключи из файла .env

anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Шаг 1: спрашиваем у Claude короткую идею
claude_response = anthropic_client.messages.create(
    model="claude-sonnet-5",
    max_tokens=200,
    messages=[
        {"role": "user", "content": "Придумай одну короткую (1-2 предложения) идею для мобильного приложения."}
    ],
)
idea = claude_response.content[0].text
print("=== Идея от Claude ===")
print(idea)

# Шаг 2: передаём идею от Claude в GPT, чтобы он её развил
gpt_response = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": f"Вот идея для приложения:\n\n{idea}\n\nПредложи 3 ключевые фичи для неё."}
    ],
)
features = gpt_response.choices[0].message.content
print("\n=== Развитие идеи от GPT ===")
print(features)
