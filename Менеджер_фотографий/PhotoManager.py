import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk, colorchooser
from PIL import Image, ImageTk, ImageOps, ImageDraw, ImageFilter, ImageEnhance, ImageChops
import os
import math
import shutil
import json

class PhotoEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Менеджер фотографий")
        self.root.geometry("800x800")
        self.root.minsize(800, 600)
        
        # Настройка стилей
        self.style = ttk.Style()
        self.style.configure('TButton', font=('Arial', 10), padding=5)
        self.style.configure('Large.TButton', font=('Arial', 11, 'bold'), padding=8)
        self.style.configure('Active.TButton', background='#4a6ea9', foreground='white')
        
        # Цвета интерфейса
        self.bg_color = "#f0f0f0"
        self.toolbar_color = "#333333"
        self.button_color = "#4a6ea9"
        self.active_color = "#2c7be5"
        
        # Переменные приложения
        self.current_folder = "Главная"
        self.image_paths = []
        self.original_image = None
        self.display_image = None
        self.tk_images = []
        self.drawing_mode = False
        self.erase_mode = False
        self.crop_mode = False
        self.last_x, self.last_y = None, None
        self.scale_factor = 1.0
        self.original_size = None
        self.brush_size = 10
        self.brush_color = "black"
        self.history = []
        self.folders = {"Главная": []}
        self.current_path = ["Главная"]
        self.image_offset_x = 0
        self.image_offset_y = 0
        self.temp_image = None
        self.current_filter = None
        self.filter_intensity = 1.0
        self.drawing_data = None
        self.crop_rect = None
        self.crop_start_x = None
        self.crop_start_y = None
        self.editor_window = None
        self.thumbnails_per_row = 4
        self.thumbnail_size = 200
        
        # Для навигации по изображениям
        self.current_image_index = 0
        self.nav_thumbnails_frame = None
        self.nav_thumbnails = []
        
        # Настройки стирания
        self.erase_smoothing = True
        self.erase_quality = 3
        self.last_erase_point = None

        # Настройка главного окна
        self.root.configure(bg=self.bg_color)
        
        # Создание интерфейса
        self.create_main_interface()
        
        # Загрузка сохраненных данных
        self.load_saved_data()
        
        # Привязка обработчика изменения размера окна
        self.root.bind("<Configure>", self.on_window_resize)

    def on_window_resize(self, event):
        """Обработчик изменения размера окна"""
        if event.widget == self.root:
            # Принудительно обновляем размещение миниатюр при изменении размера окна
            self.calculate_thumbnails_per_row()
            self.show_thumbnails()

    def calculate_thumbnails_per_row(self):
        """Вычисляет количество миниатюр в строке"""
        canvas_width = self.main_frame.winfo_width()
        if canvas_width > 0:
            # Увеличиваем количество столбцов при расширении окна
            self.thumbnails_per_row = max(2, canvas_width // (self.thumbnail_size + 20))
            # Если окно развернуто на весь экран, увеличиваем количество столбцов
            if self.root.state() == 'zoomed' or canvas_width > 1000:
                self.thumbnails_per_row = max(4, canvas_width // (self.thumbnail_size + 10))
            # Обновляем интерфейс
            self.show_thumbnails()

    def create_main_interface(self):
        """Создает основной интерфейс с миниатюрами"""
        # Панель инструментов
        self.toolbar_frame = tk.Frame(self.root, bg=self.toolbar_color, height=50)
        self.toolbar_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(self.toolbar_frame, text="Добавить фото", command=self.load_images, 
                  style='Large.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(self.toolbar_frame, text="Создать папку", command=self.create_folder, 
                  style='Large.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(self.toolbar_frame, text="Добавить папку", command=self.add_existing_folder,
                  style='Large.TButton').pack(side=tk.LEFT, padx=5)
        
        # Основная область с миниатюрами
        self.main_frame = tk.Frame(self.root, bg=self.bg_color)
        self.main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # Полоса прокрутки для миниатюр
        self.canvas = tk.Canvas(self.main_frame, bg="white")
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Фрейм для миниатюр внутри canvas
        self.thumbnail_frame = tk.Frame(self.canvas, bg="white")
        self.canvas.create_window((0, 0), window=self.thumbnail_frame, anchor="nw")
        
        # Привязка событий прокрутки
        self.thumbnail_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        # Прокрутка колесиком мыши
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        
        # Строка состояния
        self.status_bar = tk.Label(self.root, text="Готово", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def add_existing_folder(self):
        """Добавляет существующую папку с изображениями"""
        folder_path = filedialog.askdirectory(title="Выберите папку с изображениями")
        
        if folder_path:
            folder_name = os.path.basename(folder_path)
            
            # Проверяем, есть ли уже такая папка
            if folder_name in self.folders:
                messagebox.showerror("Ошибка", "Папка с таким именем уже существует!")
                return
                
            # Сканируем папку на наличие изображений
            image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
            image_files = []
            
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith(image_extensions):
                        full_path = os.path.join(root, file)
                        image_files.append(full_path)
            
            if not image_files:
                messagebox.showwarning("Предупреждение", "В выбранной папке не найдено изображений!")
                return
                
            # Добавляем папку и изображения
            self.folders[folder_name] = image_files
            self.show_thumbnails()
            messagebox.showinfo("Успех", f"Добавлена папка '{folder_name}' с {len(image_files)} изображениями")

    def on_mousewheel(self, event):
        """Прокрутка колесиком мыши"""
        if event.widget == self.canvas:  # Проверяем, что событие пришло от canvas
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def load_images(self):
        """Загружает изображения"""
        file_types = [('Изображения', '*.jpg *.jpeg *.png'), ('Все файлы', '*.*')]
        file_paths = filedialog.askopenfilenames(title="Выберите изображения", filetypes=file_types)
        
        if file_paths:
            for path in file_paths:
                if path not in self.folders[self.current_folder]:
                    self.folders[self.current_folder].append(path)
            
            self.show_thumbnails()
            messagebox.showinfo("Успех", f"Загружено {len(file_paths)} изображений")

    def create_folder(self):
        """Создает новую папку"""
        folder_name = simpledialog.askstring("Создать папку", "Введите имя папки:")
        if folder_name:
            if folder_name in self.folders:
                messagebox.showerror("Ошибка", "Папка с таким именем уже существует!")
                return

            self.folders[folder_name] = []
            self.show_thumbnails()
            messagebox.showinfo("Успех", f"Папка '{folder_name}' создана!")

    def open_folder(self, folder_name):
        """Открывает папку"""
        self.current_folder = folder_name
        self.show_thumbnails()

    def delete_image(self, image_path):
        """Удаляет изображение из приложения"""
        if not image_path:
            return
            
        if messagebox.askyesno("Подтверждение", "Вы уверены, что хотите удалить это изображение из приложения?"):
            try:
                # Удаляем из текущей папки
                if image_path in self.folders[self.current_folder]:
                    self.folders[self.current_folder].remove(image_path)
                    
                # Если изображение открыто, закрываем его
                if self.original_image and hasattr(self.original_image, 'filename') and self.original_image.filename == image_path:
                    self.original_image = None
                    self.display_image = None
                    self.image_canvas.delete("all")
                
                self.show_thumbnails()
                messagebox.showinfo("Успех", "Изображение удалено из приложения!")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить изображение:\n{str(e)}")

    def move_to_folder(self, image_path):
        """Перемещает изображение в папку"""
        if not image_path:
            return
            
        folder_name = simpledialog.askstring("Переместить в папку", "Введите имя папки:")
        if folder_name and folder_name in self.folders:
            # Создаем папку, если ее нет в файловой системе
            os.makedirs(folder_name, exist_ok=True)
            
            # Перемещаем файл
            try:
                dest_path = os.path.join(folder_name, os.path.basename(image_path))
                shutil.move(image_path, dest_path)
                
                # Обновляем данные
                if image_path in self.folders[self.current_folder]:
                    self.folders[self.current_folder].remove(image_path)
                self.folders[folder_name].append(dest_path)
                
                messagebox.showinfo("Успех", f"Изображение перемещено в папку '{folder_name}'!")
                self.show_thumbnails()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось переместить изображение:\n{str(e)}")
        elif folder_name:
            messagebox.showerror("Ошибка", f"Папка '{folder_name}' не существует!")

    def open_editor(self, image_path):
        """Открывает редактор для выбранного изображения"""
        if self.editor_window and self.editor_window.winfo_exists():
            self.editor_window.destroy()
            
        self.editor_window = tk.Toplevel(self.root)
        self.editor_window.title("Редактор изображений")
        self.editor_window.geometry("1500x800")
        self.editor_window.minsize(800, 600)
        
        # Находим индекс текущего изображения
        self.current_image_index = self.folders[self.current_folder].index(image_path)
        
        # Загружаем изображение
        try:
            self.original_image = Image.open(image_path)
            self.original_image.filename = image_path
            self.original_size = self.original_image.size
            self.scale_factor = 0.5  # Начальный масштаб 50%
            self.history = [self.original_image.copy()]
            
            # Создаем интерфейс редактора
            self.create_editor_interface()
            self.update_image_display()
            self.center_image(force=True)  # Принудительно центрируем изображение сразу после открытия
            self.update_navigation_thumbnails()
            
            # Привязка клавиш для навигации
            self.editor_window.bind("<Left>", lambda e: self.navigate_images(-1))
            self.editor_window.bind("<Right>", lambda e: self.navigate_images(1))
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть изображение:\n{str(e)}")
            self.editor_window.destroy()

    def navigate_images(self, direction):
        """Перемещается между изображениями в текущей папке"""
        if not self.folders[self.current_folder]:
            return
            
        new_index = self.current_image_index + direction
        
        # Проверяем границы
        if new_index < 0:
            new_index = len(self.folders[self.current_folder]) - 1
        elif new_index >= len(self.folders[self.current_folder]):
            new_index = 0
            
        self.current_image_index = new_index
        next_image_path = self.folders[self.current_folder][new_index]
        
        try:
            self.original_image = Image.open(next_image_path)
            self.original_image.filename = next_image_path
            self.original_size = self.original_image.size
            self.history = [self.original_image.copy()]
            
            self.update_image_display()
            self.center_image(force=True)  # Принудительно центрируем изображение после навигации
            self.update_navigation_thumbnails()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть следующее изображение:\n{str(e)}")

    def update_navigation_thumbnails(self):
        """Обновляет миниатюры для навигации по изображениям"""
        if not self.nav_thumbnails_frame:
            return
            
        # Очищаем предыдущие миниатюры
        for widget in self.nav_thumbnails_frame.winfo_children():
            widget.destroy()
        self.nav_thumbnails = []
        
        # Получаем список изображений в текущей папке
        image_list = self.folders[self.current_folder]
        if not image_list:
            return
            
        # Определяем индексы для отображения (текущее и соседние)
        total_images = len(image_list)
        indices = []
        
        # Добавляем предыдущие изображения
        for i in range(2, 0, -1):
            idx = (self.current_image_index - i) % total_images
            indices.append(idx)
        
        # Добавляем текущее изображение
        indices.append(self.current_image_index)
        
        # Добавляем следующие изображения
        for i in range(1, 3):
            idx = (self.current_image_index + i) % total_images
            indices.append(idx)
        
        # Создаем миниатюры
        for i, idx in enumerate(indices):
            try:
                img_path = image_list[idx]
                img = Image.open(img_path)
                img.thumbnail((80, 80))
                tk_img = ImageTk.PhotoImage(img)
                self.nav_thumbnails.append(tk_img)  # Сохраняем ссылку
                
                # Создаем фрейм для миниатюры
                frame = tk.Frame(self.nav_thumbnails_frame, bg="white", bd=1, relief=tk.SUNKEN)
                frame.pack(side=tk.LEFT, padx=5, pady=5)
                
                # Выделяем текущее изображение
                if idx == self.current_image_index:
                    frame.config(bg="#4a6ea9", bd=2, relief=tk.RAISED)
                
                # Миниатюра
                lbl = tk.Label(frame, image=tk_img, bg="white")
                lbl.image = tk_img
                lbl.pack(padx=5, pady=5)
                
                # Привязываем клик для перехода к изображению
                lbl.bind("<Button-1>", lambda e, path=img_path: self.open_editor(path))
                
            except Exception as e:
                print(f"Ошибка загрузки миниатюры {img_path}: {e}")

    def create_editor_interface(self):
        """Создает интерфейс редактора"""
        # Главный контейнер редактора
        main_container = tk.Frame(self.editor_window)
        main_container.pack(expand=True, fill=tk.BOTH)
        
        # Панель инструментов редактора
        editor_toolbar = tk.Frame(main_container, bg=self.toolbar_color, height=50)
        editor_toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # Кнопки редактора
        ttk.Button(editor_toolbar, text="Сохранить", command=self.show_save_options, 
                  style='Large.TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(editor_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        # Группа кнопок редактирования
        edit_btns = [
            ("Обрезать", self.toggle_crop_mode),
            ("Рисовать", self.toggle_draw_mode),
            ("Стереть", self.toggle_erase_mode),
            ("Повернуть 90°", lambda: self.rotate_image(90)),
            ("Отразить", self.mirror_image),
            ("Изменить размер", self.resize_image)
        ]
        
        for text, cmd in edit_btns:
            ttk.Button(editor_toolbar, text=text, command=cmd).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(editor_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        # Кнопка отмены
        ttk.Button(editor_toolbar, text="Отменить", command=self.undo).pack(side=tk.LEFT, padx=5)
        
        # Выбор цвета кисти
        self.color_btn = tk.Button(editor_toolbar, text="Цвет", bg=self.brush_color, fg="white",
                                 command=self.choose_brush_color)
        self.color_btn.pack(side=tk.LEFT, padx=5)
        
        # Слайдер размера кисти
        tk.Label(editor_toolbar, text="Размер:", bg=self.toolbar_color, fg="white").pack(side=tk.LEFT, padx=5)
        self.brush_size_slider = ttk.Scale(editor_toolbar, from_=1, to=50, value=self.brush_size, length=100,
                                         command=lambda v: setattr(self, 'brush_size', int(float(v))))
        self.brush_size_slider.pack(side=tk.LEFT, padx=5)
        
        # Кнопка фильтров с выпадающим меню
        self.filter_menu = tk.Menubutton(editor_toolbar, text="Фильтры", relief=tk.RAISED)
        self.filter_menu.pack(side=tk.LEFT, padx=5)
        self.filter_menu.menu = tk.Menu(self.filter_menu, tearoff=0)
        self.filter_menu["menu"] = self.filter_menu.menu
        
        filters = [
            ("Размытие", "blur"),
            ("Контур", "contour"),
            ("Детализация", "detail"),
            ("Тиснение", "emboss"),
            ("Резкость", "sharpen"),
            ("Сглаживание", "smooth")
        ]
        
        for name, filter_type in filters:
            self.filter_menu.menu.add_command(label=name, 
                                            command=lambda ft=filter_type: self.apply_filter(ft))
        
        # Основная область редактора с изображением
        editor_main = tk.Frame(main_container, bg=self.bg_color)
        editor_main.pack(expand=True, fill=tk.BOTH)
        
        # Информация о фотографии
        self.info_frame = tk.Frame(editor_main, bg=self.bg_color, height=30)
        self.info_frame.pack(side=tk.TOP, fill=tk.X)
        self.update_image_info()
        
        # Холст для изображения
        self.image_frame = tk.Frame(editor_main, bg="gray")
        self.image_frame.pack(expand=True, fill=tk.BOTH)
        
        self.image_canvas = tk.Canvas(self.image_frame, bg="gray", bd=0, highlightthickness=0)
        self.image_canvas.pack(expand=True, fill=tk.BOTH)
        
        # Панель управления масштабом
        control_frame = tk.Frame(editor_main, bg=self.bg_color)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        tk.Label(control_frame, text="Масштаб:").pack(side=tk.LEFT, padx=5)
        self.scale_slider = ttk.Scale(control_frame, from_=0.1, to=2.0, value=self.scale_factor, length=200,
                                    command=self.update_scale)
        self.scale_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Индикатор масштаба
        self.scale_label = tk.Label(control_frame, text=f"{int(self.scale_factor * 100)}%")
        self.scale_label.pack(side=tk.LEFT, padx=5)
        
        # Прокрутка колесиком мыши в редакторе
        self.image_canvas.bind("<MouseWheel>", self.on_editor_mousewheel)
        
        # Панель навигации по изображениям
        self.nav_thumbnails_frame = tk.Frame(editor_main, bg=self.bg_color, height=100)
        self.nav_thumbnails_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Подпись
        tk.Label(self.nav_thumbnails_frame, text="Навигация по изображениям (используйте стрелки ← →)", 
                bg=self.bg_color).pack(side=tk.TOP, anchor=tk.W, padx=10, pady=5)

    def update_image_info(self):
        """Обновляет информацию о текущем изображении"""
        for widget in self.info_frame.winfo_children():
            widget.destroy()
            
        if not self.original_image:
            return
            
        filename = os.path.basename(self.original_image.filename) if hasattr(self.original_image, 'filename') else "Новое изображение"
        size = f"{self.original_image.width} × {self.original_image.height} пикселей"
        
        tk.Label(self.info_frame, text=f"Файл: {filename}", bg=self.bg_color, font=('Arial', 10)).pack(side=tk.LEFT, padx=10)
        tk.Label(self.info_frame, text=f"Размер: {size}", bg=self.bg_color, font=('Arial', 10)).pack(side=tk.LEFT, padx=10)

    def show_save_options(self):
        """Показывает меню с вариантами сохранения"""
        if not self.original_image:
            messagebox.showerror("Ошибка", "Нет изображения для сохранения!")
            return
            
        menu = tk.Menu(self.editor_window, tearoff=0)
        menu.add_command(label="Сохранить на компьютер", command=self.save_to_computer)
        menu.add_command(label="Сохранить в приложении", command=self.save_to_app)
        menu.post(self.editor_window.winfo_pointerx(), self.editor_window.winfo_pointery())

    def save_to_computer(self):
        """Сохраняет изображение на компьютер"""
        if not self.original_image:
            return
            
        file_types = [('JPEG', '*.jpg'), ('PNG', '*.png'), ('Все файлы', '*.*')]
        file_path = filedialog.asksaveasfilename(
            title="Сохранить изображение",
            defaultextension=".png",
            filetypes=file_types
        )
        
        if file_path:
            try:
                # Если изображение было изменено (например, с прозрачностью)
                if hasattr(self, 'temp_image') and self.temp_image:
                    self.temp_image.save(file_path)
                else:
                    self.original_image.save(file_path)
                    
                messagebox.showinfo("Успех", "Изображение успешно сохранено на компьютере!")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить изображение:\n{str(e)}")

    def save_to_app(self):
        """Сохраняет изображение в приложении"""
        if not self.original_image:
            return
            
        try:
            # Если изображение было изменено (например, с прозрачностью)
            if hasattr(self, 'temp_image') and self.temp_image:
                image_to_save = self.temp_image
            else:
                image_to_save = self.original_image
            
            # Если изображение уже есть в приложении, обновляем его
            if hasattr(self.original_image, 'filename'):
                current_path = self.original_image.filename
                image_to_save.save(current_path)
                messagebox.showinfo("Успех", "Изображение обновлено в приложении!")
            else:
                # Иначе сохраняем в текущую папку
                file_name = simpledialog.askstring("Сохранение", "Введите имя файла (без расширения):")
                if file_name:
                    file_path = os.path.join(os.getcwd(), self.current_folder, f"{file_name}.png")
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    image_to_save.save(file_path)
                    
                    # Добавляем в текущую папку
                    if file_path not in self.folders[self.current_folder]:
                        self.folders[self.current_folder].append(file_path)
                    
                    messagebox.showinfo("Успех", "Изображение сохранено в приложении!")
                    self.show_thumbnails()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изображение:\n{str(e)}")

    def show_thumbnails(self):
        """Показывает миниатюры изображений и папок с визуальным разделением"""
        # Очищаем предыдущие миниатюры
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
        
        # Заголовок текущей папки
        tk.Label(self.thumbnail_frame, text=f"Текущая папка: {self.current_folder}", 
                bg="white", font=("Arial", 14, "bold")).grid(row=0, column=0, 
                columnspan=self.thumbnails_per_row, sticky="ew", pady=10)
        
        # Раздел "Доступные папки"
        folders_frame = tk.Frame(self.thumbnail_frame, bg="#f0f0f0", bd=2, relief=tk.GROOVE)
        folders_frame.grid(row=1, column=0, columnspan=self.thumbnails_per_row, sticky="ew", padx=5, pady=10)
        
        tk.Label(folders_frame, text="Доступные папки", bg="#f0f0f0", 
                font=("Arial", 12, "bold")).pack(side=tk.TOP, anchor=tk.W, padx=10, pady=5)
        
        # Контейнер для кнопок папок
        folders_buttons_frame = tk.Frame(folders_frame, bg="#f0f0f0")
        folders_buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Папки (кроме текущей)
        row, col = 0, 0
        for folder in sorted(self.folders.keys()):
            if folder != self.current_folder:
                btn = tk.Button(folders_buttons_frame, text=f"📁 {folder}", 
                              bg="#e6f3ff", fg="#333333",
                              font=("Arial", 10, "bold"),
                              relief=tk.RAISED, bd=2,
                              command=lambda f=folder: self.open_folder(f))
                btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
                col += 1
                if col >= min(4, self.thumbnails_per_row):  # Максимум 4 папки в строке
                    col = 0
                    row += 1
        
        # Раздел "Изображения в текущей папке"
        images_frame = tk.Frame(self.thumbnail_frame, bg="#f0f0f0", bd=2, relief=tk.GROOVE)
        images_frame.grid(row=2, column=0, columnspan=self.thumbnails_per_row, sticky="ew", padx=5, pady=10)
        
        tk.Label(images_frame, text=f"Изображения в папке '{self.current_folder}'", 
                bg="#f0f0f0", font=("Arial", 12, "bold")).pack(side=tk.TOP, anchor=tk.W, padx=10, pady=5)
        
        # Изображения
        row = 3
        col = 0
        for path in sorted(self.folders[self.current_folder]):
            try:
                img = Image.open(path)
                img.thumbnail((self.thumbnail_size, self.thumbnail_size))
                tk_img = ImageTk.PhotoImage(img)
                self.tk_images.append(tk_img)  # Сохраняем ссылку
                
                # Фрейм для миниатюры с тенью
                frame = tk.Frame(self.thumbnail_frame, bg="white", bd=2, relief=tk.RAISED)
                frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                
                # Миниатюра
                lbl = tk.Label(frame, image=tk_img, bg="white")
                lbl.image = tk_img
                lbl.pack(side=tk.TOP, padx=10, pady=10)
                
                # Информация об изображении
                info_frame = tk.Frame(frame, bg="white")
                info_frame.pack(side=tk.TOP, fill=tk.X)
                
                filename = os.path.basename(path)
                tk.Label(info_frame, text=filename, bg="white", font=("Arial", 10), 
                        wraplength=self.thumbnail_size).pack(anchor=tk.W)
                tk.Label(info_frame, text=f"{img.width}x{img.height}", bg="white").pack(anchor=tk.W)
                
                # Кнопки
                btn_frame = tk.Frame(frame, bg="white")
                btn_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
                
                ttk.Button(btn_frame, text="Редактировать", 
                          command=lambda p=path: self.open_editor(p)).pack(fill=tk.X, pady=2)
                ttk.Button(btn_frame, text="Переместить", 
                          command=lambda p=path: self.move_to_folder(p)).pack(fill=tk.X, pady=2)
                ttk.Button(btn_frame, text="Удалить", 
                          command=lambda p=path: self.delete_image(p)).pack(fill=tk.X, pady=2)
                
                col += 1
                if col >= self.thumbnails_per_row:
                    col = 0
                    row += 1
                
            except Exception as e:
                print(f"Ошибка загрузки изображения {path}: {e}")
                if path in self.folders[self.current_folder]:
                    self.folders[self.current_folder].remove(path)
        
        # Если папка пуста
        if not self.folders[self.current_folder]:
            tk.Label(self.thumbnail_frame, text="В этой папке нет изображений", 
                    bg="white", font=("Arial", 11)).grid(row=3, column=0, 
                    columnspan=self.thumbnails_per_row, pady=20)
    
        # Настраиваем растягивание колонок
        for i in range(self.thumbnails_per_row):
            self.thumbnail_frame.columnconfigure(i, weight=1)

    def on_editor_mousewheel(self, event):
        """Прокрутка колесиком мыши в редакторе"""
        if event.widget == self.image_canvas:  # Проверяем, что событие пришло от canvas
            if event.state & 0x1:  # Если зажата Ctrl - масштабирование
                if event.delta > 0:
                    self.scale_slider.set(min(2.0, self.scale_slider.get() + 0.1))
                else:
                    self.scale_slider.set(max(0.1, self.scale_slider.get() - 0.1))
            else:  # Обычная прокрутка
                self.image_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def update_scale(self, value):
        """Обновляет масштаб изображения"""
        self.scale_factor = float(value)
        self.scale_label.config(text=f"{int(self.scale_factor * 100)}%")
        self.update_image_display()
        self.center_image(force=True)  # Принудительно центрируем после изменения масштаба

    def resize_image(self):
        """Изменяет размер изображения"""
        if not self.original_image:
            return
            
        width = simpledialog.askinteger("Изменить размер", "Ширина (пиксели):", 
                                       initialvalue=self.original_image.width)
        if not width:
            return
            
        height = simpledialog.askinteger("Изменить размер", "Высота (пиксели):", 
                                        initialvalue=self.original_image.height)
        if not height:
            return
            
        self.save_state()
        
        try:
            self.original_image = self.original_image.resize((width, height), Image.LANCZOS)
            self.update_image_display()
            self.center_image(force=True)  # Принудительно центрируем после изменения размера
            self.update_image_info()
            self.status_bar.config(text=f"Размер изменен на {width}x{height} пикселей")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось изменить размер:\n{str(e)}")

    def _get_smooth_points(self, x1, y1, x2, y2):
        """Генерирует промежуточные точки для сглаживания"""
        points = []
        distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        steps = max(int(distance), 1)
        
        for i in range(steps + 1):
            t = i / steps
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            points.append((x, y))
            
        return points

    def toggle_erase_mode(self):
        """Включает/выключает режим стирания"""
        self.erase_mode = not self.erase_mode
        self.drawing_mode = False
        self.crop_mode = False
        
        if self.erase_mode:
            self.image_canvas.bind("<ButtonPress-1>", self.start_erase)
            self.image_canvas.bind("<B1-Motion>", self.erase_on_image)
            self.image_canvas.bind("<ButtonRelease-1>", self.stop_erase)
            self.image_canvas.config(cursor="circle")
        else:
            self.image_canvas.unbind("<ButtonPress-1>")
            self.image_canvas.unbind("<B1-Motion>")
            self.image_canvas.unbind("<ButtonRelease-1>")
            self.image_canvas.config(cursor="")

    def start_erase(self, event):
        """Начинает стирание"""
        if not self.original_image:
            return
            
        self.save_state()
        
        # Создаем копию изображения с альфа-каналом
        if self.original_image.mode != 'RGBA':
            self.temp_image = self.original_image.convert('RGBA')
        else:
            self.temp_image = self.original_image.copy()
        
        # Запоминаем начальную точку
        self.last_x = (event.x - self.image_offset_x) / self.scale_factor
        self.last_y = (event.y - self.image_offset_y) / self.scale_factor
        self.last_erase_point = (self.last_x, self.last_y)

    def erase_on_image(self, event):
        """Стирает часть изображения"""
        if not self.temp_image or not self.erase_mode:
            return

        # Рассчитываем текущие координаты
        x = (event.x - self.image_offset_x) / self.scale_factor
        y = (event.y - self.image_offset_y) / self.scale_factor

        if self.last_erase_point:
            # Создаем маску для стирания
            mask = Image.new('L', self.temp_image.size, 255)
            draw_mask = ImageDraw.Draw(mask)
            
            if self.erase_smoothing:
                # Рисуем сглаженную линию
                points = self._get_smooth_points(self.last_erase_point[0], self.last_erase_point[1], x, y)
                for px, py in points:
                    draw_mask.ellipse([px - self.brush_size/2, py - self.brush_size/2,
                                     px + self.brush_size/2, py + self.brush_size/2],
                                    fill=0)
            else:
                # Рисуем простую линию
                draw_mask.line([self.last_erase_point, (x, y)], 
                              fill=0,
                              width=self.brush_size)
            
            # Применяем маску к альфа-каналу
            alpha = self.temp_image.getchannel('A')
            alpha = ImageChops.darker(alpha, mask)
            self.temp_image.putalpha(alpha)
            
            # Обновляем отображение в зависимости от качества
            if self.erase_quality > 3 or event.x % 2 == 0:
                self.update_image_display(self.temp_image)
        
        # Сохраняем текущую точку
        self.last_erase_point = (x, y)

    def stop_erase(self, event):
        """Завершает стирание"""
        if self.temp_image is not None:
            self.original_image = self.temp_image.copy()
            self.temp_image = None
        
        self.last_erase_point = None
        self.last_x, self.last_y = None, None
        self.update_image_display()

    def center_image(self, force=False):
        """Центрирует изображение на холсте"""
        if not self.display_image:
            return
            
        img_width = self.display_image.width()
        img_height = self.display_image.height()
        
        canvas_width = self.image_canvas.winfo_width()
        canvas_height = self.image_canvas.winfo_height()
        
        # Принудительно обновляем смещение, если указано force=True
        if force or self.image_offset_x == 0 or self.image_offset_y == 0:
            self.image_offset_x = max((canvas_width - img_width) // 2, 0)
            self.image_offset_y = max((canvas_height - img_height) // 2, 0)
        
        self.image_canvas.delete("all")
        self.image_canvas.create_image(self.image_offset_x, self.image_offset_y, 
                                      anchor=tk.NW, image=self.display_image)

    def update_image_display(self, image=None):
        """Обновляет отображение изображения"""
        if image is None:
            image = self.original_image
            
        if not image:
            return
            
        # Масштабируем изображение для отображения
        width = int(image.width * self.scale_factor)
        height = int(image.height * self.scale_factor)
        display_img = image.resize((width, height), Image.LANCZOS)
        
        # Конвертируем для Tkinter
        self.display_image = ImageTk.PhotoImage(display_img)
        self.center_image()

    def toggle_crop_mode(self):
        """Включает/выключает режим обрезки"""
        self.crop_mode = not self.crop_mode
        self.drawing_mode = False
        self.erase_mode = False
        
        if self.crop_mode:
            self.image_canvas.bind("<ButtonPress-1>", self.start_crop)
            self.image_canvas.bind("<B1-Motion>", self.update_crop)
            self.image_canvas.bind("<ButtonRelease-1>", self.end_crop)
            self.image_canvas.config(cursor="cross")
        else:
            self.image_canvas.unbind("<ButtonPress-1>")
            self.image_canvas.unbind("<B1-Motion>")
            self.image_canvas.unbind("<ButtonRelease-1>")
            self.image_canvas.config(cursor="")
            self.crop_rect = None
            self.image_canvas.delete("crop_rect")

    def start_crop(self, event):
        """Начинает выделение области для обрезки"""
        self.crop_start_x = (event.x - self.image_offset_x) / self.scale_factor
        self.crop_start_y = (event.y - self.image_offset_y) / self.scale_factor
        self.crop_rect = None

    def update_crop(self, event):
        """Обновляет выделение области для обрезки"""
        if not self.crop_start_x or not self.crop_start_y:
            return
            
        end_x = (event.x - self.image_offset_x) / self.scale_factor
        end_y = (event.y - self.image_offset_y) / self.scale_factor
        
        # Удаляем предыдущий прямоугольник
        self.image_canvas.delete("crop_rect")
        
        # Рисуем новый прямоугольник
        x1 = min(self.crop_start_x, end_x) * self.scale_factor + self.image_offset_x
        y1 = min(self.crop_start_y, end_y) * self.scale_factor + self.image_offset_y
        x2 = max(self.crop_start_x, end_x) * self.scale_factor + self.image_offset_x
        y2 = max(self.crop_start_y, end_y) * self.scale_factor + self.image_offset_y
        
        self.image_canvas.create_rectangle(x1, y1, x2, y2, outline="red", tags="crop_rect", width=2)
        self.crop_rect = (self.crop_start_x, self.crop_start_y, end_x, end_y)

    def end_crop(self, event):
        """Завершает выделение и обрезает изображение"""
        if not self.crop_rect:
            return
            
        self.save_state()
        
        try:
            # Обрезаем изображение
            x1, y1, x2, y2 = self.crop_rect
            left = min(x1, x2)
            upper = min(y1, y2)
            right = max(x1, x2)
            lower = max(y1, y2)
            
            # Проверяем границы
            left = max(0, left)
            upper = max(0, upper)
            right = min(self.original_image.width, right)
            lower = min(self.original_image.height, lower)
            
            if right - left > 10 and lower - upper > 10:  # Минимальный размер
                self.original_image = self.original_image.crop((left, upper, right, lower))
                self.update_image_display()
                self.center_image(force=True)  # Принудительно центрируем после обрезки
                self.update_image_info()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обрезать изображение:\n{str(e)}")
        
        self.crop_mode = False
        self.image_canvas.delete("crop_rect")
        self.image_canvas.config(cursor="")

    def toggle_draw_mode(self):
        """Включает/выключает режим рисования"""
        self.drawing_mode = not self.drawing_mode
        self.erase_mode = False
        self.crop_mode = False
        
        if self.drawing_mode:
            self.image_canvas.bind("<ButtonPress-1>", self.start_drawing)
            self.image_canvas.bind("<B1-Motion>", self.draw_on_image)
            self.image_canvas.bind("<ButtonRelease-1>", self.stop_drawing)
            self.image_canvas.config(cursor="pencil")
        else:
            self.image_canvas.unbind("<ButtonPress-1>")
            self.image_canvas.unbind("<B1-Motion>")
            self.image_canvas.unbind("<ButtonRelease-1>")
            self.image_canvas.config(cursor="")

    def start_drawing(self, event):
        """Начинает рисование"""
        if not self.original_image:
            return
            
        self.save_state()
        
        # Создаем копию изображения для рисования
        self.temp_image = self.original_image.copy()
        self.last_x = (event.x - self.image_offset_x) / self.scale_factor
        self.last_y = (event.y - self.image_offset_y) / self.scale_factor

    def draw_on_image(self, event):
        """Рисует на изображении"""
        if not self.temp_image or not self.drawing_mode:
            return

        # Рассчитываем текущие координаты
        x = (event.x - self.image_offset_x) / self.scale_factor
        y = (event.y - self.image_offset_y) / self.scale_factor

        if self.last_x and self.last_y:
            # Создаем временное изображение для рисования
            temp_draw_image = self.temp_image.copy()
            draw = ImageDraw.Draw(temp_draw_image)
            
            # Рисуем сглаженную линию
            points = self._get_smooth_points(self.last_x, self.last_y, x, y)
            for px, py in points:
                draw.ellipse([px - self.brush_size/2, py - self.brush_size/2,
                             px + self.brush_size/2, py + self.brush_size/2],
                            fill=self.brush_color)
            
            self.temp_image = temp_draw_image
        
        self.last_x = x
        self.last_y = y
        
        # Обновляем отображение
        self.update_image_display(self.temp_image)

    def stop_drawing(self, event):
        """Завершает рисование"""
        if self.temp_image is not None:
            self.original_image = self.temp_image.copy()
            self.temp_image = None
        
        self.last_x, self.last_y = None, None
        self.update_image_display()

    def choose_brush_color(self):
        """Выбирает цвет кисти"""
        color = colorchooser.askcolor(title="Выберите цвет кисти", initialcolor=self.brush_color)
        if color[1]:
            self.brush_color = color[1]
            self.color_btn.config(bg=self.brush_color)

    def rotate_image(self, angle):
        """Поворачивает изображение"""
        if not self.original_image:
            return
            
        self.save_state()
        
        try:
            self.original_image = self.original_image.rotate(angle, expand=True)
            self.update_image_display()
            self.center_image(force=True)  # Принудительно центрируем после поворота
            self.update_image_info()
            self.status_bar.config(text=f"Изображение повернуто на {angle}°")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось повернуть изображение:\n{str(e)}")

    def mirror_image(self):
        """Отражает изображение по горизонтали"""
        if not self.original_image:
            return
            
        self.save_state()
        
        try:
            self.original_image = ImageOps.mirror(self.original_image)
            self.update_image_display()
            self.center_image(force=True)  # Принудительно центрируем после отражения
            self.status_bar.config(text="Изображение отражено")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось отразить изображение:\n{str(e)}")

    def apply_filter(self, filter_type):
        """Применяет фильтр к изображению"""
        if not self.original_image:
            return
            
        self.save_state()
        
        try:
            if filter_type == "blur":
                self.original_image = self.original_image.filter(ImageFilter.BLUR)
            elif filter_type == "contour":
                self.original_image = self.original_image.filter(ImageFilter.CONTOUR)
            elif filter_type == "detail":
                self.original_image = self.original_image.filter(ImageFilter.DETAIL)
            elif filter_type == "emboss":
                self.original_image = self.original_image.filter(ImageFilter.EMBOSS)
            elif filter_type == "sharpen":
                self.original_image = self.original_image.filter(ImageFilter.SHARPEN)
            elif filter_type == "smooth":
                self.original_image = self.original_image.filter(ImageFilter.SMOOTH)
                
            self.update_image_display()
            self.center_image(force=True)  # Принудительно центрируем после применения фильтра
            self.status_bar.config(text=f"Применен фильтр: {filter_type}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось применить фильтр:\n{str(e)}")

    def save_state(self):
        """Сохраняет текущее состояние изображения в историю"""
        if self.original_image:
            self.history.append(self.original_image.copy())
            if len(self.history) > 20:  # Ограничиваем историю
                self.history.pop(0)

    def undo(self):
        """Отменяет последнее действие"""
        if len(self.history) > 1:
            self.history.pop()  # Удаляем текущее состояние
            self.original_image = self.history[-1].copy()  # Восстанавливаем предыдущее
            self.update_image_display()
            self.center_image(force=True)  # Принудительно центрируем после отмены
            self.update_image_info()
            self.status_bar.config(text="Отменено последнее действие")
        else:
            messagebox.showinfo("Информация", "Нечего отменять")

    def load_saved_data(self):
        """Загружает сохраненные данные о фотографиях и папках"""
        try:
            if os.path.exists("photo_editor_data.json"):
                with open("photo_editor_data.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.folders = data.get("folders", {"Главная": []})
                    self.current_folder = data.get("current_folder", "Главная")
                    
                    # Проверяем существование файлов
                    for folder in list(self.folders.keys()):
                        valid_paths = []
                        for path in self.folders[folder]:
                            if os.path.exists(path):
                                valid_paths.append(path)
                        self.folders[folder] = valid_paths
                    
                    self.show_thumbnails()
        except Exception as e:
            print(f"Ошибка загрузки данных: {e}")
            self.folders = {"Главная": []}
            self.current_folder = "Главная"

    def save_data(self):
        """Сохраняет данные о фотографиях и папках"""
        try:
            data = {
                "folders": self.folders,
                "current_folder": self.current_folder
            }
            with open("photo_editor_data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения данных: {e}")

    def on_close(self):
        """Обработчик закрытия приложения"""
        self.save_data()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoEditorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()