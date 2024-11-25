import asyncio
from binance.client import Client
import telebot
from datetime import datetime, timedelta

# Binance API ключи
api_key = '4DxOHs9FQU9SAUJLlHN397vnsUqBlt6BhLTWcKltX86mdhFbMDRVGxzFA8t9Moe4'
api_secret = '8FwRWGd7A0g176UAKjQEMVJkLMzfQLoiSDZqTBzpcEfxz8cvl4DNt1UhNV28ypmK'
client = Client(api_key, api_secret)

# Telegram Bot
bot = telebot.TeleBot('7423569961:AAG9vR0bfF-NSBcjQFgBf4JCpGw0h_YIkpI')
TELEGRAM_CHAT_ID = 6485631209  # Ваш Telegram ID


# Параметри
GROWTH_PERCENT_MIN = 4.0  # Мінімальний ріст/падіння в процентах (оновлено на 5%)
GROWTH_PERCENT_MAX = 100  # Максимальний ріст/падіння в процентах
TIME_INTERVAL = 30  # Інтервал між перевірками (в хвилинах) — оновлено на 30 хвилин
WAIT_TIME = 900  # Час очікування між перевірками для кожної пари (в секундах) — 30 хвилин

# Словник для зберігання кількості сигналів за останні 24 години
signals_count = {}


# Функція отримання всіх ф'ючерсних символів
async def get_all_futures_symbols():
    try:
        info = client.futures_exchange_info()  # Отримуємо інформацію про ф'ючерсні пари
        symbols = [symbol['symbol'] for symbol in info['symbols'] if
                   symbol['status'] == 'TRADING']  # Фільтруємо тільки ті, які торгуються
        return symbols
    except Exception as e:
        print(f"Помилка при отриманні ф'ючерсних пар: {e}")
        return []


# Функція отримання історичних даних за останні 30 хвилин
async def get_historical_price(symbol):
    try:
        klines = client.futures_klines(symbol=symbol, interval='1m',
                                       limit=31)  # Візьмемо 31 хвилину для аналізу (30 хвилин + поточна)
        price_30_minutes_ago = float(klines[-31][4])  # Ціна 30 хвилин тому
        current_price = float(klines[-1][4])  # Поточна ціна
        return current_price, price_30_minutes_ago
    except Exception as e:
        print(f"Помилка при отриманні історичних даних для {symbol}: {e}")
        return None, None


# Функція розрахунку зміни обсягу (інвестицій) за останні 30 хвилин
async def get_investment_change(symbol):
    try:
        klines = client.futures_klines(symbol=symbol, interval='1m', limit=31)
        if len(klines) < 31:
            print(f"Недостатньо даних для розрахунку обсягу для {symbol}")
            return None
        volume_30_minutes_ago = sum(float(kline[7]) for kline in klines[:30])  # Обсяг перших 30 хвилин
        current_volume = sum(float(kline[7]) for kline in klines[1:31])  # Обсяг останніх 30 хвилин
        investment_change_percent = ((current_volume - volume_30_minutes_ago) / volume_30_minutes_ago) * 100
        return investment_change_percent
    except Exception as e:
        print(f"Помилка при розрахунку обсягу для {symbol}: {e}")
        return None


# Функція надсилання повідомлень в Telegram
async def send_message(text):
    try:
        print("Надсилання повідомлення в Telegram...")
        bot.send_message(TELEGRAM_CHAT_ID, text, parse_mode="HTML")
        print("Повідомлення успішно надіслано!")
    except Exception as e:
        print(f"Помилка при надсиланні повідомлення: {e}")


