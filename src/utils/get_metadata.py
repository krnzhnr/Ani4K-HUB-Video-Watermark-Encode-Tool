import subprocess
import os
from colorama import Fore

class GetVideoMetadata:
    def __init__(self, input_file):
        self.input_file = input_file
        self.codec = None
        self.duration = 0.0
        self.audio_bitrate = 0.0
        self.color_space = 'bt709'
        self.color_primaries = 'bt709'
        self.color_trc = 'bt709'
        self.color_range = 'tv'
        self.is_valid = False
        self.extract()

    def extract(self):
        """Извлекает метаданные из видеофайла"""
        try:
            # Проверка существования файла
            if not os.path.exists(self.input_file):
                raise FileNotFoundError(f"Файл {self.input_file} не найден")

            # Извлечение кодека
            self.codec = self._run_ffprobe(
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name"
            ).strip()

            # Извлечение длительности
            duration_str = self._run_ffprobe(
                "-show_entries", "format=duration"
            ).strip()
            self.duration = float(duration_str) if duration_str else 0.0

            # Извлечение аудио битрейта
            audio_bitrate_str = self._run_ffprobe(
                "-select_streams", "a:0",
                "-show_entries", "stream=bit_rate"
            ).strip()
            self.audio_bitrate = (float(audio_bitrate_str) / 1000) if audio_bitrate_str else 0.0  # кбит/с

            # Извлечение параметров цвета
            self.color_space = self._run_ffprobe(
                "-select_streams", "v:0",
                "-show_entries", "stream=color_space"
            ).strip() or 'bt709'
            
            self.color_primaries = self._run_ffprobe(
                "-select_streams", "v:0",
                "-show_entries", "stream=color_primaries"
            ).strip() or 'bt709'
            
            self.color_trc = self._run_ffprobe(
                "-select_streams", "v:0",
                "-show_entries", "stream=color_transfer"
            ).strip() or 'bt709'
            
            self.color_range = self._run_ffprobe(
                "-select_streams", "v:0",
                "-show_entries", "stream=color_range"
            ).strip() or 'tv'

            self.is_valid = True
        except Exception as e:
            print(f"{Fore.RED}Ошибка извлечения метаданных: {str(e)}{Fore.RESET}")

    def _run_ffprobe(self, *args):
        """Вспомогательный метод для вызова ffprobe"""
        command = [
            "ffprobe",
            "-v", "error",
            "-of", "default=noprint_wrappers=1:nokey=1",
            self.input_file
        ] + list(args)
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.stdout.decode().strip()

    def __repr__(self):
        return (f"VideoMetadata(codec={self.codec}, duration={self.duration}s, "
                f"audio_bitrate={self.audio_bitrate}kbit/s, color_space={self.color_space}, "
                f"color_primaries={self.color_primaries}, color_trc={self.color_trc}, "
                f"color_range={self.color_range})")