import asyncio
import logging
import os
import subprocess
import json
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = '8469254637:AAH38u632eQb7la4_Tm6HJY0L1dMGyV_8-4'
BASE_VIDEO_1 = r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прикол.mov"
BASE_VIDEO_2 = r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прикол2.mov"
BASE_VIDEO_3 = r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прикол3.mov"
SPIDER_SOUNDS = [
    r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прико\паук1.WAV",
    r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прико\паук2.WAV",
    r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прико\паук3.WAV",
    r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прико\паук4.WAV",
    r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прико\паук5.mp3",
]
OUTPUT_DIR = "processed"

# Simple storage for user media
user_data = {}

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

async def get_duration(file_path):
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', file_path
    ]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode == 0:
        return float(stdout.decode().strip())
    return 0.0

async def has_audio(file_path):
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'a',
        '-show_entries', 'stream=index', '-of', 'csv=p=0', file_path
    ]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    return len(stdout.decode().strip()) > 0

async def process_media(input_path, output_path, variant=1, is_photo=False):
    if variant == 1:
        base_path = BASE_VIDEO_1
    elif variant == 2:
        base_path = BASE_VIDEO_2
    else:
        base_path = BASE_VIDEO_3
        
    base_duration = await get_duration(base_path)
    base_has_audio = await has_audio(base_path)
    
    if is_photo:
        temp_video = input_path + "_temp.mp4"
        spider_sound = random.choice(SPIDER_SOUNDS)
        spider_duration = await get_duration(spider_sound)
        photo_duration = max(3.0, spider_duration)
        
        cmd_photo = [
            'ffmpeg', '-y', '-loop', '1', '-i', input_path,
            '-i', spider_sound,
            '-t', str(photo_duration), '-pix_fmt', 'yuv420p',
            '-vf', "crop='min(iw,ih)':'min(iw,ih)',scale=640:640,setsar=1",
            '-c:v', 'libx264', '-r', '30', '-c:a', 'aac', '-shortest', temp_video
        ]
        proc = await asyncio.create_subprocess_exec(*cmd_photo)
        await proc.wait()
        input_path = temp_video
        user_duration = photo_duration
        user_has_audio = True
    else:
        user_duration = await get_duration(input_path)
        user_has_audio = await has_audio(input_path)

    if variant == 1:
        transition_duration = 0.3
        if user_duration < transition_duration:
            transition_duration = user_duration / 2
        offset = base_duration - transition_duration
    elif variant == 2:
        # Variant 2: Transition at 1.0s, user video starts at 2s
        transition_duration = 0.2
        offset = 1.0
        user_start_offset = 2.0
    else:
        # Variant 3: Transition at 2.0s, user video starts at 3s
        transition_duration = 0.2
        offset = 2.0
        user_start_offset = 3.0

    v0_filter = "scale=640:640,setsar=1,fps=30,settb=1/30,format=yuv420p"
    v1_filter = "crop='min(iw,ih)':'min(iw,ih)',scale=640:640,setsar=1,fps=30,settb=1/30,format=yuv420p"
    
    audio_source = ""
    if not base_has_audio:
        audio_source += "aevalsrc=0:d=inf[a0_silence];"
        a0_ready = "[a0_silence]"
    else:
        a0_ready = "[0:a]"
        
    if not user_has_audio:
        audio_source += "aevalsrc=0:d=inf[a1_silence];"
        a1_ready = "[a1_silence]"
    else:
        a1_ready = "[1:a]"

    if variant == 1:
        filter_complex = (
            f"{audio_source}"
            f"[0:v]{v0_filter}[v0];"
            f"[1:v]{v1_filter}[v1];"
            f"[v0][v1]xfade=transition=fade:duration={transition_duration}:offset={offset}[v];"
            f"{a0_ready}aresample=44100[a0];"
            f"{a1_ready}aresample=44100[a1];"
            f"[a0][a1]acrossfade=d={transition_duration}[a]"
        )
    else:
        # Variant 2 & 3: Overlay style transition
        # For photos, we don't need to offset the start time (user_start_offset)
        # For videos, we start from user_start_offset
        start_time = user_start_offset if not is_photo else 0.0
        
        # Calculate how much of the user video will be played
        user_play_duration = user_duration - start_time
        total_duration = offset + user_play_duration
        
        # We use tpad to extend the base video with its last frame (clone) instead of black
        v0_filter_extended = f"{v0_filter},tpad=stop_mode=clone:stop_duration={user_play_duration}"
        
        v1_overlay_filter = (
            f"trim=start={start_time},setpts=PTS-STARTPTS,crop='min(iw,ih)':'min(iw,ih)',"
            f"scale=640:640,setsar=1,fps=30,settb=1/30,"
            f"format=yuva420p,fade=in:st=0:d=0.2:alpha=1,setpts=PTS+{offset}/TB"
        )
        
        # Audio from user needs to be trimmed AND DELAYED to match the video offset
        a1_delay = int(offset * 1000)
        a1_filter = (
            f"atrim=start={start_time},asetpts=PTS-STARTPTS,aresample=44100,adelay={a1_delay}|{a1_delay}"
            if not is_photo else f"aresample=44100,adelay={a1_delay}|{a1_delay}"
        )

        filter_complex = (
            f"{audio_source}"
            f"[0:v]{v0_filter_extended}[v0];"
            f"[1:v]{v1_overlay_filter}[v1_faded];"
            f"[v0][v1_faded]overlay=eof_action=pass[v_temp];"
            f"[v_temp]format=yuv420p[v];"
            f"{a0_ready}aresample=44100[a0];"
            f"{a1_ready}{a1_filter}[a1];"
            f"[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0,volume=2[a]"
        )
    
    cmd = [
        'ffmpeg', '-y',
        '-i', base_path,
        '-i', input_path,
        '-filter_complex', filter_complex,
        '-map', '[v]', '-map', '[a]',
        '-t', str(total_duration) if variant != 1 else str(base_duration + user_duration - transition_duration),
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30', '-b:v', '1M',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        output_path
    ]
    
    logging.info(f"Running FFmpeg: {' '.join(map(str, cmd))}")
    process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        error_msg = stderr.decode(errors='replace')
        logging.error(f"FFmpeg error (code {process.returncode}): {error_msg}")
        return False
    return True

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Дарова! Здесь можно создать кружок с Махом. Отправь мне видео, кружок или фото, и выбери вариант прикола!"
    )

