import asyncio
from FileStream.bot import FileStream, multi_clients
from FileStream.utils.bot_utils import (
    is_user_banned, is_user_exist, is_user_joined, gen_link, 
    is_channel_banned, is_channel_exist, is_user_authorized
)
from FileStream.utils.database import Database
from FileStream.utils.file_properties import get_file_ids, get_file_info
from FileStream.config import Telegram
from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums.parse_mode import ParseMode

db = Database(Telegram.DATABASE_URL, Telegram.SESSION_NAME)

@FileStream.on_message(
    filters.private & (filters.document | filters.video | filters.video_note |
                       filters.audio | filters.voice | filters.animation | filters.photo),
    group=4
)
async def private_receive_handler(bot: Client, message: Message):
    if not message.from_user:  # Ignore if the message is from the bot itself
        return  

    if not await is_user_authorized(message) or await is_user_banned(message):
        return

    await is_user_exist(bot, message)
    
    if Telegram.FORCE_SUB and not await is_user_joined(bot, message):
        return

    try:
        inserted_id = await db.add_file(get_file_info(message))
        await get_file_ids(False, inserted_id, multi_clients, message)
        reply_markup, stream_text = await gen_link(_id=inserted_id)

        await message.reply_text(
            text=stream_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=reply_markup,
            quote=True
        )

    except FloodWait as e:
        print(f"Sleeping for {e.value}s due to FloodWait")
        await asyncio.sleep(e.value)
        await bot.send_message(
            chat_id=Telegram.ULOG_CHANNEL,
            text=f"🚨 **FloodWait**: {e.value}s from [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n\n"
                 f"**User ID:** `{message.from_user.id}`",
            disable_web_page_preview=True,
            parse_mode=ParseMode.MARKDOWN
        )

@FileStream.on_message(
    filters.channel & ~filters.forwarded & ~filters.media_group & 
    (filters.document | filters.video | filters.video_note | 
     filters.audio | filters.voice | filters.photo)
)
async def channel_receive_handler(bot: Client, message: Message):
    if await is_channel_banned(bot, message):
        return

    await is_channel_exist(bot, message)

    try:
        inserted_id = await db.add_file(get_file_info(message))
        await get_file_ids(False, inserted_id, multi_clients, message)
        reply_markup, stream_link = await gen_link(_id=inserted_id)

        await bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.id,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Download Link", 
                                      url=f"https://t.me/{FileStream.username}?start=stream_{inserted_id}")]
            ])
        )

    except FloodWait as w:
        print(f"Sleeping for {w.value}s due to FloodWait")
        await asyncio.sleep(w.value)
        await bot.send_message(
            chat_id=Telegram.ULOG_CHANNEL,
            text=f"🚨 **FloodWait**: {w.value}s from {message.chat.title}\n\n"
                 f"**Channel ID:** `{message.chat.id}`",
            disable_web_page_preview=True
        )

    except Exception as e:
        error_msg = f"❌ **Error:** {e}\n\n⚠️ Ensure the bot has 'Edit Messages' permission in the channel."
        await bot.send_message(chat_id=Telegram.ULOG_CHANNEL, text=error_msg, disable_web_page_preview=True)
        print(error_msg)
