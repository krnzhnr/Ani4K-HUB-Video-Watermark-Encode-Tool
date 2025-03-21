import os
import subprocess
import logging
from colorama import Fore, Style, init
import yaml
import tqdm
import re

from src.utils.get_metadata import GetVideoMetadata
from src.config import CONFIG

init(autoreset=True)


# Логирование
log_file_path = os.path.join(os.path.dirname(__file__), "script.log")
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding='utf-8'  # Устанавливаем кодировку UTF-8 для поддержки кириллицы
)

def log(message, level="INFO"):
    """
    Выводит сообщение в консоль с соответствующим цветом и записывает его в лог-файл.

    :param message: Сообщение, которое нужно вывести.
    :param level: Уровень логирования, может быть "INFO", "SUCCESS", "WARNING", "ERROR".
    """
    color_map = {"INFO": Style.BRIGHT + Fore.BLUE, 
                "SUCCESS": Fore.GREEN, 
                "WARNING": Fore.YELLOW, 
                "ERROR": Fore.RED}
    print(color_map.get(level, Fore.WHITE) + message)
    getattr(logging, level.lower(), logging.info)(message)

# Создание выходных директорий, если они не существуют
# os.makedirs(output_dir, exist_ok=True)
# os.makedirs(no_wm_output_dir, exist_ok=True)

def print_process_title(input_file: str):
    """Печатает разделитель с названием текущего файла."""
    print(f"\n{Fore.CYAN}{'=' * 100}")
    print(f"{Fore.YELLOW}Обработка файла: {input_file}")
    print(f"{Fore.CYAN}{'=' * 100}\n")


def calculate_sizes(duration, video_bitrate, audio_bitrate=None):
    """
    Оценивает размеры видео и аудиопотоков на основе длительности видео и битрейтов.

    :param duration: Длительность видео в секундах.
    :param video_bitrate: Битрейт видео в бит/с.
    :param audio_bitrate: Битрейт аудио в кбит/с. Если None, используется target_audio_bitrate.
    :return: Размер видео и аудио потоков в МБ.
    """
    audio_bitrate = CONFIG.target_audio_bitrate or audio_bitrate  # Используем целевой битрейт, если текущий не указан
    video_size = (video_bitrate * duration) / (8 * 1024 * 1024)  # в МБ
    audio_size = (audio_bitrate * duration) / (8 * 1024)  # в МБ
    
    return video_size, audio_size

def adjust_bitrate_to_size(input_file, static_watermark, duration, audio_bitrate, target_size_gb, video_bitrate):
    """
    Попытка уменьшить битрейт видео до тех пор, пока размер выходного файла не станет меньше заданного target_size_gb.

    :param input_file: Путь к видеофайлу.
    :param static_watermark: Путь к файлу водяного знака (не используется в расчетах, но может быть нужен для корректной обработки).
    :param duration: Длительность видео в секундах.
    :param audio_bitrate: Битрейт аудио в кбит/с.
    :param target_size_gb: Целевой размер выходного файла в ГБ.
    :param video_bitrate: Начальный битрейт видео в бит/с.
    :return: Адаптированный битрейт видео в бит/с.
    """
    target_size_bytes = target_size_gb * 1024 * 1024 * 1024  # целевой размер в байтах
    current_video_bitrate = video_bitrate

    while True:
        # Оценка размера видео с текущими битрейтами
        video_size, audio_size = calculate_sizes(duration, current_video_bitrate, audio_bitrate)
        total_size = (video_size + audio_size) * (1024 * 1024)  # Перевод в байты

        log(f"Текущий расчетный размер: {total_size / (1024**3):.2f} GB (video: {video_size:.2f} MB, audio: {audio_size:.2f} MB)")

        if total_size <= target_size_bytes:
            maxrate, bufsize = calculate_maxrate_and_bufsize(current_video_bitrate)
            # Переводим maxrate, current_video_bitrate и bufsize в Мбит
            maxrate_mbit = maxrate / 1000000
            current_video_bitrate_mbit = current_video_bitrate / 1000000
            bufsize_mbit = bufsize / 1000000
            log(f"Целевой размер достигнут: {total_size / (1024**3):.2f} GB. "
                f"Битрейт (Мбит) max/min/avg: {maxrate_mbit:.2f}/0/{current_video_bitrate_mbit:.2f}, "
                f"размер буфера: {bufsize_mbit:.2f} Мбит.", "SUCCESS")
            break
        else:
            # Уменьшаем битрейт видео на 1% и проверяем снова
            current_video_bitrate *= 0.99
            log(f"Снижение битрейта до {current_video_bitrate / 10**6:.2f} Mbps для достижения целевого размера.", "WARNING")

    return current_video_bitrate

