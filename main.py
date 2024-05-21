import datetime
from datetime import datetime
from datetime import timedelta
import matplotlib
import matplotlib.dates as mdates
import pytz
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

matplotlib.use('Agg')
from matplotlib import pyplot as plt
import uuid
import os.path
from astral import LocationInfo
from astral.sun import sun
import logging

import config

TOKEN_API = config.bot_token

bot = Bot(TOKEN_API)
dp = Dispatcher(bot, storage=MemoryStorage())

logging.basicConfig(level=logging.INFO)

global line_temp_now, tempDate, tempValue


class AuthStates(StatesGroup):
    waiting_for_password = State()


#################################  FUNCTION  #################################

def logs(message):
    idHuman = message.from_user.id
    firstName = message.from_user.first_name
    operType = message.text

    connection = config.connectDB()

    if connection.is_connected():
        cursor = connection.cursor()
        my_sql_insert = "INSERT INTO logs (data, idHuman, name, operType) values (now(), %s, %s, %s)"
        cursor.execute(my_sql_insert, (idHuman, firstName, operType))
        connection.commit()

        cursor.close()
        connection.close()


def avgTemp(dataJ):
    connection = config.connectDB()

    if connection.is_connected():
        cursor = connection.cursor()
        my_sql_select = "select avg(tempValue) from Temperature t WHERE tempDate >= %s and tempDate < %s"
        cursor.execute(my_sql_select, (dataJ, dataJ + timedelta(hours=1)))
        line_avgTemp = cursor.fetchone()
        cursor.close()
        connection.close()
        return line_avgTemp[0]


#################################  CLIENT_HANDLER  #################################


@dp.message_handler(commands=['start'])
async def start_message(message: types.Message):
    logs(message)
    await message.answer("Цей бот показує температуру на вулиці.\n"
                         "Щоб побачити всі команди, напишіть /help\n"
                         "Більше інформації по команді /info\n")


@dp.message_handler(commands="buttons")
async def cmd_start(message: types.Message):
    kb = [
        [types.KeyboardButton(text="Середня температура за 12 годин ⏱"),
         types.KeyboardButton(text="Останні 10 змін температури 🗒"),
         types.KeyboardButton(text="Середня температура за останню годину ⏱")],
        [types.KeyboardButton(text="Графік температур 📈"),
         types.KeyboardButton(text="Поточна температура 🌡")]
    ]

    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    logs(message)
    await message.answer("Доступні кнопки", reply_markup=keyboard)


@dp.message_handler(commands=["info"])
async def info(message: types.Message):
    logs(message)
    await message.answer("Цей бот показує температуру на вулиці.\nВерсія бота 2.2.0\n"
                         "Щоб побачити всі команди, напишіть /help")


@dp.message_handler(commands=["help"])
async def info(message: types.Message):
    logs(message)
    await message.answer("Доступні команди: "
                         "\n/buttons - Активувати кнопки"
                         "\n/temp_now - Показати поточну температуру 🌡"
                         "\n/last_ten_changes - Останні 10 змін температури 🗒"
                         "\n/avg_last_hour - Середня температура за останню годину ⏱"
                         "\n/avg_for_12_hours - Середня температура за 12 годин ⏱"
                         "\n/show_graf - Графік температур за день ☀"
                         "\n/about_update - Інформація про останнє оновлення 🔄")


@dp.message_handler(commands=['temp_now'])
async def temp_now(message: types.Message):
    global line_temp_now, tempDate, tempValue
    connection = config.connectDB()
    if connection.is_connected():
        cursor = connection.cursor()
        cursor.execute('SELECT * from Temperature t order by tempDate desc limit 1')

        line_temp_now = ""

        for (tempDate, tempValue) in cursor:
            line_temp_now = line_temp_now + "\n" + str(tempDate) + "\n" + str(tempValue)

        current_time = datetime.now()
        time_diff = current_time - tempDate

        if time_diff >= timedelta(minutes=15):
            line_temp_now += "\n Увага! Час відрізняється від теперішнього, температура може бути некоректною "

        cursor.close()
        connection.close()

    logs(message)
    await message.answer(line_temp_now)


@dp.message_handler(commands=['avg_for_12_hours'])
async def avg_for_12_hours(message: types.Message):
    dt_old = datetime.now()
    dt_new = datetime(dt_old.year, dt_old.month, dt_old.day, dt_old.hour)
    line_12_hours = ""

    for i in range(1, 13):
        print(i)
        j = dt_new - timedelta(hours=i)
        avg = avgTemp(j)
        if avg is None:
            avgout = "---"
        else:
            avgout = '{0:.1f}'.format(avg)
        line_12_hours = line_12_hours + "\n" + str(j) + "   " + avgout

    logs(message)
    await message.answer(str(line_12_hours))


