import os
import yaml
from dataclasses import dataclass

@dataclass
class AppConfig:
    input_dir: str
    output_dir: str
    no_wm_output_dir: str
    static_watermark: str
    ffmpeg_path: str
    description: str
    threshold_minutes: int
    max_file_size_gb: float
    default_video_bitrate: int  # в Мбит/с
    target_audio_bitrate: int  # в кбит/с
    long_video_encoder: str
    short_video_encoder: str

    def validate(self):
        """Валидация конфигурации"""
        self._validate_paths()
        self._validate_numerical_ranges()

    def _validate_paths(self):
        # Проверка существования директорий
        for path in [self.input_dir, self.output_dir, self.no_wm_output_dir]:
            if not os.path.exists(path):
                os.makedirs(path)
                print(f"Создана директория: {path}")
        
        # Проверка водяного знака
        if not os.path.exists(self.static_watermark):
            raise FileNotFoundError(f"Файл водяного знака не найден: {self.static_watermark}")

    def _validate_numerical_ranges(self):
        if self.threshold_minutes <= 0:
            raise ValueError("threshold_minutes должно быть больше 0")
        if self.max_file_size_gb <= 0:
            raise ValueError("max_file_size_gb должно быть больше 0")
        if self.default_video_bitrate <= 0:
            raise ValueError("default_video_bitrate должно быть больше 0")
        if self.target_audio_bitrate <= 0:
            raise ValueError("target_audio_bitrate должно быть больше 0")
    
    # ДОБАВЛЕНО: Валидация значений кодеров
    def _validate_encoders(self):
        valid_encoders = {"av1_nvenc", "hevc_nvenc"}
        if self.long_video_encoder not in valid_encoders:
            raise ValueError(f"Недопустимое значение для long_video_encoder: {self.long_video_encoder}")
        if self.short_video_encoder not in valid_encoders:
            raise ValueError(f"Недопустимое значение для short_video_encoder: {self.short_video_encoder}")

def load_config() -> AppConfig:
    """Загрузка и валидация конфигурации"""
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Преобразование путей в абсолютные
        config['input_dir'] = os.path.abspath(config['input_dir'])
        config['output_dir'] = os.path.abspath(config['output_dir'])
        config['no_wm_output_dir'] = os.path.abspath(config['no_wm_output_dir'])
        config['static_watermark'] = os.path.abspath(config['static_watermark'])
        config['ffmpeg_path'] = os.path.abspath(config['ffmpeg_path'])

        # Создание объекта конфигурации
        app_config = AppConfig(**config)
        app_config.validate()
        return app_config

    except FileNotFoundError:
        raise SystemExit("config.yaml не найден в корне проекта")
    except yaml.YAMLError as e:
        raise SystemExit(f"Ошибка в config.yaml: {e}")
    except TypeError as e:
        raise SystemExit(f"Неполный config.yaml: {e}")

# Глобальный экземпляр конфига
CONFIG = load_config()