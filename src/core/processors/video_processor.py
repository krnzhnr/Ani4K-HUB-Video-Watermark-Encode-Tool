# src/core/processors/video_processor.py
import os
import subprocess
import re
import tqdm
from typing import Optional

from src.config import CONFIG
from src.utils.logger import logger
from src.core.calculations.bitrate_calculator import BitrateCalculator
from src.utils.get_metadata import GetVideoMetadata


class VideoProcessor:
    def __init__(self, metadata: GetVideoMetadata, bitrate_calculator: BitrateCalculator):
        self.metadata = metadata
        self.bitrate_calculator = bitrate_calculator
        self._setup_bitrates()

    def _setup_bitrates(self):
        """Инициализация параметров битрейта на основе метаданных"""
        if self.metadata.duration / 60 > CONFIG.threshold_minutes:
            logger.info(f"Длина видео превышает {CONFIG.threshold_minutes} минут. Расчет битрейта...")
            calc_result = self.bitrate_calculator.adjust_bitrate_to_size(
                duration=self.metadata.duration,
                audio_bitrate=self.metadata.audio_bitrate,
                target_size_gb=CONFIG.max_file_size_gb,
            )
            self.video_bitrate, self.maxrate, self.bufsize = calc_result
        else:
            logger.info(f"Длина видео менее {CONFIG.threshold_minutes} минут. Установка стандартного битрейта...")
            self.video_bitrate = CONFIG.default_video_bitrate
            self.maxrate = 100 * 10**6  # 100 Мбит/с
            self.bufsize = 200 * 10**6  # 200 Мбит

    def _run_ffmpeg_with_progress(self, command, total_duration):
        """Запуск FFmpeg с рабочим прогресс-баром"""
        # Добавляем обязательные параметры для вывода прогресса
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "info",  # Включаем вывод информации
            "-stats",             # Включаем статистику
            *command[1:]          # Оставляем остальные параметры
        ]

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
        return [
            # Глобальные параметры
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",

            # Входные файлы
            "-hwaccel", "cuda",
            "-c:v", self._get_input_decoder(),
            "-i", input_file,
            "-i", CONFIG.static_watermark,

            # Фильтры
            "-filter_complex", self._watermark_filter,
            "-pix_fmt", "yuv420p10le",

            # Параметры кодирования
            *self._encoding_parameters,

            # Выходной файл
            output_path
        ]

    def _build_base_command(self, input_file: str, output_path: str) -> list:
        """Сборка базовой команды без водяного знака"""
        return [
            # Глобальные параметры
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",

            # Входные файлы
            "-c:v", self._get_input_decoder(),
            "-i", input_file,

            # Параметры кодирования
            *self._encoding_parameters,

            # Выходной файл
            output_path
        ]

    @property
    def _encoding_parameters(self) -> list:
        """Общие параметры кодирования"""
        return [
            "-c:v", "hevc_nvenc",
            "-preset", "p7",
            "-profile:v", "main10",
            "-b:v", f"{self.video_bitrate}",
            "-maxrate", f"{self.maxrate}",
            "-bufsize", f"{self.bufsize}",
            "-rc", "vbr",
            "-aq-strength", "15",
            "-spatial-aq", "1",
            "-temporal-aq", "1",
            "-rc-lookahead", "64",
            "-colorspace", self.metadata.color_space,
            "-color_primaries", self.metadata.color_primaries,
            "-color_trc", self.metadata.color_trc,
            "-color_range", self.metadata.color_range,
            "-tag:v", "hvc1",
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-b:a", f"{self.metadata.audio_bitrate}k",
            "-ac", "2",
            "-map_metadata", "-1",
            "-metadata", f"description={CONFIG.description}",
            "-metadata", f"title={CONFIG.description}"
        ]

    @property
    def _watermark_filter(self) -> str:
        """Фильтр для добавления водяного знака"""
        return (
            "[1:v]scale=iw*0.09:ih*0.09,"
            "zscale=rangein=full:range=limited,"
            "format=rgba[watermark];"
            "[0:v][watermark]overlay="
            "x='max(main_w - w - (w/3.5), 0)':"
            "y='max((w/2.5) - (h/2), 0)'[overlayed_video];"
            "[overlayed_video]format=yuv420p10le"
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