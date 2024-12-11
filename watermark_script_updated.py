import os
import subprocess
import logging
from colorama import Fore, init

init(autoreset=True)

# Параметры (загружаются из config.yaml)
input_dir = '.'
output_dir = 'WATERMARKED'
no_wm_output_dir = 'ENCODED_NO_WM'
static_watermark = 'Ani4KHUB.png'
description = 'Made by Ani4K HUB | t.me/ani4k_ru'

import yaml

# Загрузка конфигурации
with open('config.yaml', 'r', encoding='utf-8') as config_file:
    config = yaml.safe_load(config_file)

# Настройки из файла конфигурации
input_dir = config['input_dir']
output_dir = config['output_dir']
no_wm_output_dir = config['no_wm_output_dir']
static_watermark = config['static_watermark']
description = config['description']
SETTINGS = {
    "threshold_minutes": config['threshold_minutes'],
    "max_file_size_gb": config['max_file_size_gb'],
    "default_video_bitrate": config['default_video_bitrate'] * 10**6,  # Преобразуем из Мбит/с в биты/с,
    "target_audio_bitrate": config['target_audio_bitrate'],
}

# SETTINGS = {
#     "threshold_minutes": 30,  # Порог длины видео (минуты), после которого применяется расчет битрейта и сжатие аудио
#     "max_file_size_gb": 3.8,  # Максимальный размер выходного файла (ГБ)
#     "default_video_bitrate": 12 * 10**6,  # 12(МБ) - это фиксированный битрейт для коротких видео (бит/с)
#     "target_audio_bitrate": 256,  # Целевой битрейт аудио в кбит/с
# }

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
    color_map = {"INFO": Fore.BLUE, "SUCCESS": Fore.GREEN, "WARNING": Fore.YELLOW, "ERROR": Fore.RED}
    print(color_map.get(level, Fore.WHITE) + message)
    getattr(logging, level.lower(), logging.info)(message)

# Создание выходных директорий, если они не существуют
os.makedirs(output_dir, exist_ok=True)
os.makedirs(no_wm_output_dir, exist_ok=True)

