import osmnx as ox
import pandas as pd
import numpy as np
import networkx as nx
import tkinter as tk
from tkinter import messagebox
import folium
import webbrowser
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

# ==========================================
# ЧАСТЬ 1: ЗАГРУЗКА ДАННЫХ И ОБУЧЕНИЕ МОДЕЛИ
# ==========================================

def prepare_and_train_model(csv_path='spb_road_network_base.csv'):
    """Загружает данные, генерирует синтетическую целевую переменную и обучает модель."""
    print("Загрузка данных и подготовка признаков...")
    df = pd.read_csv(csv_path)
    
    # Синтетическая генерация признака "час суток" (от 0 до 23)
    np.random.seed(42)
    df['hour'] = np.random.randint(0, 24, size=len(df))
    
    # Генерация синтетического "фактического времени" (actual_time)
    # Базовое время + влияние часа пик (8-10 и 17-19 часы) + случайный шум
    rush_hour_multiplier = np.where((df['hour'] >= 8) & (df['hour'] <= 10) | 
                                    (df['hour'] >= 17) & (df['hour'] <= 19), 1.6, 1.1)
    noise = np.random.normal(1.0, 0.15, size=len(df)) # +/- 15% случайного отклонения
    
    df['actual_time'] = df['travel_time'] * rush_hour_multiplier * noise
    
    # Выбор признаков для обучения
    features = ['length', 'speed_kph', 'hour']
    X = df[features]
    y = df['actual_time']
    
    # Разделение на обучающую и тестовую выборки
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Обучение модели случайного леса (ансамблевый метод)
    print("Обучение модели Random Forest...")
    model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    
    # Оценка качества
    predictions = model.predict(X_test)
    mae = mean_absolute_error(y_test, predictions)
    print(f"Обучение завершено. Средняя абсолютная ошибка (MAE): {mae:.2f} секунд.")
    
    return model, df, features

# ==========================================
# ЧАСТЬ 2: ЛОГИКА ПОИСКА МАРШРУТОВ
# ==========================================

def find_k_shortest_paths(G, model, features, start_coord, end_coord, k=3):
    """Находит K альтернативных маршрутов, оценивая их по предсказаниям модели."""
    print("Поиск ближайших узлов графа...")
    start_node = ox.distance.nearest_nodes(G, start_coord[1], start_coord[0]) # lon, lat
    end_node = ox.distance.nearest_nodes(G, end_coord[1], end_coord[0])
    
    # Функция веса для алгоритма поиска: предсказанное время проезда по ребру
    def weight_func(u, v, data):
        # Создаем DataFrame из одного ребра для предсказания
        # Берем среднее значение hour = 18 (вечерний час пик для демонстрации)
        edge_data = pd.DataFrame([{
            'length': data.get('length', 100),
            'speed_kph': data.get('speed_kph', 40),
            'hour': 18 
        }])
        predicted_time = model.predict(edge_data[features])[0]
        return max(predicted_time, 1) # Вес должен быть строго положительным

    print(f"Поиск {k} альтернативных маршрутов...")
    routes = []
    try:
        # nx.shortest_simple_paths реализует алгоритм Йена для поиска K кратчайших путей
        path_generator = nx.shortest_simple_paths(G, start_node, end_node, weight=weight_func)
        
        for _ in range(k):
            route = next(path_generator)
            routes.append(route)
    except nx.NetworkXNoPath:
        print("Маршрут не найден.")
        return []
        
    return routes

# ==========================================
# ЧАСТЬ 3: ГРАФИЧЕСКИЙ ИНТЕРФЕЙС И ВИЗУАЛИЗАЦИЯ
# ==========================================