@dp.message(F.video | F.video_note | F.photo)
async def handle_media(message: types.Message):
    file_id = None
    is_photo = False
    ext = ".mp4"
    
    if message.video:
        file_id = message.video.file_id
    elif message.video_note:
        file_id = message.video_note.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id
        is_photo = True
        ext = ".jpg"
    
    user_data[message.from_user.id] = {
        'file_id': file_id,
        'is_photo': is_photo,
        'ext': ext
    }
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎬 смотрите какой прикол..", callback_data="prikol_1"))
    builder.row(InlineKeyboardButton(text="⚡ давно хотел вам это показать..", callback_data="prikol_2"))
    builder.row(InlineKeyboardButton(text="🔥 мои личные рабы", callback_data="prikol_3"))
    
    await message.answer("Выбери вариант прикола:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("prikol_"))
async def process_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_data:
        await callback.answer("Ошибка: медиа не найдено. Отправь файл снова.")
        return
        
    variant = int(callback.data.split("_")[1])
    data = user_data[user_id]
    
    variant_names = {
        1: "смотрите какой прикол..",
        2: "давно хотел вам это показать..",
        3: "мои личные рабы"
    }
    
    await callback.message.edit_text(f"⏳ Обрабатываю: {variant_names[variant]}... Это займет пару секунд.")
    
    try:
        file = await bot.get_file(data['file_id'])
        input_path = os.path.join(OUTPUT_DIR, f"input_{user_id}{data['ext']}")
        output_path = os.path.join(OUTPUT_DIR, f"output_{user_id}.mp4")
        
        await bot.download_file(file.file_path, input_path)
        
        success = await process_media(input_path, output_path, variant, data['is_photo'])
        
        if success:
            video_note = FSInputFile(output_path)
            await callback.message.answer_video_note(video_note)
            await callback.message.delete()
        else:
            await callback.message.edit_text("❌ Ошибка обработки видео.")
            
        # Cleanup
        if os.path.exists(input_path): os.remove(input_path)
        if data['is_photo'] and os.path.exists(input_path + "_temp.mp4"): os.remove(input_path + "_temp.mp4")
        if os.path.exists(output_path): os.remove(output_path)
        
    except Exception as e:
        logging.error(f"Error: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}")

async def main():
    logging.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
