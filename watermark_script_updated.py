import os
import subprocess
import logging
from colorama import Fore, Style, init
import yaml
import tqdm
import re

from src.utils.get_metadata import GetVideoMetadata
from src.config import CONFIG
from src.utils.logger import logger
from src.calculations.bitrate_calculator import BitrateCalculator


init(autoreset=True)

# Создание выходных директорий, если они не существуют
# os.makedirs(output_dir, exist_ok=True)
# os.makedirs(no_wm_output_dir, exist_ok=True)

def print_process_title(input_file: str):
    """Печатает разделитель с названием текущего файла."""
    print(f"\n{Fore.CYAN}{'=' * 100}")
    print(f"{Fore.YELLOW}Обработка файла: {input_file}")
    print(f"{Fore.CYAN}{'=' * 100}\n")

def run_ffmpeg_with_progress(command, total_duration):
    """
    Запускает команду ffmpeg с прогресс-баром.

    :param command: Команда для выполнения.
    :param total_duration: Общая длительность видео в секундах.
    """
    progress_bar = tqdm.tqdm(total=int(total_duration), unit="s", desc="Обработка видео", dynamic_ncols=True)
    try:
        # Явно указываем кодировку и обработку ошибок
        process = subprocess.Popen(
            command,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            encoding='utf-8',       # Используем UTF-8
            errors='replace'         # Заменяем неподдерживаемые символы
        )
        fps = 0  # Начальное значение FPS
        for line in process.stderr:
            # Ищем строку с прогрессом (время обработки)
            time_match = re.search(r"time=(\d+):(\d+):(\d+.\d+)", line)
            fps_match = re.search(r"fps=\s*(\d+)", line)  # Ищем FPS
            if time_match:
                h, m, s = map(float, time_match.groups())
                elapsed_time = int(h * 3600 + m * 60 + s)  # Приводим к целому числу
                progress_bar.n = min(elapsed_time, int(total_duration))
                progress_bar.refresh()
            if fps_match:
                fps = int(fps_match.group(1))  # Извлекаем FPS как целое число
            progress_bar.set_postfix({"fps": fps})  # Обновляем FPS в прогресс-баре
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)
    finally:
        progress_bar.close()

def process_video_with_watermark(input_file, base_name, codec, duration, audio_bitrate, color_space, color_primaries, color_trc, color_range, video_bitrate, maxrate, bufsize):
    """
    Обрабатывает видео с добавлением водяного знака.

    :param input_file: Путь к входному видеофайлу.
    :param base_name: Базовое имя выходного файла.
    :param codec: Кодек видео.
    :param duration: Длительность видео в секундах.
    :param audio_bitrate: Битрейт аудио в кбит/с.
    :param color_space: Цветовое пространство.
    :param color_primaries: Основные цвета.
    :param color_trc: Цветовая передача.
    :param color_range: Диапазон цвета.
    :param video_bitrate: Битрейт видео в бит/с.
    :param maxrate: Максимальный битрейт.
    :param bufsize: Размер буфера.
    """
    output_file = os.path.join(CONFIG.output_dir, f'[Ani4KHUB] {base_name}_watermarked.mp4')

    if os.path.exists(output_file):
        logger.info(f'Файл с водяной меткой {output_file} уже существует. Пропускаем обработку.')
        return

    logger.info (f'Обработка файла с водяной меткой: {base_name}_watermarked.mp4')

    ffmpeg_command = [
        "ffmpeg",
        "-hwaccel", "cuda",
        "-c:v", (
            "auto" if codec not in ["hevc", "h264"]
            else "hevc_cuvid" if codec == "hevc"
            else "h264_cuvid"
        ),
        "-i", input_file,
        "-i", CONFIG.static_watermark,
        "-pix_fmt", "yuv420p10le",
        "-color_range", color_range,
        "-filter_complex", (
            "[1:v]scale=iw*0.09:ih*0.09,"
            "zscale=rangein=full:range=limited,"
            "format=rgba[watermark];"
            "[0:v][watermark]overlay="
            "x='max(main_w - w - (w/3.5), 0)':"
            "y='max((w/2.5) - (h/2), 0)'[overlayed_video];"
            "[overlayed_video]format=yuv420p10le"
        ),
        "-c:v", "hevc_nvenc",
        "-preset", "p7",
        "-profile:v", "main10",
        "-b:v", f"{video_bitrate}",
        "-maxrate", f"{maxrate}",
        "-bufsize", f"{bufsize}",
        "-rc", "vbr",
        "-aq-strength", "15",
        "-spatial-aq", "1",
        "-temporal-aq", "1",
        "-rc-lookahead", "64",
        "-colorspace", color_space,
        "-color_primaries", color_primaries,
        "-color_trc", color_trc,
        "-tag:v", "hvc1",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", f"{audio_bitrate}k",
        "-ac", "2",
        "-map_metadata", "-1",
        "-metadata", f"description={CONFIG.description}",
        "-metadata", f"title={CONFIG.description}",
        output_file
    ]
    logger.debug(ffmpeg_command)
    run_ffmpeg_with_progress(ffmpeg_command, duration)