class RoutingApp:
    def __init__(self, root, model, df, features, G):
        self.root = root
        self.root.title("Интеллектуальный маршрутизатор Санкт-Петербурга (Qwen3.7)")
        self.root.geometry("500x350")
        
        self.model = model
        self.df = df
        self.features = features
        self.G = G
        
        # Настройка интерфейса
        tk.Label(root, text="Координаты старта (Широта, Долгота):", font=("Arial", 10)).pack(pady=5)
        self.start_entry = tk.Entry(root, width=40)
        self.start_entry.insert(0, "59.9343, 30.3351") # Дворцовая площадь
        self.start_entry.pack(pady=5)
        
        tk.Label(root, text="Координаты финиша (Широта, Долгота):", font=("Arial", 10)).pack(pady=5)
        self.end_entry = tk.Entry(root, width=40)
        self.end_entry.insert(0, "59.9500, 30.3167") # Петропавловская крепость
        self.end_entry.pack(pady=5)
        
        self.btn = tk.Button(root, text="Построить оптимальный маршрут", command=self.calculate_and_show, 
                             bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), pady=5)
        self.btn.pack(pady=20)
        
        self.status_label = tk.Label(root, text="Готов к работе", fg="blue")
        self.status_label.pack(pady=10)

    def calculate_and_show(self):
        try:
            self.status_label.config(text="Обработка данных...", fg="orange")
            self.root.update()
            
            start_lat, start_lon = map(float, self.start_entry.get().split(','))
            end_lat, end_lon = map(float, self.end_entry.get().split(','))
            
            routes = find_k_shortest_paths(self.G, self.model, self.features, 
                                           (start_lat, start_lon), (end_lat, end_lon), k=3)
            
            if not routes:
                messagebox.showerror("Ошибка", "Маршрут не найден. Проверьте координаты.")
                self.status_label.config(text="Ошибка поиска", fg="red")
                return
            
            self.visualize_routes(routes, (start_lat, start_lon), (end_lat, end_lon))
            self.status_label.config(text=f"Успешно найдено {len(routes)} маршрутов. Карта открыта.", fg="green")
            
        except ValueError:
            messagebox.showerror("Ошибка ввода", "Введите координаты в формате: Широта, Долгота (например, 59.93, 30.31)")

    def visualize_routes(self, routes, start_coord, end_coord):
        print("Генерация интерактивной карты...")
        # Центрируем карту на середине маршрута
        center_lat = (start_coord[0] + end_coord[0]) / 2
        center_lon = (start_coord[1] + end_coord[1]) / 2
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles="CartoDB positron")
        
        # Добавляем маркеры старта и финиша
        folium.Marker(location=start_coord, popup="Старт", icon=folium.Icon(color="green", icon="play")).add_to(m)
        folium.Marker(location=end_coord, popup="Финиш", icon=folium.Icon(color="red", icon="stop")).add_to(m)
        
        # Визуализация всех найденных маршрутов
        for i, route in enumerate(routes):
            # Извлекаем координаты узлов для построения линии
            route_coords = [(self.G.nodes[node]['y'], self.G.nodes[node]['x']) for node in route]
            
            # Рассчитываем общую предсказанную длительность маршрута для всплывающей подсказки
            total_time = 0
            for u, v in zip(route[:-1], route[1:]):
                edge_data = self.G[u][v][0]
                edge_df = pd.DataFrame([{'length': edge_data.get('length', 100), 
                                         'speed_kph': edge_data.get('speed_kph', 40), 
                                         'hour': 18}])
                total_time += self.model.predict(edge_df[self.features])[0]
            
            # Первый маршрут (индекс 0) считается оптимальным по предсказанию модели
            if i == 0:
                folium.PolyLine(locations=route_coords, color="red", weight=6, opacity=0.9, 
                                popup=f"Оптимальный маршрут (прогноз: {total_time/60:.1f} мин)").add_to(m)
            else:
                folium.PolyLine(locations=route_coords, color="gray", weight=3, opacity=0.6, 
                                popup=f"Альтернатива {i+1} (прогноз: {total_time/60:.1f} мин)").add_to(m)
        
        # Сохранение и открытие карты
        map_file = "spb_route_map.html"
        m.save(map_file)
        webbrowser.open('file://' + os.path.realpath(map_file))

# ==========================================
# ЧАСТЬ 4: ЗАПУСК ПРИЛОЖЕНИЯ
# ==========================================

if __name__ == "__main__":
    print("Инициализация системы...")
    
    # 1. Загружаем граф (используем кэш OSMnx, если он был создан ранее)
    print("Загрузка графа Санкт-Петербурга...")
    G = ox.graph_from_place('Saint Petersburg, Russia', network_type='drive')
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    
    # 2. Если у вас уже есть сохраненный CSV, раскомментируйте следующую строку:
    # model, df, features = prepare_and_train_model('spb_road_network_base.csv')
    
    # Для демонстрации создадим синтетический датасет прямо из графа G
    edges_gdf = ox.graph_to_gdfs(G, nodes=False, edges=True)
    df_demo = edges_gdf[['length', 'speed_kph', 'travel_time']].reset_index(drop=True)
    df_demo['hour'] = np.random.randint(0, 24, size=len(df_demo))
    rush_hour_multiplier = np.where((df_demo['hour'] >= 8) & (df_demo['hour'] <= 10) | (df_demo['hour'] >= 17) & (df_demo['hour'] <= 19), 1.6, 1.1)
    df_demo['actual_time'] = df_demo['travel_time'] * rush_hour_multiplier * np.random.normal(1.0, 0.15, size=len(df_demo))
    
    features = ['length', 'speed_kph', 'hour']
    X = df_demo[features]
    y = df_demo['actual_time']
    
    model = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
    model.fit(X, y)
    print("Модель успешно обучена на синтетических данных графа.")
    
    # 3. Запуск графического интерфейса
    root = tk.Tk()
    app = RoutingApp(root, model, df_demo, features, G)
    root.mainloop()