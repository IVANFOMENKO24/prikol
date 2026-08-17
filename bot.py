import asyncio
import logging
import os
import subprocess
import json
import random
import shutil
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.getenv("FFPROBE_BIN", "ffprobe")

API_TOKEN = os.getenv("BOT_TOKEN", "8469254637:AAH38u632eQb7la4_Tm6HJY0L1dMGyV_8-4")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.getenv("MEDIA_DIR", BASE_DIR)


def media_path(filename):
    if os.path.isabs(filename):
        return filename
    return os.path.join(MEDIA_DIR, filename)


BASE_VIDEO_1 = media_path(os.getenv("BASE_VIDEO_1", r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прикол.mov"))
BASE_VIDEO_2 = media_path(os.getenv("BASE_VIDEO_2", r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прикол2.mov"))
BASE_VIDEO_3 = media_path(os.getenv("BASE_VIDEO_3", r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прикол3.mov"))

DEFAULT_SPIDER_SOUNDS = [
    r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прико\паук1.WAV",
    r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прико\паук2.WAV",
    r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прико\паук3.WAV",
    r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прико\паук4.WAV",
    r"C:\Users\иванка\Downloads\фигура\да слез\эдиь\123\сайт\сайт 2\эд\мемасы\рендер\прикол\прико\паук5.mp3",
]

SPIDER_SOUNDS_ENV = os.getenv("SPIDER_SOUNDS")
if SPIDER_SOUNDS_ENV:
    SPIDER_SOUNDS = [media_path(p.strip()) for p in SPIDER_SOUNDS_ENV.split(";") if p.strip()]
else:
    SPIDER_SOUNDS = [media_path(p) for p in DEFAULT_SPIDER_SOUNDS]

OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(BASE_DIR, "processed"))

FFMPEG_INSTALL_HINT = (
    "❌ ffmpeg/ffprobe не найдены.\n"
    "Установите ffmpeg:\n"
    "  • Ubuntu/Debian:  apt-get update && apt-get install -y ffmpeg\n"
    "  • CentOS/RHEL:    yum install -y ffmpeg\n"
    "  • Alpine:         apk add --no-cache ffmpeg\n"
    "  • macOS (brew):   brew install ffmpeg\n"
    "  • Windows:        скачайте с https://www.gyan.dev/ffmpeg/builds/ и добавьте bin в PATH\n"
    "Либо задайте пути через переменные окружения FFMPEG_BIN и FFPROBE_BIN."
)

user_data = {}

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)


def check_binary(bin_path, name):
    if os.path.isabs(bin_path):
        if not os.path.isfile(bin_path):
            return None
        return bin_path
    found = shutil.which(bin_path)
    if not found:
        return None
    return found


def check_required_files():
    errors = []
    ff = check_binary(FFMPEG_BIN, "ffmpeg")
    fp = check_binary(FFPROBE_BIN, "ffprobe")
    if not ff:
        errors.append(f"ffmpeg не найден: '{FFMPEG_BIN}'")
    if not fp:
        errors.append(f"ffprobe не найден: '{FFPROBE_BIN}'")

    for label, path in [
        ("BASE_VIDEO_1", BASE_VIDEO_1),
        ("BASE_VIDEO_2", BASE_VIDEO_2),
        ("BASE_VIDEO_3", BASE_VIDEO_3),
    ]:
        if not os.path.isfile(path):
            errors.append(f"{label} не найден: {path}")

    for i, path in enumerate(SPIDER_SOUNDS, 1):
        if not os.path.isfile(path):
            errors.append(f"SPIDER_SOUNDS[{i}] не найден: {path}")

    return errors, ff, fp


async def run_subprocess(*cmd):
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout, stderr, None
    except FileNotFoundError as e:
        return -1, b"", b"", f"{FFMPEG_INSTALL_HINT}\n\nДетали: {e}"
    except Exception as e:
        return -1, b"", b"", str(e)


async def get_duration(file_path):
    cmd = [
        FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    code, stdout, stderr, err = await run_subprocess(*cmd)
    if err:
        logging.error(f"get_duration subprocess error: {err}")
        raise RuntimeError(err)
    if code == 0:
        try:
            return float(stdout.decode().strip())
        except ValueError:
            return 0.0
    logging.error(f"ffprobe error (code {code}): {stderr.decode(errors='replace')}")
    return 0.0


async def has_audio(file_path):
    cmd = [
        FFPROBE_BIN, "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index", "-of", "csv=p=0", file_path
    ]
    code, stdout, stderr, err = await run_subprocess(*cmd)
    if err:
        logging.error(f"has_audio subprocess error: {err}")
        raise RuntimeError(err)
    if code != 0:
        logging.error(f"ffprobe error (code {code}): {stderr.decode(errors='replace')}")
        return False
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
        if not SPIDER_SOUNDS:
            logging.error("SPIDER_SOUNDS пуст — добавьте хотя бы один звук")
            return False
        temp_video = input_path + "_temp.mp4"
        spider_sound = random.choice(SPIDER_SOUNDS)
        spider_duration = await get_duration(spider_sound)
        photo_duration = max(3.0, spider_duration)

        cmd_photo = [
            FFMPEG_BIN, "-y", "-loop", "1", "-i", input_path,
            "-i", spider_sound,
            "-t", str(photo_duration), "-pix_fmt", "yuv420p",
            "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=640:640,setsar=1",
            "-c:v", "libx264", "-r", "30", "-c:a", "aac", "-shortest", temp_video
        ]
        code, _out, err, sub_err = await run_subprocess(*cmd_photo)
        if sub_err:
            logging.error(f"photo encode error: {sub_err}")
            return False
        if code != 0:
            logging.error(f"ffmpeg photo error (code {code}): {err.decode(errors='replace')}")
            return False
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
        transition_duration = 0.2
        offset = 1.0
        user_start_offset = 2.0
    else:
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
        start_time = user_start_offset if not is_photo else 0.0
        user_play_duration = user_duration - start_time
        total_duration = offset + user_play_duration
        v0_filter_extended = f"{v0_filter},tpad=stop_mode=clone:stop_duration={user_play_duration}"

        v1_overlay_filter = (
            f"trim=start={start_time},setpts=PTS-STARTPTS,crop='min(iw,ih)':'min(iw,ih)',"
            f"scale=640:640,setsar=1,fps=30,settb=1/30,"
            f"format=yuva420p,fade=in:st=0:d=0.2:alpha=1,setpts=PTS+{offset}/TB"
        )

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
        FFMPEG_BIN, "-y",
        "-i", base_path,
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-t", str(total_duration) if variant != 1 else str(base_duration + user_duration - transition_duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-b:v", "1M",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ]

    logging.info(f"Running FFmpeg: {' '.join(map(str, cmd))}")
    code, _out, err, sub_err = await run_subprocess(*cmd)
    if sub_err:
        logging.error(f"process_media subprocess error: {sub_err}")
        raise RuntimeError(sub_err)
    if code != 0:
        error_msg = err.decode(errors="replace")
        logging.error(f"FFmpeg error (code {code}): {error_msg}")
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
        "file_id": file_id,
        "is_photo": is_photo,
        "ext": ext,
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
        3: "мои личные рабы",
    }

    await callback.message.edit_text(
        f"⏳ Обрабатываю: {variant_names[variant]}... Это займет пару секунд."
    )

    input_path = None
    output_path = None
    try:
        file = await bot.get_file(data["file_id"])
        input_path = os.path.join(OUTPUT_DIR, f"input_{user_id}{data['ext']}")
        output_path = os.path.join(OUTPUT_DIR, f"output_{user_id}.mp4")

        await bot.download_file(file.file_path, input_path)

        success = await process_media(input_path, output_path, variant, data["is_photo"])

        if success:
            video_note = FSInputFile(output_path)
            await callback.message.answer_video_note(video_note)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                "❌ Ошибка обработки видео. Возможно, на хостинге не установлен ffmpeg или нет медиафайлов."
            )

    except RuntimeError as e:
        logging.error(f"Runtime error: {e}")
        await callback.message.edit_text(f"❌ {e}")
    except Exception as e:
        logging.error(f"Error: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    finally:
        try:
            if input_path and os.path.exists(input_path):
                os.remove(input_path)
            temp_path = (input_path + "_temp.mp4") if input_path else None
            if temp_path and data.get("is_photo") and os.path.exists(temp_path):
                os.remove(temp_path)
            if output_path and os.path.exists(output_path):
                os.remove(output_path)
        except Exception as ce:
            logging.warning(f"Cleanup error: {ce}")


async def main():
    errors, _ff, _fp = check_required_files()
    if errors:
        logging.error("========== ОШИБКИ КОНФИГУРАЦИИ ==========")
        for e in errors:
            logging.error("  • " + e)
        logging.error("=========================================")
        logging.error(FFMPEG_INSTALL_HINT)
        raise RuntimeError("Ошибки конфигурации: " + "; ".join(errors))

    logging.info(f"Using ffmpeg:  {_ff}")
    logging.info(f"Using ffprobe: {_fp}")
    logging.info(f"Media dir:     {MEDIA_DIR}")
    logging.info(f"Output dir:    {OUTPUT_DIR}")
    logging.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
