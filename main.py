import os
import pandas as pd
from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
    CommandHandler,
    CallbackContext,
)

# Telegram bot token
telegram_token = "8325336162:AAGBsi3GpmXX6PlZH-Y8m1vdR4yPmviPbBA"  # Replace with your actual Telegram bot token

# Base path for university folders
BASE_PATH = r"D:\Butana_University_Students_Assistant_Bot\Butana_University_Students_Assistant_Bot\Butana_University"

# Load student results data
data = pd.read_excel("students_results.xlsx", sheet_name="Sheet1")

# User states dictionary to handle multiple users
user_states = {}


def get_user_state(user_id):
    """Get or create user state"""
    if user_id not in user_states:
        user_states[user_id] = {
            "path_stack": [],  # Stack to track the navigation path (actual folder names)
            "display_stack": [],  # Stack for display names (without numbers)
            "last_message_id": None,
            "awaiting_results": False,
            "result_context": None,  # Store context for result queries (semester, field, etc.)
        }
    return user_states[user_id]


def clean_display_name(name):
    """
    Remove leading numbers and dots from folder/file names for display.
    Examples: '01. Programming' -> 'Programming', '02.Data Structures' -> 'Data Structures'
    """
    import re

    # Remove pattern like "01. " or "02." or "1. " from the start
    cleaned = re.sub(r"^\d+\.\s*", "", name)
    return cleaned.strip()


def get_folders_and_files(path):
    """
    Get all folders and files in the given path.
    Returns: (folders_dict, files_dict) where keys are display names and values are actual names
    """
    if not os.path.exists(path):
        return {}, {}

    try:
        items = os.listdir(path)
        folders = {}
        files = {}

        for item in sorted(items):
            item_path = os.path.join(path, item)
            display_name = clean_display_name(item)

            if os.path.isdir(item_path):
                folders[display_name] = item
            else:
                files[display_name] = item

        return folders, files
    except Exception as e:
        print(f"Error reading directory {path}: {e}")
        return {}, {}


# def create_keyboard(items, add_back_button=False):
#     """
#     Create a keyboard markup from a list of items.
#     Arranges buttons in rows of 2.
#     """
#     if not items:
#         return ReplyKeyboardRemove()

#     buttons = []

#     # Add items in rows of 2
#     for i in range(0, len(items), 2):
#         row = [KeyboardButton(items[i])]
#         if i + 1 < len(items):
#             row.append(KeyboardButton(items[i + 1]))
#         buttons.append(row)

#     # Add back button if needed
#     if add_back_button:
#         buttons.append(
#             [KeyboardButton("🔙 رجوع"), KeyboardButton("🔝 القائمة الرئيسية")]
#         )

#     return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def create_keyboard(items, add_back_button=False):
    """
    Create a keyboard markup from a list of items.
    Each button on its own line.
    """
    if not items:
        return ReplyKeyboardRemove()

    buttons = []

    # Add each item as a separate row
    for item in items:
        buttons.append([KeyboardButton(item)])

    # Add back button if needed
    if add_back_button:
        buttons.append(
            [KeyboardButton("🔙 رجوع"), KeyboardButton("🔝 القائمة الرئيسية")]
        )

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


async def delete_last_message(context: CallbackContext, chat_id: int, message_id: int):
    """Delete a specific message"""
    if message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            print(f"Could not delete message: {e}")


async def send_file(update: Update, context: CallbackContext, file_path: str):
    """Send a file to the user"""
    try:
        with open(file_path, "rb") as file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=file,
                caption=f"📄 {os.path.basename(file_path)}",
            )
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ عذراً، حدث خطأ في إرسال الملف: {str(e)}",
        )