def calculate_maxrate_and_bufsize(video_bitrate):
    """
    Рассчитывает оптимальные значения для maxrate и bufsize на основе переданного битрейта видео.

    :param video_bitrate: Битрейт видео в бит/с.
    :return: Рассчитанные значения maxrate и bufsize.
    """
    maxrate = int(video_bitrate * 1.2)  # Максимальный битрейт — 1.25 раза больше обычного
    bufsize = maxrate * 1.6  # Размер буфера равен maxrate
    return maxrate, bufsize

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
        log(f'Файл с водяной меткой {output_file} уже существует. Пропускаем обработку.', "INFO")
        return

    log(f'Обработка файла с водяной меткой: {base_name}_watermarked.mp4', "INFO")

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
    
    ffmpeg_commands = [
    'ffmpeg',
    '-hwaccel', 'cuda',
    '-c:v', 'libaom-av1',
    '-i', input_file,
    '-i', CONFIG.static_watermark,
    '-pix_fmt', 'yuv420p10le',
    '-color_range', color_range,
    '-filter_complex', "[1:v]scale=iw*0.09:ih*0.09:flags=lanczos[scaled_static];"
                        "[0:v][scaled_static]overlay=x='main_w-w-68':y='64':format=auto,"
                        "gradfun=3:30,format=yuv420p10le",
    '-preset', 'p7',  # Максимальное качество
    '-b:v', f'{video_bitrate}',  
    '-maxrate', f'{maxrate}',  
    '-bufsize', f'{bufsize}',  
    '-colorspace', color_space,
    '-color_primaries', color_primaries,
    '-color_trc', color_trc,
    # '-spatial-aq', '1',
    # '-temporal-aq', '1',
    # '-aq-strength', '20',  # Максимальная адаптивная компрессия
    # '-rc', 'vbr',
    # '-cq', '16',  # Чистейшее качество (можно пробовать 14 или 12)
    # '-multipass', 'fullres',  
    # '-bf', '7',
    # '-refs', '7',
    # '-g', '500',
    # '-rc-lookahead', '64',
    # '-deblock', '-3:-3',
    # '-tag:v', 'av01',
    '-movflags', '+faststart',
    '-c:a', 'aac',
    '-b:a', f"{int(audio_bitrate)}k",
    '-ac', '2',
    '-map_metadata', '-1',
    '-metadata', f'description={CONFIG.description}',
    '-metadata', f'title={CONFIG.description}',
    output_file
]





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
        log(f'Файл без водяной метки {no_wm_output_file} уже существует. Пропускаем обработку.', "INFO")
        return

    log(f'Обработка файла без водяной метки: {base_name}_wwm.mp4', "INFO")

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
    
    print(metadata)
    
    if metadata.codec is None:
        log(f'Не удалось получить метаданные для {input_file}', "ERROR")
        return

    # Оценка размера видео и аудио
    target_size_gb = CONFIG.max_file_size_gb
    if metadata.duration / 60 > CONFIG.threshold_minutes:  # Если длительность видео больше порога
        log(f"Длина видео превышает {CONFIG.threshold_minutes} минут. "
            f"Расчет битрейта для достижения целевого размера...", "INFO")
        video_bitrate = adjust_bitrate_to_size(
            input_file, CONFIG.static_watermark, metadata.duration, metadata.audio_bitrate, target_size_gb, CONFIG.default_video_bitrate)

        # Рассчитываем maxrate и bufsize только для адаптированного битрейта
        maxrate, bufsize = calculate_maxrate_and_bufsize(video_bitrate)
    else:
        log(f"Длина видео менее {CONFIG.threshold_minutes} минут. "
            f"Установка битрейта(Мбит/с) max/min/avg: 100/0/12, размер буфера: 200 Мбит...", "INFO")
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
        log("Неверный режим обработки. Выберите 1 или 2.", "ERROR")

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
        log("Неверный режим обработки. Выберите 1 или 2.", "ERROR")
        return

    processed_any = False

    for file in os.listdir(CONFIG.input_dir):
        file_path = os.path.join(CONFIG.input_dir, file)
        
        if os.path.isfile(file_path) and file.lower().endswith(('mkv', 'mp4', 'avi')):
            base_name = os.path.splitext(file)[0]
            process_video(file_path, base_name, mode)
            processed_any = True

    if not processed_any:
        log("Не найдено файлов для обработки.", "INFO")

    # Завершение работы
    log("Все файлы уже обработаны или пропущены.", "SUCCESS")
    input("Нажмите Enter для выхода...")

if __name__ == "__main__":
    main()