@dp.message_handler(commands=['last_ten_changes'])
async def last_ten_changes(message: types.Message):
    connection = config.connectDB()
    if connection.is_connected():
        cursor = connection.cursor()
        cursor.execute('SELECT * from Temperature t order by tempDate desc limit 10')

        line_ten_changes = ""

        for (tempDate, tempValue) in cursor:
            line_ten_changes = line_ten_changes + "\n" + str(tempDate) + "   " + str(tempValue)

        cursor.close()
        connection.close()

        logs(message)
        await message.answer(str(line_ten_changes))


@dp.message_handler(commands=['avg_last_hour'])
async def avg_last_hour(message: types.Message):
    connection = config.connectDB()

    if connection.is_connected():
        cursor = connection.cursor()
        cursor.execute('select avg(tempValue) from Temperature t WHERE tempDate >= DATE_SUB(NOW(), INTERVAL 1 HOUR)')
        line_last_hour = cursor.fetchone()[0]
        cursor.close()
        connection.close()

        logs(message)
        await message.answer("Середня температура за останню годину ⏱\n" + str(round(line_last_hour, 1)))


@dp.message_handler(commands=['show_graf'])
async def show_graf(message: types.Message):
    connection = config.connectDB()

    logs(message)
    if connection.is_connected():
        cursor = connection.cursor()
        cursor.execute(
            'SELECT CAST(Time(tempDate) as DATETIME), tempValue from Temperature t WHERE tempDate >= DATE(DATE_SUB(NOW(),INTERVAL 1 DAY)) AND tempDate < DATE(NOW()) order by tempDate asc')

        x_1 = []
        y_1 = []
        x_2 = []
        y_2 = []
        x_3 = []
        y_3 = []

        city = LocationInfo(name="Krop", region="Ukraine", timezone="Europe/Kyiv", latitude=48.513199,
                            longitude=32.259701)

        s = sun(city.observer, tzinfo=pytz.timezone(city.timezone))

        sunRise = s["sunrise"]
        sunSet = s["sunset"]

        for (tempDate, tempValue) in cursor:
            x_1.append(tempDate)
            y_1.append(tempValue)

        cursor.execute(
            'SELECT CAST(Time(tempDate) as DATETIME), tempValue from Temperature t WHERE DATE(tempDate) = CURDATE() order by tempDate asc')

        for (tempDate, tempValue) in cursor:
            x_2.append(tempDate)
            y_2.append(tempValue)

        cursor.execute(
            'SELECT CAST(Time(tempDate) as DATETIME), tempValue from Temperature t WHERE tempDate >= DATE(DATE_SUB(NOW(),INTERVAL 2 DAY)) AND tempDate < DATE(DATE_SUB(NOW(),INTERVAL 1 DAY )) order by tempDate asc')

        for (tempDate, tempValue) in cursor:
            x_3.append(tempDate)
            y_3.append(tempValue)

        fig, ax = plt.subplots()
        plt.xticks(rotation=70)

        hours = mdates.DateFormatter('%H:%M')
        ax.xaxis.set_major_formatter(hours)
        ax.set_ylabel('°C')
        ax.plot(x_3, y_3, 'gray', x_1, y_1, x_2, y_2, 'r', linewidth=1)
        dt_now = datetime.now()
        ax.axvline(datetime(dt_now.year, dt_now.month, dt_now.day, sunRise.hour, sunRise.minute), color='#F7D005')
        ax.axvline(datetime(dt_now.year, dt_now.month, dt_now.day, sunSet.hour, sunSet.minute), color='#F7D005')
        ax.legend(['Позавчорашня', 'Вчорашня', 'Сьогоднішня', '☀ Схід/Захід'])
        plt.grid()
        strFile = 'YYY' + str(uuid.uuid1()) + '.png'
        if os.path.isfile(strFile):
            os.remove(strFile)
        plt.savefig(strFile)
        plt.close()
        img = open(strFile, 'rb')
        await message.answer_photo(img)
        img.close()
        if os.path.isfile(strFile):
            os.remove(strFile)

        cursor.close()
        connection.close()


@dp.message_handler(commands=['about_update'])
async def about_update(message: types.Message):
    logs(message)
    await message.answer("Оновлення 2.2.1"
                         "\n• Додано повідомлення про попередження неправильної дати")


#################################  ADMIN_HANDLER  #################################


@dp.message_handler(Command("login_admin"), state="*")
async def login_admin(message: types.Message):
    logs(message)
    await message.answer("Введіть пароль:")
    await AuthStates.waiting_for_password.set()


