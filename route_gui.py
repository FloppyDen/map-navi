import importlib.util
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from tkintermapview import TkinterMapView


def load_route_length_module():
    route_path = Path(__file__).resolve().parent / 'route-length.py'
    if not route_path.exists():
        raise FileNotFoundError(f'Файл route-length.py не найден рядом с {__file__}')

    spec = importlib.util.spec_from_file_location('route_length_module', route_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RouteGuiApp:
    def __init__(self, root, route_module):
        self.root = root
        self.route_module = route_module
        self.route_module_path = Path(__file__).resolve().parent
        self.graph = None
        self.model = None
        self.features = None
        self.start_marker = None
        self.end_marker = None
        self.route_path = None

        self.root.title('Маршрутизатор SPB с интерактивной картой')
        self.root.geometry('980x680')

        top_frame = tk.Frame(root)
        top_frame.pack(fill='x', padx=10, pady=6)

        self.status_label = tk.Label(top_frame, text='Карта загружается... Пожалуйста, подождите.', fg='blue')
        self.status_label.pack(anchor='w')

        main_frame = tk.Frame(root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=4)

        map_frame = tk.Frame(main_frame, bd=2, relief='sunken')
        map_frame.pack(side='left', fill='both', expand=True)

        controls_frame = tk.Frame(main_frame, width=320)
        controls_frame.pack(side='right', fill='y', padx=(10, 0))

        self.map_widget = TkinterMapView(map_frame, width=700, height=640, corner_radius=0)
        self.map_widget.pack(fill='both', expand=True)
        self.map_widget.set_position(59.9343, 30.3351)
        self.map_widget.set_zoom(12)
        self.map_widget.add_left_click_map_command(self.on_map_click)

        tk.Label(controls_frame, text='Координаты стартовой точки:', anchor='w').pack(fill='x', pady=(8, 2))
        self.start_entry = tk.Entry(controls_frame, width=38)
        self.start_entry.pack(fill='x', padx=6)
        self.start_entry.insert(0, '59.9343, 30.3351')

        tk.Label(controls_frame, text='Координаты конечной точки:', anchor='w').pack(fill='x', pady=(10, 2))
        self.end_entry = tk.Entry(controls_frame, width=38)
        self.end_entry.pack(fill='x', padx=6)
        self.end_entry.insert(0, '59.9500, 30.3167')

        tk.Label(controls_frame, text='Инструкция:', anchor='w').pack(fill='x', pady=(10, 2))
        tk.Label(controls_frame, text='Клик на карте выбирает сначала старт, затем финиш.', wraplength=300, justify='left').pack(fill='x', padx=6)
        tk.Label(controls_frame, text='После выбора нажмите "Рассчитать маршрут".', wraplength=300, justify='left').pack(fill='x', padx=6, pady=(0, 10))

        self.calc_button = tk.Button(controls_frame, text='Рассчитать маршрут', command=self.calculate_route, bg='#4CAF50', fg='white', font=('Arial', 11, 'bold'))
        self.calc_button.pack(fill='x', padx=6, pady=6)

        self.reset_button = tk.Button(controls_frame, text='Сбросить точки', command=self.clear_points)
        self.reset_button.pack(fill='x', padx=6, pady=6)

        self.load_button = tk.Button(controls_frame, text='Загрузить граф и модель', command=self.load_graph_and_model)
        self.load_button.pack(fill='x', padx=6, pady=6)

        self.info_label = tk.Label(controls_frame, text='Карты загружаются из сети OSM. Дополнительный файл не требуется.', wraplength=300, justify='left', fg='gray')
        self.info_label.pack(fill='x', padx=6, pady=(20, 0))

        self.map_widget.set_tile_server('https://a.tile.openstreetmap.org/{z}/{x}/{y}.png')
        self.status_label.config(text='Карта загружена. Выберите две точки на карте.', fg='green')

    def on_map_click(self, coords):
        lat, lon = coords
        if self.start_marker is None:
            self.start_marker = self.map_widget.set_marker(lat, lon, text='Старт')
            self.start_entry.delete(0, tk.END)
            self.start_entry.insert(0, f'{lat:.6f}, {lon:.6f}')
            self.status_label.config(text='Старт установлен. Кликните вторую точку на карте для финиша.', fg='blue')
        elif self.end_marker is None:
            self.end_marker = self.map_widget.set_marker(lat, lon, text='Финиш')
            self.end_entry.delete(0, tk.END)
            self.end_entry.insert(0, f'{lat:.6f}, {lon:.6f}')
            self.status_label.config(text='Финиш установлен. Нажмите "Рассчитать маршрут".', fg='blue')
        else:
            self.clear_points()
            self.on_map_click(coords)

    def clear_points(self):
        if self.start_marker:
            self.start_marker.delete()
            self.start_marker = None
        if self.end_marker:
            self.end_marker.delete()
            self.end_marker = None
        if self.route_path is not None:
            try:
                self.map_widget.delete_path(self.route_path)
            except Exception:
                pass
            self.route_path = None
        self.status_label.config(text='Точки сброшены. Кликните на карту для выбора стартовой точки.', fg='blue')

    def load_graph_and_model(self):
        if self.graph is not None and self.model is not None:
            self.status_label.config(text='Граф и модель уже загружены.', fg='green')
            return

        self.status_label.config(text='Загружаю граф и обучаю модель, подождите...', fg='orange')
        self.root.update_idletasks()

        csv_path = Path(self.route_module.CSV_PATH)
        if not csv_path.exists():
            messagebox.showerror('Файл не найден', f'Локальный CSV не найден: {csv_path}')
            self.status_label.config(text='Локальный CSV не найден.', fg='red')
            return

        try:
            self.model, _, self.features = self.route_module.load_model_with_dataset(str(csv_path))
            self.graph = self.route_module.load_osm_graph('Saint Petersburg, Russia')
            self.status_label.config(text='Граф и модель загружены. Теперь можно рассчитывать маршрут.', fg='green')
        except Exception as exc:
            messagebox.showerror('Ошибка загрузки', str(exc))
            self.status_label.config(text='Ошибка при загрузке графа или модели.', fg='red')

    def calculate_route(self):
        if self.graph is None or self.model is None:
            self.load_graph_and_model()
            if self.graph is None or self.model is None:
                return

        try:
            start_text = self.start_entry.get().strip()
            end_text = self.end_entry.get().strip()
            origin = tuple(map(float, start_text.split(',')))
            destination = tuple(map(float, end_text.split(',')))
        except ValueError:
            messagebox.showerror('Ошибка ввода', 'Введите координаты в формате: широта, долгота')
            return

        self.status_label.config(text='Вычисляю маршрут...', fg='orange')
        self.root.update_idletasks()

        route = self.route_module.get_route(self.graph, self.model, self.features, origin, destination)
        if route is None:
            messagebox.showerror('Ошибка маршрута', 'Маршрут не найден для указанных точек.')
            self.status_label.config(text='Маршрут не найден.', fg='red')
            return

        coords = [(self.graph.nodes[node]['y'], self.graph.nodes[node]['x']) for node in route]
        if self.route_path is not None:
            try:
                self.map_widget.delete_path(self.route_path)
            except Exception:
                pass
        self.route_path = self.map_widget.set_path(coords, color='red', width=4)
        self.map_widget.set_position((origin[0] + destination[0]) / 2, (origin[1] + destination[1]) / 2)
        self.map_widget.set_zoom(13)
        self.status_label.config(text='Маршрут построен. Он показан на карте.', fg='green')


def main():
    route_module = load_route_length_module()
    root = tk.Tk()
    app = RouteGuiApp(root, route_module)
    root.mainloop()


if __name__ == '__main__':
    main()