# Функція сигналу з додаванням посилання на торгову пару
async def message_signal(symbol, current_price, price_30_minutes_ago, percent, investment_change, signal_count,
                         recommendation):
    direction = "🟢Ріст" if percent > 0 else "🔴Падіння"
    trading_link = f"https://www.binance.com/en/futures/{symbol}"  # Посилання на торгову пару
    message = f"""
    <b>🚨Сигнал для: {symbol}</b>
    <b>Ціна зараз:</b> <code>{current_price:.2f} USDT</code>
    <b>Ціна 30 хвилин тому:</b> <code>{price_30_minutes_ago:.2f} USDT</code>
    <b>{direction} за 30 хвилин:</b> <code>{abs(percent):.2f}%</code>
    <b>Зміна обсягу (інвестицій):</b> <code>{investment_change:.2f}%</code>
    <b>Рекомендація:</b> {recommendation}
    <i>Інтервал: {TIME_INTERVAL} хвилин</i>

    <b>Кількість сигналів за останні 24 години:</b> <u>{signal_count}</u>

    <b>🔗 Торговельна пара:</b> <a href="{trading_link}">Перейти до торгівлі</a>
    """
    print("Повідомлення сформовано, готове до надсилання:")
    print(message)
    await send_message(message)


# Оновлення кількості сигналів для монети
def update_signal_count(symbol):
    now = datetime.now()
    if symbol not in signals_count:
        signals_count[symbol] = []
    signals_count[symbol] = [timestamp for timestamp in signals_count[symbol] if now - timestamp < timedelta(days=1)]
    signals_count[symbol].append(now)
    return len(signals_count[symbol])


# Функція аналізу для прийняття рішення по покупці/продаже
def analyze_trade_signal(percent, investment_change):
    if percent > GROWTH_PERCENT_MAX and investment_change > 15:
        return "💥Рекомендується продати: сильний ріст та збільшення обсягу"
    elif percent < -GROWTH_PERCENT_MAX and investment_change > 15:
        return "💥Рекомендується купити: сильне падіння та збільшення обсягу"
    elif percent > GROWTH_PERCENT_MIN and percent <= GROWTH_PERCENT_MAX and investment_change > 5:
        return "⚠️Рекомендується почекати: помірний ріст та збільшення обсягу"
    elif percent < -GROWTH_PERCENT_MIN and percent >= -GROWTH_PERCENT_MAX and investment_change > 5:
        return "⚠️Рекомендується почекати: помірне падіння та збільшення обсягу"
    elif percent > 0 and investment_change < 0:
        return "⚠️Продаж: ріст ціни при зниженні обсягу, можливий тренд на падіння"
    elif percent < 0 and investment_change < 0:
        return "⚠️Покупка: падіння ціни при зниженні обсягу, можлива корекція"
    else:
        return "❓Немає чіткої рекомендації"


# Основна логіка перевірки пари
async def check_price(symbol):
    current_price, price_30_minutes_ago = await get_historical_price(symbol)
    investment_change = await get_investment_change(symbol)

    if current_price is None or price_30_minutes_ago is None or investment_change is None:
        return

    percent = ((current_price - price_30_minutes_ago) / price_30_minutes_ago) * 100

    if GROWTH_PERCENT_MIN <= abs(percent) <= GROWTH_PERCENT_MAX:
        signal_count = update_signal_count(symbol)
        recommendation = analyze_trade_signal(percent, investment_change)
        await message_signal(symbol, current_price, price_30_minutes_ago, percent, investment_change, signal_count,
                             recommendation)
    else:
        print(f"{symbol}: Зміна {percent:.2f}% поза діапазоном {GROWTH_PERCENT_MIN}% - {GROWTH_PERCENT_MAX}%")


# Перевірка всіх ф'ючерсних пар
async def check_all_symbols():
    symbols = await get_all_futures_symbols()
    print(f"Знайдено {len(symbols)} пар для перевірки.")
    tasks = []
    for symbol in symbols:
        tasks.append(check_price(symbol))
    await asyncio.gather(*tasks)


# Запуск програми
async def main():
    while True:
        await check_all_symbols()
        print(f"Очікування {TIME_INTERVAL} хвилин перед наступною перевіркою...")
        await asyncio.sleep(WAIT_TIME)  # Перевірка кожні 30 хвилин


if __name__ == "__main__":
    asyncio.run(main())
