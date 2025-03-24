# src/utils/cli/cli.py
from colorama import Fore, Style, init
from typing import Optional

class CLIInterface:
    def __init__(self, app_name: str = "Ani4K HUB Watermarker", width: int = 100, 
                line_char: str = "=", accent_color: str = Fore.CYAN):
        """
        Инициализация интерфейса
        :param app_name: Название приложения
        :param width: Ширина элементов
        :param line_char: Символ для линий
        :param accent_color: Основной цвет акцентов
        """
        init(autoreset=True)
        self.app_name = app_name
        self.width = width
        self.line_char = line_char
        self.accent_color = accent_color
        self.title_color = Fore.YELLOW

    def _create_line(self, color: Optional[str] = None) -> str:
        """Создает горизонтальную линию"""
        color = color or self.accent_color
        return f"{color}{self.line_char * self.width}"

    def print_app_header(self):
        """Выводит главный заголовок приложения"""
        print()
        print(self._create_line())
        print(f"{self.title_color}{f' {self.app_name} ':-^{self.width}}")
        print(f"{self._create_line()}\n")

    def print_section(self, title: str, color: Optional[str] = None):
        """Выводит секцию с заголовком"""
        color = color or self.accent_color
        print(f"\n{color}{title:^{self.width}}")
        print(self._create_line(color))

    def print_process_header(self, filename: str):
        """Заголовок для начала обработки файла"""
        print(f"\n{self._create_line(Fore.CYAN)}")
        print(f"{Fore.LIGHTYELLOW_EX}🚀 Обработка файла: {filename}")
        print(f"{self._create_line(Fore.CYAN)}\n")

    def print_footer(self, message: str = "Завершено"):
        """Нижний колонтитул"""
        print(f"\n{self._create_line(Fore.GREEN)}")
        print(f"{Fore.LIGHTGREEN_EX}{message:^{self.width}}")
        print(self._create_line(Fore.GREEN))

    def print_spacer(self, lines: int = 1):
        """Пустые строки-разделители"""
        print("\n" * (lines - 1))

    def wrap_in_box(self, text: str, color: Optional[str] = None) -> str:
        """Оборачивает текст в декоративную рамку"""
        color = color or self.accent_color
        lines = text.split('\n')
        box = [
            self._create_line(color),
            *[f"{color}║ {Fore.RESET}{line.ljust(self.width - 4)} {color}║" for line in lines],
            self._create_line(color)
        ]
        return "\n".join(box)

    def print_mode_selection(self, modes: dict, title: str = "Режим обработки"):
        """Простой вывод меню с рамкой"""
        menu_lines = [title]
        for num, desc in modes.items():
            menu_lines.append(f" {num} - {desc}")
        
        print(self.wrap_in_box("\n".join(menu_lines)))
    
    def divider(self):
        """Публичный метод для вывода разделителя с пустыми строками"""
        print(f"\n{self._create_line()}\n")