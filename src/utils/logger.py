# src/utils/logger.py
import logging
import colorama
from colorama import Fore, Style
from tqdm import tqdm
import os
from pathlib import Path
from datetime import datetime

# Инициализация colorama
colorama.init(autoreset=True)

# Создаем пользовательский уровень SUCCESS
logging.addLevelName(logging.INFO + 1, 'SUCCESS')
SUCCESS = logging.INFO + 1

class TqdmLoggingHandler(logging.Handler):
    """Обработчик логов для совместимости с tqdm"""
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg, end='\n')
            self.flush()
        except Exception:
            self.handleError(record)

class ColorFormatter(logging.Formatter):
    """Форматирование с цветами для консоли"""
    format_template = (
        "%(asctime)s | %(levelname)-7s | %(message)s"
    )
    
    # Цвета для уровней логирования
    level_colors = {
        'DEBUG': Fore.LIGHTBLACK_EX,
        'INFO': Fore.WHITE,
        'SUCCESS': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }

    def format(self, record):
        levelname = record.levelname
        message = super().format(record)
        
        # Добавляем цвет для уровня логирования
        if levelname in self.level_colors:
            message = self.level_colors[levelname] + message
        
        return message

def setup_logger():
    """Создает уникальный лог-файл для каждого запуска"""
    # Генерация имени файла с временной меткой
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"encode_session_{timestamp}.log"
    log_file_path = log_dir / log_filename

    # Настройка логгера
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Удаляем старые обработчики
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Консольный обработчик с tqdm
    console_handler = TqdmLoggingHandler()
    console_formatter = ColorFormatter("%(asctime)s | %(levelname)-8s | %(message)s")
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG)
    
    # Файловый обработчик с уникальным именем
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
# Глобальный логгер
logger = setup_logger()

# Добавляем метод success
def success(self, message, *args, **kwargs):
    self._log(SUCCESS, message, args, **kwargs)

logging.Logger.success = success