def get_video_metadata(input_file):
    """
    Извлекает метаданные видеофайла, включая кодек, длительность, битрейт аудио и параметры цвета, с помощью ffprobe.
    Параметры цвета обрабатываются, если они не извлечены — используются значения по умолчанию.

    :param input_file: Путь к видеофайлу.
    :return: Кодек видео, длительность в секундах, битрейт аудио в кбит/с, параметры цвета.
    """

    try:
        # Извлекаем кодек
        codec = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1", input_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

        # Извлекаем длительность
        duration = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", input_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip())

        # Извлекаем битрейт аудио
        audio_bitrate = float(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1", input_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()) / 1000  # в кбит/с

        audio_bitrate = float(SETTINGS['target_audio_bitrate']) if audio_bitrate > float(SETTINGS['target_audio_bitrate']) else audio_bitrate

        # Извлекаем параметры цвета
        color_space = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=colorspace",
            "-of", "default=noprint_wrappers=1:nokey=1", input_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

        color_primaries = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_primaries",
            "-of", "default=noprint_wrappers=1:nokey=1", input_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

        color_trc = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_trc",
            "-of", "default=noprint_wrappers=1:nokey=1", input_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

        color_range = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_range",
            "-of", "default=noprint_wrappers=1:nokey=1", input_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

        # Логируем извлеченные параметры
        log(f"Извлеченные параметры цвета:"
            f"color_space -> {color_space}, "
            f"color_primaries -> {color_primaries}, "
            f"color_trc -> {color_trc}, "
            f"color_range -> {color_range}. "
            f"Для пустых параметров будут применены параметры по умолчанию.", "INFO")

        # Устанавливаем значения по умолчанию, если какие-то параметры не были извлечены
        color_space = color_space if color_space else 'bt709'
        color_primaries = color_primaries if color_primaries else 'bt709'
        color_trc = color_trc if color_trc else 'bt709'
        color_range = color_range if color_range else 'limited'

        return codec, duration, audio_bitrate, color_space, color_primaries, color_trc, color_range

    except Exception as e:
        log(f"Не удалось извлечь метаданные для {input_file}: {e}", "ERROR")
        return None, None, None, None, None, None, None

def calculate_sizes(duration, video_bitrate, audio_bitrate=None):
    """
    Оценивает размеры видео и аудиопотоков на основе длительности видео и битрейтов.

    :param duration: Длительность видео в секундах.
    :param video_bitrate: Битрейт видео в бит/с.
    :param audio_bitrate: Битрейт аудио в кбит/с. Если None, используется target_audio_bitrate.
    :return: Размер видео и аудио потоков в МБ.
    """
    
    audio_bitrate = SETTINGS["target_audio_bitrate"] or audio_bitrate  # Используем целевой битрейт, если текущий не указан
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
            log(f"Целевой размер достигнут: {total_size / (1024**3):.2f} GB. Битрейт (Мбит) max/min/avg: {maxrate_mbit:.2f}/0/{current_video_bitrate_mbit:.2f}, "
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

    maxrate = int(video_bitrate * 1.3)  # Максимальный битрейт — 1.25 раза больше обычного
    bufsize = maxrate * 1.8  # Размер буфера равен maxrate
    return maxrate, bufsize

# Функция для обработки видео
def process_video(input_file, base_name):
    """
    Обрабатывает видеофайл, добавляя водяной знак (если нужно) и сжимая его для соответствия целевому размеру файла.
    Создает два варианта: с водяным знаком и без.

    :param input_file: Путь к входному видеофайлу.
    :param base_name: Базовое имя выходного файла, используется для формирования имён с водяным знаком и без.
    """

    output_file = os.path.join(output_dir, f'[TG - Ani4K] {base_name}_watermarked.mp4')
    no_wm_output_file = os.path.join(no_wm_output_dir, f'[TG - Ani4K] {base_name}_wwm.mp4')

    # Проверка существования выходных файлов
    if os.path.exists(output_file) and os.path.exists(no_wm_output_file):
        log(f'Оба файла для {base_name} уже существуют. Пропускаем обработку.', "INFO")
        return
    elif os.path.exists(output_file):
        log(f'Файл с водяной меткой {output_file} уже существует. Отсутствует файл без водяной метки.', "WARNING")
    elif os.path.exists(no_wm_output_file):
        log(f'Файл без водяной метки {no_wm_output_file} уже существует. Отсутствует файл с водяной меткой.', "WARNING")

    # Получение метаданных
    codec, duration, audio_bitrate, color_space, color_primaries, color_trc, color_range = get_video_metadata(input_file)
    if codec is None:
        log(f'Не удалось получить метаданные для {input_file}', "ERROR")
        return

    # Оценка размера видео и аудио
    target_size_gb = SETTINGS["max_file_size_gb"]
    if duration / 60 > SETTINGS["threshold_minutes"]:  # Если длительность видео больше порога
        log(f"Длина видео превышает {SETTINGS['threshold_minutes']} минут. Расчет битрейта для достижения целевого размера...", "INFO")
        video_bitrate = adjust_bitrate_to_size(input_file, static_watermark, duration, audio_bitrate, target_size_gb, SETTINGS["default_video_bitrate"])

        # Рассчитываем maxrate и bufsize только для адаптированного битрейта
        maxrate, bufsize = calculate_maxrate_and_bufsize(video_bitrate)
    else:
        log(f"Длина видео менее {SETTINGS['threshold_minutes']} минут. Установка битрейта(Мбит/с) max/min/avg: 100/0/12, размер буфера: 200 Мбит...", "INFO")
        # Для коротких видео устанавливаем стандартный битрейт
        video_bitrate = SETTINGS["default_video_bitrate"]
        maxrate = 100 * 10**6  # 100 Мбит
        bufsize = 200 * 10**6  # 200 Мбит

    # Проверка и обработка файла с водяной меткой
    if not os.path.exists(output_file):
        log(f'Обработка файла с водяной меткой: {input_file}', "INFO")
        try:
            subprocess.run([
            'ffmpeg', '-c:v', 'hevc_cuvid', '-i', input_file, '-i', static_watermark, 
            '-pix_fmt', 'p010le', '-color_range', color_range,  # Используем параметр, извлеченный из метаданных
            '-filter_complex', "[1:v]scale=iw*0.09:ih*0.09[scaled_static];[0:v][scaled_static]overlay=x='main_w-w-68':y='64':format=auto,gradfun=2.5:24,format=yuv420p10le", 
            '-c:v', 'hevc_nvenc', '-preset', 'p7', '-profile:v', 'main10', '-b:v', f'{video_bitrate}', 
            '-maxrate', f'{maxrate}', '-bufsize', f'{bufsize}', '-colorspace', color_space, '-color_primaries', color_primaries, 
            '-color_trc', color_trc, '-rc-lookahead', '20', '-tag:v', 'hvc1', 
            '-movflags', '+faststart', '-c:a', 'aac', '-b:a', f"{audio_bitrate}k", '-ac', '2',
            '-map_metadata', '-1', '-metadata', f'description={description}', 
            '-metadata', f'title={description}', output_file
        ], check=True)
            log(f'Файл с водяной меткой сохранён как: {output_file}', "SUCCESS")
        except subprocess.CalledProcessError as e:
            log(f'Ошибка при обработке с водяной меткой: {e}', "ERROR")

    # Проверка и обработка файла без водяной метки
    if not os.path.exists(no_wm_output_file):
        log(f'Обработка файла без водяной метки: {input_file}', "INFO")
        try:
            subprocess.run([
            'ffmpeg', '-c:v', 'hevc_cuvid', '-i', input_file, 
            '-c:v', 'hevc_nvenc', '-preset', 'p7', '-profile:v', 'main10', 
            '-b:v', f'{video_bitrate}', '-maxrate', f'{maxrate}', '-bufsize', f'{bufsize}',
            '-colorspace', color_space, '-color_primaries', color_primaries, 
            '-color_trc', color_trc, '-color_range', color_range,  # Используем параметр, извлеченный из метаданных
            '-rc-lookahead', '20', '-tag:v', 'hvc1', 
            '-movflags', '+faststart', '-c:a', 'aac', '-b:a', f"{audio_bitrate}k", '-ac', '2', 
            '-map_metadata', '-1', '-metadata', f'title={description}', '-metadata', f'description={description}', 
            no_wm_output_file
        ], check=True)
            log(f'Файл без водяной метки сохранён как: {no_wm_output_file}', "SUCCESS")
        except subprocess.CalledProcessError as e:
            log(f'Ошибка при обработке без водяной метки: {e}', "ERROR")

# Применение функции ко всем видео в указанной директории
processed_any = False
for file in os.listdir(input_dir):
    file_path = os.path.join(input_dir, file)
    if os.path.isfile(file_path) and file.lower().endswith(('mkv', 'mp4', 'avi')):
        base_name = os.path.splitext(file)[0]
        process_video(file_path, base_name)
        processed_any = True

if not processed_any:
    log("Не найдено файлов для обработки.", "INFO")

# Завершение работы
log("Все файлы уже обработаны или пропущены.", "SUCCESS")
input("Нажмите Enter для выхода...")