def process_video_without_watermark(input_file, base_name, codec, duration, audio_bitrate, color_space, color_primaries, color_trc, color_range, video_bitrate, maxrate, bufsize):
    """
    Обрабатывает видео без добавления водяного знака.

    :param input_file: Путь к входному видеофайлу.
    :param base_name: Базовое имя выходного файла.
    :param codec: Кодек видео.
    :param duration: Длительность видео в секундах.
    :param audio_bitrate: Битрейт аудио в кбит/с.
    :param color_space: Цветовое пространство.
    :param color_primaries: Основные цвета.
    :param color_trc: Цветовая передача.
    :param color_range: Диапазон цвета.
    :param video_bitrate: Битрейт видео в бит/с.
    :param maxrate: Максимальный битрейт.
    :param bufsize: Размер буфера.
    """
    no_wm_output_file = os.path.join(CONFIG.no_wm_output_dir, f'[Ani4KHUB] {base_name}_wwm.mp4')

    if os.path.exists(no_wm_output_file):
        logger.info(f'Файл без водяной метки {no_wm_output_file} уже существует. Пропускаем обработку.')
        return

    logger.info(f'Обработка файла без водяной метки: {base_name}_wwm.mp4')

    ffmpeg_command = [
        "ffmpeg",
        "-c:v", (
            "auto" if codec not in ["hevc", "h264"]
            else "hevc_cuvid" if codec == "hevc"
            else "h264_cuvid"
        ),
        "-i", input_file,
        "-c:v", "hevc_nvenc",
        "-preset", "p7",
        "-profile:v", "main10",
        "-b:v", f"{video_bitrate}",
        "-maxrate", f"{maxrate}",
        "-bufsize", f"{bufsize}",
        "-rc", "vbr",
        "-aq-strength", "15",
        "-spatial-aq", "1",
        "-temporal-aq", "1",
        "-rc-lookahead", "64",
        "-colorspace", color_space,
        "-color_primaries", color_primaries,
        "-color_trc", color_trc,
        "-color_range", color_range,
        "-tag:v", "hvc1",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", f"{audio_bitrate}k",
        "-ac", "2",
        "-map_metadata", "-1",
        "-metadata", f"title={CONFIG.description}",
        "-metadata", f"description={CONFIG.description}",
        no_wm_output_file
    ]

    run_ffmpeg_with_progress(ffmpeg_command, duration)

def process_video(input_file, base_name, mode):
    """
    Обрабатывает видеофайл в зависимости от выбранного режима.

    :param input_file: Путь к входному видеофайлу.
    :param base_name: Базовое имя выходного файла.
    :param mode: Режим обработки (1 - с водяным знаком и без, 2 - только с водяным знаком).
    """
    # Получение метаданных
    metadata = GetVideoMetadata(input_file)
    bitrate_calc = BitrateCalculator()
    
    logger.debug(metadata)
    
    if metadata.codec is None:
        logger.error(f'Не удалось получить метаданные для {input_file}')
        return

    # Оценка размера видео и аудио    
    if metadata.duration / 60 > CONFIG.threshold_minutes:  # Если длительность видео больше порога
        logger.info(f"Длина видео превышает {CONFIG.threshold_minutes} минут. "
            f"Расчет битрейта для достижения целевого размера...")
        video_bitrate, maxrate, bufsize = bitrate_calc.adjust_bitrate_to_size(
            duration=metadata.duration,
            audio_bitrate=metadata.audio_bitrate,  # Теперь передаем явно
            target_size_gb=CONFIG.max_file_size_gb,
        )
    
    else:
        logger.info(f"Длина видео менее {CONFIG.threshold_minutes} минут. "
            f"Установка битрейта(Мбит/с) max/min/avg: 100/0/12, размер буфера: 200 Мбит...")
        # Для коротких видео устанавливаем стандартный битрейт
        video_bitrate = CONFIG.default_video_bitrate
        maxrate = 100 * 10**6  # 100 Мбит
        bufsize = 200 * 10**6  # 200 Мбит

    print_process_title(input_file)

    if mode == 1:
        # Обработка с водяным знаком и без
        process_video_with_watermark(
            input_file,
            base_name,
            metadata.codec,
            metadata.duration,
            metadata.audio_bitrate,
            metadata.color_space,
            metadata.color_primaries,
            metadata.color_trc, 
            metadata.color_range,
            video_bitrate,
            maxrate,
            bufsize
        )
        process_video_without_watermark(
            input_file,
            base_name,
            metadata.codec,
            metadata.duration,
            metadata.audio_bitrate,
            metadata.color_space,
            metadata.color_primaries,
            metadata.color_trc,
            metadata.color_range,
            video_bitrate,
            maxrate,
            bufsize
        )
    elif mode == 2:
        # Обработка только с водяным знаком
        process_video_with_watermark(
            input_file,
            base_name,
            metadata.codec,
            metadata.duration,
            metadata.audio_bitrate,
            metadata.color_space,
            metadata.color_primaries,
            metadata.color_trc,
            metadata.color_range,
            video_bitrate,
            maxrate,
            bufsize
        )
    else:
        logger.error("Неверный режим обработки. Выберите 1 или 2.")

def main():
    """
    Основная функция, которая запускает скрипт и обрабатывает видео в зависимости от выбранного режима.
    """
    print(f"{Fore.CYAN}{'=' * 100}\n")
    print("Выберите режим обработки:")
    print("1 - Обработка всех видео в двух вариантах: с водяным знаком и без")
    print("2 - Обработка только с водяным знаком")
    mode = int(input("Введите номер режима: "))

    if mode not in [1, 2]:
        logger.error("Неверный режим обработки. Выберите 1 или 2.")
        return

    processed_any = False

    for file in os.listdir(CONFIG.input_dir):
        file_path = os.path.join(CONFIG.input_dir, file)
        
        if os.path.isfile(file_path) and file.lower().endswith(('mkv', 'mp4', 'avi')):
            base_name = os.path.splitext(file)[0]
            process_video(file_path, base_name, mode)
            processed_any = True

    if not processed_any:
        logger.info("Не найдено файлов для обработки.")

    # Завершение работы
    logger.success("Все файлы уже обработаны или пропущены.")
    input("Нажмите Enter для выхода...")

if __name__ == "__main__":
    main()