async def show_current_level(update: Update, context: CallbackContext, state: dict):
    """
    Show the current navigation level based on the path stack.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Delete previous message
    await delete_last_message(context, chat_id, state["last_message_id"])

    # Build current path
    current_path = BASE_PATH
    for folder in state["path_stack"]:
        current_path = os.path.join(current_path, folder)

    # Get folders and files at current level (returns dicts with display names as keys)
    folders, files = get_folders_and_files(current_path)

    # Determine the message based on depth level
    level_names = ["التخصص", "الدفعة", "الفصل الدراسي"]
    depth = len(state["path_stack"])

    if depth < len(level_names):
        message = f"اختر {level_names[depth]}:"
    else:
        message = "اختر مما يلي:"

    # Get display names (sorted keys)
    all_items = list(folders.keys()) + list(files.keys())

    if not all_items:
        # Create keyboard with only back and home buttons
        buttons = [[KeyboardButton("🔙 رجوع"), KeyboardButton("🔝 القائمة الرئيسية")]]
        keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)

        msg = await context.bot.send_message(
            chat_id=chat_id,
            text="❌ لا يوجد محتوى في هذا المجلد.",
            reply_markup=keyboard,
        )
        state["last_message_id"] = msg.message_id
        return

    # Create keyboard with back button if not at root
    keyboard = create_keyboard(all_items, add_back_button=(depth > 0))

    msg = await context.bot.send_message(
        chat_id=chat_id, text=message, reply_markup=keyboard
    )
    state["last_message_id"] = msg.message_id


async def start_command(update: Update, context: CallbackContext):
    """Handle /start command"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)

    # Reset state
    state["path_stack"] = []
    state["display_stack"] = []
    state["awaiting_results"] = False
    state["result_context"] = None

    # Delete previous message
    await delete_last_message(
       context, update.effective_chat.id, state["last_message_id"]
   )

    # Show root level
    await show_current_level(update, context, state)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    user_id = update.effective_user.id
    state = get_user_state(user_id)
    text = update.message.text.strip()

    # Handle special buttons (these work even when awaiting results)
    if text == "🔝 القائمة الرئيسية":
        state["path_stack"] = []
        state["display_stack"] = []
        state["awaiting_results"] = False
        state["result_context"] = None
        await show_current_level(update, context, state)
        return

    if text == "🔙 رجوع":
        if state["awaiting_results"]:
            # Cancel result query mode and go back
            state["awaiting_results"] = False
            state["result_context"] = None
        elif state["path_stack"]:
            state["path_stack"].pop()
            state["display_stack"].pop()
        await show_current_level(update, context, state)
        return

    # If waiting for academic number input
    if state["awaiting_results"]:
        await handle_result_query(update, context, state, text)
        return

    # Build current path
    current_path = BASE_PATH
    for folder in state["path_stack"]:
        current_path = os.path.join(current_path, folder)

    # Get folders and files at current level
    folders, files = get_folders_and_files(current_path)

    # Check if text matches a display name
    actual_name = None
    is_folder = False

    if text in folders:
        actual_name = folders[text]
        is_folder = True
    elif text in files:
        actual_name = files[text]
        is_folder = False

    if actual_name:
        potential_path = os.path.join(current_path, actual_name)

        if is_folder:
            # Check if this is the results folder
            if text == "النتيجة" or "نتيجة" in text.lower():
                # Activate result query mode
                state["awaiting_results"] = True
                state["result_context"] = {
                    "path": state["path_stack"].copy(),
                    "display_path": state["display_stack"].copy(),
                }

                # Create cancel button
                cancel_button = ReplyKeyboardMarkup(
                    [
                        [
                            KeyboardButton("🔙 رجوع"),
                            KeyboardButton("🔝 القائمة الرئيسية"),
                        ]
                    ],
                    resize_keyboard=True,
                )

                msg = await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="📝 الرجاء إدخال رقمك الأكاديمي:",
                    reply_markup=cancel_button,
                )
                state["last_message_id"] = msg.message_id
                return

            # Regular folder navigation
            state["path_stack"].append(actual_name)
            state["display_stack"].append(text)
            await show_current_level(update, context, state)
        else:
            # It's a file, send it
            await send_file(update, context, potential_path)
            # Keep the same menu after sending the file
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ تم إرسال الملف. يمكنك اختيار ملف آخر أو العودة للقائمة السابقة.",
                reply_markup=create_keyboard([], add_back_button=True),
            )
            state["last_message_id"] = msg.message_id
    else:
        # Invalid selection
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ اختيار غير صحيح. الرجاء اختيار أحد الخيارات المتاحة.",
        )


async def handle_result_query(
    update: Update, context: CallbackContext, state: dict, text: str
):
    """
    Handle student result queries when academic number is entered.
    """
    chat_id = update.effective_chat.id

    # Validate that input is a number
    if not text.isdigit():
        await context.bot.send_message(
            chat_id=chat_id, text="❌ الرجاء إدخال رقم أكاديمي صحيح (أرقام فقط)."
        )
        return

    student_id = int(text)

    # Check if student exists in data
    if student_id not in data["رقم_الطالب"].values:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ الرقم الأكاديمي غير موجود. الرجاء التحقق والمحاولة مرة أخرى.",
        )
        return

    # Get student result
    result_row = data[data["رقم_الطالب"] == student_id].iloc[0]

    # Format the response
    response = (
        f"نتيجة الطالب {result_row['الاسم_الكامل']}\n"
        f"{'─' * 18}\n"
        f"التخصص: {result_row['التخصص']}\n"
        f"المستوى: {result_row['المستوى']}\n"
        f"المعدل: {result_row['المعدل']}\n"
        f"الحالة: {result_row['الحالة']}\n"
        f"التقدير: {result_row['التقدير']}\n"
    )

    # Send the result
    await context.bot.send_message(chat_id=chat_id, text=response)

    # Reset state and go back to previous menu
    state["awaiting_results"] = False
    state["result_context"] = None

    # Show the menu again
    await show_current_level(update, context, state)


async def help_command(update: Update, context: CallbackContext):
    """Handle /help command"""
    help_text = """
🤖 مرحباً بك في بوت جامعة البطانة

هذا البوت يساعدك في:
• الوصول إلى المحاضرات والملفات الدراسية
• تصفح المواد حسب التخصص والدفعة والفصل الدراسي
• تحميل الملفات مباشرة

📝 كيفية الاستخدام:
1. اختر التخصص
2. اختر الدفعة
3. اختر الفصل الدراسي
4. اختر المادة
5. اختر المحاضرة أو الملف المطلوب

استخدم الأزرار للتنقل:
• 🔙 رجوع: للعودة للقائمة السابقة
• 🔝 القائمة الرئيسية: للعودة للبداية

للبدء من جديد، استخدم الأمر /start
"""
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)


if __name__ == "__main__":
    # Check if base path exists
    if not os.path.exists(BASE_PATH):
        print(f"Warning: Base path '{BASE_PATH}' does not exist. Creating it...")
        os.makedirs(BASE_PATH, exist_ok=True)

    # Build application
    application = ApplicationBuilder().token(telegram_token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    )

    print("Bot is running...")
    application.run_polling()
