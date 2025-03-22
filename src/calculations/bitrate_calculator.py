# src/calculations/bitrate_calculator.py

from src.config import CONFIG
from src.utils.logger import logger

class BitrateCalculator:
    def __init__(self, target_size_gb=None):
        self.target_size_gb = target_size_gb or CONFIG.max_file_size_gb

    def calculate_sizes(self, duration, video_bitrate, audio_bitrate=None):
        # Используем значение из конфига как максимальное
        audio_bitrate = min(
            audio_bitrate or CONFIG.target_audio_bitrate, 
            CONFIG.target_audio_bitrate  # Максимальный битрейт из конфига [[6]]
        )
        
        video_size = (video_bitrate * duration) / (8 * 1024 * 1024)  # бит/с → МБ
        audio_size = (audio_bitrate * 1000 * duration) / (8 * 1024 * 1024)  # кбит/с → МБ
        return video_size, audio_size

    def adjust_bitrate_to_size(
        self,
        duration: float,
        audio_bitrate: int,
        target_size_gb: float
    ) -> tuple[int, int, int]:
        MIN_VIDEO_BITRATE = 1 * 10**6  # 1 Мбит/с
        target_size_bytes = target_size_gb * 1024**3
        current_bitrate = CONFIG.default_video_bitrate * 10**6
        
        while current_bitrate > MIN_VIDEO_BITRATE:  # Минимум 1 Мбит/с [[8]]
            video_size, audio_size = self.calculate_sizes(
                duration,
                current_bitrate,
                audio_bitrate
            )
            total_size = (video_size + audio_size) * 1024**2  # в байты
            
            if total_size <= target_size_bytes:
                maxrate, bufsize = self.calculate_maxrate_and_bufsize(current_bitrate)
                logger.success(f"Битрейт оптимизирован: {current_bitrate/1e6:.2f} Mbps")
                return current_bitrate, maxrate, bufsize
                
            current_bitrate = int(current_bitrate * 0.99)  # Уменьшаем шаг до 5% [[9]]
            logger.warning(
                f"Текущий расчетный размер: {total_size / 1024**3:.2f} GB "
                f"(Видео: {video_size:.2f} MB, Аудио: {audio_size:.2f} MB). "
                f"Снижение битрейта до {current_bitrate/1e6:.2f} Mbps"
            )
        
        if current_bitrate <= MIN_VIDEO_BITRATE:
            logger.error("Достигнут минимальный битрейт! Результат может быть некорректным")
        logger.error("Не удалось подобрать битрейт!")
        
        return current_bitrate, 0, 0

    @staticmethod
    def calculate_maxrate_and_bufsize(video_bitrate):
        """Расчет maxrate и bufsize"""
        maxrate = int(video_bitrate * 1.2)
        bufsize = int(maxrate * 1.6)
        return maxrate, bufsize