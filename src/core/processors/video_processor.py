# src/core/processors/video_processor.py
import os
import subprocess
import re
import tqdm
import sys

from src.config import CONFIG
from src.utils.logger import logger
from src.core.calculations.bitrate_calculator import BitrateCalculator
from src.utils.get_metadata import GetVideoMetadata

class VideoProcessor:
    def __init__(self, metadata: GetVideoMetadata, bitrate_calculator: BitrateCalculator):
        self.metadata = metadata
        self.bitrate_calculator = bitrate_calculator
        self.adjusted_audio_bitrate = min(
            self.metadata.audio_bitrate,
            CONFIG.target_audio_bitrate
        )
        self.current_encoder = None 
        self._setup_bitrates()

    def _setup_bitrates(self):
        """Инициализация параметров битрейта на основе метаданных"""
        if self.metadata.duration / 60 > CONFIG.threshold_minutes:
            logger.info(f"Длина видео превышает {CONFIG.threshold_minutes} минут. Расчет битрейта...")
            
            self.current_encoder = CONFIG.long_video_encoder
            logger.info(f"Выбран кодер для длинного видео: {self.current_encoder}")
            
            calc_result = self.bitrate_calculator.adjust_bitrate_to_size(
                duration=self.metadata.duration,
                audio_bitrate=self.metadata.audio_bitrate,
                target_size_gb=CONFIG.max_file_size_gb,
            )
            self.video_bitrate, self.maxrate, self.bufsize = calc_result
        else:
            logger.info(f"Длина видео менее {CONFIG.threshold_minutes} минут. Установка стандартного битрейта...")
            
            self.current_encoder = CONFIG.short_video_encoder
            logger.info(f"Выбран кодер для короткого видео: {self.current_encoder}")
            
            self.video_bitrate = CONFIG.default_video_bitrate
            self.maxrate = 100 * 10**6  # 100 Мбит/с
            self.bufsize = 200 * 10**6  # 200 Мбит

    def _run_ffmpeg_with_progress(self, command, total_duration):
        """Запуск FFmpeg с рабочим прогресс-баром"""
        # Добавляем обязательные параметры для вывода прогресса
        command = [
            CONFIG.ffmpeg_path,
            "-y",
            # "-hide_banner",
            "-loglevel", "info",  # Включаем вывод информации
            "-stats",             # Включаем статистику
            *command         # Оставляем остальные параметры
        ]
        
        # logger.debug(f"Команда FFmpeg: {' '.join(command)}")


        progress_bar = tqdm.tqdm(
            total=int(total_duration),
            unit="s",
            desc="Обработка видео",
            dynamic_ncols=True,
            bar_format="{l_bar}{bar}| {n:.0f}s/{total}s [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
        )

        try:
            process = subprocess.Popen(
                command,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,  # Важно для избежания блокировок
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace'
            )

            fps = 0
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                
                # Выводим строку в терминал
                # sys.stderr.write(line)
                # sys.stderr.flush()

                # Парсим время из двух форматов:
                # 1. Стандартный вывод времени
                time_match = re.search(
                    r"time=(\d+):(\d+):(\d+\.\d+)", 
                    line.replace(",", ".")
                )
                
                # 2. Альтернативный формат для коротких видео
                if not time_match:
                    time_match = re.search(
                        r"time=(\d+):(\d+\.\d+)", 
                        line.replace(",", ".")
                    )
                    if time_match:
                        m, s = map(float, time_match.groups())
                        elapsed = int(m * 60 + s)
                    else:
                        elapsed = None
                else:
                    h, m, s = map(float, time_match.groups())
                    elapsed = int(h * 3600 + m * 60 + s)

                # Обновляем прогресс
                if elapsed is not None:
                    progress_bar.n = min(elapsed, int(total_duration))
                    progress_bar.refresh()

                # Парсим FPS
                fps_match = re.search(r"fps\s*=\s*(\d+)", line)
                if fps_match:
                    fps = int(fps_match.group(1))
                    progress_bar.set_postfix({"fps": fps})

            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, 
                    ' '.join(command)
                )

        finally:
            progress_bar.close()
            process.terminate()
        
    def _build_watermark_command(self, input_file: str, output_path: str) -> list:
        """Сборка команды для обработки с водяным знаком"""
        # Определяем формат пикселей в зависимости от кодера
        pix_fmt = "p010le" if self.current_encoder == "av1_nvenc" else "yuv420p10le"
        return [
            # Входные файлы
            "-hwaccel", "cuda",
            "-c:v", self._get_input_decoder(),
            "-i", input_file,
            "-i", CONFIG.static_watermark,

            # Фильтры
            "-filter_complex", self._watermark_filter,
            "-pix_fmt", pix_fmt,

            # Параметры кодирования
            *self._encoding_parameters,

            # Выходной файл
            output_path
        ]

    def _build_base_command(self, input_file: str, output_path: str) -> list:
        """Сборка базовой команды без водяного знака"""
        return [
            # Входные файлы
            "-hwaccel", "cuda",
            "-c:v", self._get_input_decoder(),
            "-i", input_file,

            # Параметры кодирования
            *self._encoding_parameters,

            # Выходной файл
            output_path
        ]

    @property
    def _encoding_parameters(self) -> list:
        """Общие параметры кодирования, зависящие от выбранного кодера."""
        # Общие параметры для аудио и контейнера
        common_params = [
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-b:a", f"{self.adjusted_audio_bitrate}k",
            "-ac", "2",
            "-map_metadata", "-1",
            "-metadata", f"description={CONFIG.description}",
            "-metadata", f"title={CONFIG.description}"
        ]

        if self.current_encoder == "av1_nvenc":
            # Параметры для AV1 с исправленным синтаксисом
            av1_params = [
                "-c:v", "av1_nvenc",
                "-preset", "p7",
                "-multipass", "fullres",
                "-rc", "vbr",
                "-b:v", f"{self.video_bitrate}",
                "-maxrate", f"{self.maxrate}",
                "-bufsize", f"{self.bufsize}",
                "-rc-lookahead", "240",
                "-spatial-aq", "true",
                "-enable-ref-frame-mvs", "true",
                "-b_ref_mode", "each",
                # "-weighted_pred", "true",
                # Цветовые параметры
                "-colorspace", self.metadata.color_space,
                "-color_primaries", self.metadata.color_primaries,
                "-color_trc", self.metadata.color_trc,
                "-color_range", self.metadata.color_range,
            ]
            return av1_params + common_params

        elif self.current_encoder == "hevc_nvenc":
            # Параметры для HEVC (здесь все было в порядке)
            hevc_params = [
                "-c:v", "hevc_nvenc",
                "-preset", "p7",
                "-profile:v", "main10",
                "-rc", "vbr",
                "-b:v", f"{self.video_bitrate}",
                "-maxrate", f"{self.maxrate}",
                "-bufsize", f"{self.bufsize}",
                "-multipass", "fullres",
                "-rc-lookahead", "64",
                "-aq-strength", "15",
                "-spatial-aq", "1",
                "-temporal-aq", "1",
                "-b_ref_mode", "each",
                "-nonref_p", "1",
                "-tag:v", "hvc1",
                "-colorspace", self.metadata.color_space,
                "-color_primaries", self.metadata.color_primaries,
                "-color_trc", self.metadata.color_trc,
                "-color_range", self.metadata.color_range,
            ]
            return hevc_params + common_params
        
        else:
            raise ValueError(f"Неподдерживаемый кодер указан в конфигурации: {self.current_encoder}")

    @property
    def _watermark_filter(self) -> str:
        """Фильтр для добавления водяного знака"""
        # Определяем конечный формат в зависимости от кодера для лучшей производительности
        output_format = "p010le" if self.current_encoder == "av1_nvenc" else "yuv420p10le"

        return (
            "[1:v]scale=iw*0.09:ih*0.09,"
            "zscale=rangein=full:range=limited,"
            "format=rgba[watermark];"
            "[0:v][watermark]overlay="
            "x='max(main_w - w - (w/3.5), 0)':"
            "y='max((w/2.5) - (h/2), 0)'[overlayed_video];"
            f"[overlayed_video]format={output_format}"
        )

    def _get_input_decoder(self) -> str:
        """Определение декодера для входного видео"""
        codec = self.metadata.codec.lower()
        return (
            "hevc_cuvid" if codec == "hevc" else
            "h264_cuvid" if codec == "h264" else
            "auto"
        )

    def process_with_watermark(self, input_file: str, output_path: str):
        """Обработка видео с водяным знаком"""
        if os.path.exists(output_path):
            logger.info(f"Файл с водяным знаком {output_path} уже существует. Пропускаем.")
            return

        logger.info(f"Начало обработки с водяным знаком: {os.path.basename(input_file)}")
        command = self._build_watermark_command(input_file, output_path)
        logger.debug(f"Команда FFmpeg: {' '.join(command)}")
        self._run_ffmpeg_with_progress(command, self.metadata.duration)

    def process_without_watermark(self, input_file: str, output_path: str):
        """Обработка видео без водяного знака"""
        if os.path.exists(output_path):
            logger.info(f"Файл без водяного знака {output_path} уже существует. Пропускаем.")
            return

        logger.info(f"Начало обработки без водяного знака: {os.path.basename(input_file)}")
        command = self._build_base_command(input_file, output_path)
        logger.debug(f"Команда FFmpeg: {' '.join(command)}")
        self._run_ffmpeg_with_progress(command, self.metadata.duration)