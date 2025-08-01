import os
import json
import telebot
from mistralai import Mistral

# --- Настройка ---
MISTRAL_API_KEY = "2bhEWXz5xHeZjCDhylAdbxHyH7t3OvZx"  # Замените на свой ключ
TELEGRAM_BOT_TOKEN = "8224846913:AAE9eJcggdofjH2s4BSQ-GczlubgBJA1uKE"  # Замените на свой токен

# Инициализация бота и клиента Mistral
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = Mistral(api_key=MISTRAL_API_KEY)

# ID вашего агента с включенным image_generation
AGENT_ID = "ag_019864490ff6739d8d51d770fc593fe9" # Замените на реальный ID

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Отправь мне текст, и я постараюсь создать пост с текстом и изображением.")

@bot.message_handler(func=lambda message: True)
def handle_post_request(message):
    """
    1. Пытается сгенерировать изображение с помощью Agents API.
    2. Генерирует текст с помощью стандартного chat.complete API.
    3. Отправляет пользователю пост с текстом и (если доступно) изображением.
    """
    user_text = message.text
    chat_id = message.chat.id

    # Переменная для хранения file_id изображения
    image_file_id = None

    # --- Шаг 1: Попытка сгенерировать изображение через Agents API ---
    try:
        # Запускаем агент с запросом, который побуждает его сгенерировать изображение
        agent_response = client.beta.conversations.start(
            agent_id=AGENT_ID,
            inputs=f"Создай визуальное изображение для поста на тему: '{user_text}'."
        )

        # Ищем ответ от ассистента
        assistant_output = None
        for output in agent_response.outputs:
            if output.type == "message.output" and output.role == "assistant":
                assistant_output = output
                break

        # Если нашли ответ, ищем в нем сгенерированное изображение
        if assistant_output:
            for chunk in assistant_output.content:
                if hasattr(chunk, 'type') and chunk.type == "tool_file" and chunk.tool == "image_generation":
                    image_file_id = chunk.file_id
                    print(f"Изображение успешно сгенерировано. File ID: {image_file_id}")
                    break # Нашли изображение, выходим из цикла

    except Exception as e:
        # Ловим любую ошибку (429, таймаут и т.д.) и просто продолжаем без изображения
        print(f"Ошибка при генерации изображения: {e}")
        image_file_id = None # Убедимся, что переменная сброшена

    # --- Шаг 2: Генерация текста с помощью стандартного API ---
    # Этот шаг выполняется ВСЕГДА, независимо от результата шага 1.
    try:
        # Используем chat.complete для генерации текста с хорошим форматированием
        text_response = client.chat.complete(
            model="mistral-medium-latest",
            messages=[
                {"role": "system",
                 "content": "Ты - опытный копирайтер для социальных сетей. Твоя задача — создать КОРОТКИЙ и ёмкий пост, который занимает НЕ БОЛЕЕ 900 СИМВОЛОВ (чтобы уместиться в подпись к изображению в Telegram). "
                            "Используй эмодзи, абзацы и хештеги. Форматируй текст красиво и естественно. "
                            "Не используй markdown. Не пиши вводные фразы вроде 'Вот ваш пост:' или 'Предлагаю вашему вниманию:'. "
                            "Начни сразу с основного содержания. Будь кратким и по делу."},  # Усиленный промпт
                {"role": "user", "content": user_text}
            ],
            max_tokens=256  # Ключевой параметр: ограничиваем длину ответа модели
        )
        final_text = text_response.choices[0].message.content

    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка при генерации текста: {str(e)}")
        return # Прерываем выполнение, если не удалось сгенерировать текст

    # --- Шаг 3: Формирование и отправка поста ---
    if image_file_id and final_text.strip():
        try:
            # Скачиваем изображение
            file_bytes = client.files.download(file_id=image_file_id).read()

            # Проверка длины текста
            if len(final_text.strip()) > 1000:
                # Если текст длинный, разделяем отправку
                bot.send_photo(chat_id, file_bytes, caption="")
                bot.send_message(chat_id, final_text.strip())
            else:
                # Если текст короткий, можно отправить его как подпись
                bot.send_photo(chat_id, file_bytes, caption=final_text.strip())
        except Exception as e:
            print(f"Ошибка при отправке изображения: {e}")
            # Если все еще есть проблемы с изображением, отправляем только текст
            bot.reply_to(message, final_text.strip())
    elif final_text.strip():
        # Если изображения нет, отправляем только текст
        bot.reply_to(message, final_text.strip())
    else:
        bot.reply_to(message, "Не удалось сгенерировать пост.")

# --- Запуск бота ---
if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)