import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from datetime import datetime, timedelta
import aiosqlite
import asyncio

bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher(bot, storage=MemoryStorage())
DB = "tasks.db"

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS tasks
                         (id INTEGER PRIMARY KEY, user_id INTEGER, text TEXT, date TEXT, done INTEGER)''')
        await db.commit()

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ Добавить задачу", callback_data="add"))
    kb.add(InlineKeyboardButton("📅 Сегодня", callback_data="today"))
    kb.add(InlineKeyboardButton("📊 Статистика", callback_data="stats"))
    kb.add(InlineKeyboardButton("🗑 Очистить всё", callback_data="clear"))
    return kb

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer(
        "🔥 Привет, ебарь времени!\n\nЯ твой личный планировщик, который не даёт тебе быть лузером.\n"
        "Жми кнопки ниже и пиздец твоей прокрастинации!",
        reply_markup=main_menu()
    )

@dp.callback_query_handler(lambda c: c.data == "add")
async def add_task(call: types.CallbackQuery):
    await call.message.answer("📝 Пиши задачу, которую надо заебать сегодня:")
    await call.answer()
    await dp.current_state(user=call.from_user.id).set_state("waiting_task")

@dp.message_handler(state="waiting_task")
async def save_task(message: types.Message, state):
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT INTO tasks (user_id, text, date, done) VALUES (?, ?, ?, 0)",
                        (message.from_user.id, message.text, today))
        await db.commit()
    await message.answer(f"✅ Задача добавлена!\n\n「{message.text}」", reply_markup=main_menu())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "today")
async def show_today(call: types.CallbackQuery):
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT id, text, done FROM tasks WHERE user_id=? AND date=?", 
                             (call.from_user.id, today)) as cursor:
            tasks = await cursor.fetchall()
    
    if not tasks:
        await call.message.answer("🎉 Сегодня пусто! Иди еби мир, а не диван!", reply_markup=main_menu())
        return

    text = f"📅 *Задачи на {datetime.now().strftime('%d.%m.%Y')}*\n\n"
    kb = InlineKeyboardMarkup(row_width=1)
    for task in tasks:
        status = "✅" if task[2] else "⬜"
        text += f"{status} {task[1]}\n"
        if not task[2]:
            kb.add(InlineKeyboardButton(f"{status} {task[1]}", callback_data=f"done_{task[0]}"))
    
    kb.add(InlineKeyboardButton("🔄 Обновить", callback_data="today"))
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith("done_"))
async def task_done(call: types.CallbackQuery):
    task_id = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE tasks SET done=1 WHERE id=?", (task_id,))
        await db.commit()
    await call.answer("✅ Засчитано, красавчик!")
    await show_today(call)

@dp.callback_query_handler(lambda c: c.data == "stats")
async def stats(call: types.CallbackQuery):
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT done FROM tasks WHERE user_id=? AND date>=?", 
                             (call.from_user.id, week_ago)) as cursor:
            all_tasks = await cursor.fetchall()
    
    total = len(all_tasks)
    done = sum(1 for t in all_tasks if t[0] == 1)
    percent = (done / total * 100) if total else 0
    
    await call.message.answer(
        f"📊 *Статистика за 7 дней*\n\n"
        f"Всего задач: {total}\n"
        f"Выполнено: {done} ({percent:.1f}%)\n\n"
        f"{'🔥 ТЫ БОГ' if percent >= 90 else '😐 Могло быть и лучше' if percent >= 50 else '😭 Иди работай, лентяй'}",
        reply_markup=main_menu(), parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data == "clear")
async def clear_today(call: types.CallbackQuery):
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE tasks SET date=? WHERE user_id=? AND date=? AND done=0", 
                        (tomorrow, call.from_user.id, today))
        await db.commit()
    await call.message.answer("🧹 День закрыт!\nНевыполненное улетело на завтра. Не расслабляйся!", reply_markup=main_menu())

async def main():
    await init_db()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
