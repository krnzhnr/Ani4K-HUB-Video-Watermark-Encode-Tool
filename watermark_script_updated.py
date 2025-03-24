import os
from colorama import Fore, Style, init
from src.config import CONFIG
from src.utils.logger import logger
from src.core.calculations.bitrate_calculator import BitrateCalculator
from src.utils.get_metadata import GetVideoMetadata
from src.core.processors.video_processor import VideoProcessor
from src.utils.cli.cli import CLIInterface

init(autoreset=True)

cli = CLIInterface()

def process_video(input_file: str, base_name: str, mode: int):
    metadata = GetVideoMetadata(input_file)
    if not metadata.codec:
        logger.error(f'Не удалось получить метаданные для {input_file}')
        return

    cli.print_process_header(os.path.basename(input_file))
    processor = VideoProcessor(metadata, BitrateCalculator())

    output_wm = os.path.join(CONFIG.output_dir, f'[Ani4KHUB] {base_name}_watermarked.mp4')
    output_no_wm = os.path.join(CONFIG.no_wm_output_dir, f'[Ani4KHUB] {base_name}_wwm.mp4')

    try:
        if mode == 1:
            processor.process_with_watermark(input_file, output_wm)
            processor.process_without_watermark(input_file, output_no_wm)
        elif mode == 2:
            processor.process_with_watermark(input_file, output_wm)
    except Exception as e:
        logger.error(f"Ошибка обработки файла {input_file}: {str(e)}")

def main():
    cli.print_app_header()

    modes = {
        1: "Обработка в двух вариантах (с водяным знаком и без)",
        2: "Только с водяным знаком"
    }
    cli.print_mode_selection(modes)
    
    try:
        mode = int(input("Введите номер режима: "))
        if mode not in [1, 2]:
            raise ValueError
    except ValueError:
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

    cli.print_footer()

    input("Дважды нажмите Enter для выхода...")

if __name__ == "__main__":
    main()