@dp.message_handler(state=AuthStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text
    connection = config.connectDB()

    if password == config.admin_password:
        if connection.is_connected():
            name_admin = message.from_user.first_name
            id_admin = message.from_user.id

            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM admins")
            row_count = cursor.fetchone()[0]

            if row_count == 0:
                cursor.execute("INSERT INTO admins (id_admins, name_admins) VALUES (%s, %s)", (id_admin, name_admin))
            else:
                cursor.execute("INSERT INTO admins (id_admins, name_admins) \
                                SELECT * FROM (SELECT %s, %s) AS tmp \
                                WHERE NOT EXISTS (SELECT id_admins FROM admins WHERE id_admins = %s) \
                                LIMIT 1;", (id_admin, name_admin, id_admin))

                await state.finish()
                await message.answer("Ви вже зареєстровані як адміністратор")

            connection.commit()
            cursor.close()
            connection.close()
    else:
        await state.finish()
        await message.answer("Невірний пароль!")


@dp.message_handler(commands=['show_count_users'])
async def show_count_users(message: types.Message):
    connection = config.connectDB()

    if connection.is_connected():
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM admins WHERE id_admins = %s", (message.from_user.id,))
        is_admin = cursor.fetchone()

        if is_admin:
            logs(message)

            cursor.execute("SELECT COUNT(DISTINCT name) FROM logs")
            count_users = cursor.fetchone()[0]

            button = InlineKeyboardButton("Список користувачів", callback_data="list_users")

            keyboard = InlineKeyboardMarkup()
            keyboard.add(button)

            await message.answer("Кількість користувачів: " + str(count_users), reply_markup=keyboard)
        else:
            await message.answer("Ви не маєте доступу до цієї інформації.")
            connection.close()


@dp.callback_query_handler(lambda c: c.data == 'list_users')
async def list_users(query: types.CallbackQuery):
    connection = config.connectDB()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT name FROM logs")
        users = cursor.fetchall()
        user_str = '\n'.join(f"{i}. {user[0]}" for i, user in enumerate(users, start=1))

        if user_str:
            await query.message.answer(user_str)
        else:
            await query.message.answer("Список користувачів порожній.")
    except Exception as e:
        await query.message.answer("Виникла помилка під час виконання запиту.")
        print(e)
    finally:
        connection.close()


@dp.message_handler(commands=['last_entry_of_all_users'])
async def last_entry_of_all_users(message: types.Message):
    connection = config.connectDB()

    if connection.is_connected():
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM admins WHERE id_admins = %s", (message.from_user.id,))
        is_admin = cursor.fetchone()

        if is_admin:
            cursor.execute("SELECT data, name, operType FROM \
            (SELECT data, idHuman, operType, name, ROW_NUMBER() \
            OVER (PARTITION BY idHuman ORDER BY data DESC) as row_num FROM logs) t \
            WHERE row_num = 1 ORDER BY data DESC;")

            last_logs_str = ""

            for (data, name, operType) in cursor:
                last_logs_str = last_logs_str + str(data) + " | " + name + " | " + operType + "\n"

            logs(message)
            await message.answer(last_logs_str)
        else:
            await message.answer("Ви не маєте доступу до цієї інформації.")
            connection.close()


@dp.message_handler(commands=['admin'])
async def admin(message: types.Message):
    connection = config.connectDB()

    if connection.is_connected():
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM admins WHERE id_admins = %s", (message.from_user.id,))
        is_admin = cursor.fetchone()

        if is_admin:
            logs(message)
            await message.answer("Доступні команди адміністратора: \n"
                                 "/show_count_users - Показати кількість користувачів\n"
                                 "/last_entry_of_all_users - Показати останню дію всіх користувачів\n")

        else:
            await message.answer("Ви не маєте доступу до цієї інформації.")
            connection.close()


#################################  OTHER_HANDLER  #################################


@dp.errors_handler(exception=Exception)
async def error_handler(update: types.Update, exception: Exception):
    logging.exception(exception)
    await update.message.reply("Виникла помилка при обробці вашого запиту!")


@dp.message_handler(content_types="text")
async def text(message: types.Message):
    if message.text == "Поточна температура 🌡":
        await temp_now(message)
    elif message.text == "Останні 10 змін температури 🗒":
        await last_ten_changes(message)
    elif message.text == "Середня температура за останню годину ⏱":
        await avg_last_hour(message)
    elif message.text == "Середня температура за 12 годин ⏱":
        await avg_for_12_hours(message)
    elif message.text == "Графік температур 📈":
        await show_graf(message)
    else:
        await info(message)


if __name__ == '__main__':
    print("start MyTempBot")
    executor.start_polling(dp, skip_updates=True)
