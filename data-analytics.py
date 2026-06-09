import osmnx as ox
import pandas as pd
import numpy as np

# Настройка параметров OSMnx для корректной работы с графами
ox.settings.use_cache = True
ox.settings.log_console = True

def build_spb_base_graph():
    # Этап 1: Загрузка дорожной сети Санкт-Петербурга
    # Параметр network_type='drive' гарантирует, что мы получим только автомобильные дороги, 
    # исключая пешеходные тропы и велодорожки, что критично для задачи маршрутизации авто.
    print("Загрузка графа Санкт-Петербурга из OpenStreetMap...")
    G = ox.graph_from_place('Saint Petersburg, Russia', network_type='drive')
    print(f"Граф загружен. Узлов: {G.number_of_nodes()}, Ребер: {G.number_of_edges()}")

    # Этап 2: Обогащение графа атрибутами скорости и времени
    # OSMnx автоматически извлекает ограничения скорости из тегов OSM. 
    # Если тег отсутствует, библиотека пытается вывести скорость на основе типа дороги (например, жилой район или магистраль).
    G = ox.add_edge_speeds(G)
    
    # На основе длины ребра и скорости рассчитывается базовое время проезда (travel_time) в секундах.
    G = ox.add_edge_travel_times(G)

    # Этап 3: Преобразование графа в табличный формат (DataFrame)
    # Алгоритмы ансамблей (Random Forest, XGBoost, CatBoost) работают с табличными данными, 
    # а не с объектами NetworkX. Поэтому мы извлекаем только ребра (edges).
    edges_gdf = ox.graph_to_gdfs(G, nodes=False, edges=True).reset_index()
    
    # Выбираем ключевые признаки для будущего датасета
    # u и v - это идентификаторы начального и конечного узлов ребра
    # length - длина в метрах, speed_kph - скорость в км/ч, travel_time - время в секундах
    target_columns = ['osmid', 'u', 'v', 'length', 'speed_kph', 'travel_time']
    
    # Создаем чистый DataFrame, сбрасывая сложный индекс GeoDataFrame
    df_ml = edges_gdf[target_columns].reset_index(drop=True)

    # Этап 4: Инженерия данных и обработка пропусков
    # В реальных данных OSM некоторые дороги могут не иметь тега скорости. 
    # Для устойчивости модели мы заполняем пропуски (NaN) медианной скоростью по городу, например, 40 км/ч.
    median_speed = df_ml['speed_kph'].median()
    df_ml['speed_kph'] = df_ml['speed_kph'].fillna(median_speed)
    
    # Пересчитываем время проезда для строк с заполненной скоростью для абсолютной точности.
    # Формула: время (сек) = расстояние (м) / (скорость (км/ч) / 3.6)
    df_ml['travel_time'] = df_ml['length'] / (df_ml['speed_kph'] / 3.6)

    return df_ml, G

# Выполнение функции и просмотр результата
if __name__ == "__main__":
    dataframe, graph = build_spb_base_graph()
    print("\nПервые 5 строк подготовленного датасета:")
    print(dataframe.head())
    
    # Сохранение результата для дальнейшего использования
    dataframe.to_csv('spb_road_network_base.csv', index=False, encoding='utf-8')
    print("\nДатасет успешно сохранен в файл spb_road_network_base.csv")