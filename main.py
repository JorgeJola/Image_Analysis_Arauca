from flask import Blueprint,Flask, render_template, url_for, request,jsonify, send_file, redirect,flash,current_app
import tempfile
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import os
import seaborn as sns
import folium
import zipfile
import geopandas as gpd
import pandas as pd

main=Blueprint('main',__name__)

UPLOAD_FOLDER = tempfile.mkdtemp()
RESULT_FOLDER = tempfile.mkdtemp()
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

def extract_shapefile(zip_path, extract_folder):
    print(f"Extracting zip: {zip_path} to {extract_folder}")  # Depuración
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_folder)
    
    # Buscar archivos .shp en subdirectorios, ignorando archivos no válidos como '._'
    shapefiles = []
    for root, dirs, files in os.walk(extract_folder):
        for file in files:
            # Ignorar archivos con prefijo '._' o archivos no shapefiles
            if file.endswith('.shp') and not file.startswith('._'):
                shapefiles.append(os.path.join(root, file))
    
    print(f"Shapefiles found: {shapefiles}")  # Depuración
    return shapefiles[0] if shapefiles else None

class_colors = {  
    'Urban Zones': '#761800',
    'Industry and Comerciall': '#934741',
    'Mining': '#4616d4',
    'Pastures': '#e8d610',
    'Pastures': '#cddc97',
    'Agricultural Areas': '#dbc382',
    'Forest': '#3a6a00',
    'Shrublands and Grassland': '#cafb4d',
    'Little vegetation areas': '#bfc5b9',
    'Continental Wetlands': '#6b5c8c',
    'Continental Waters': '#0127ff'
}

def create_folium_map(gdf, map_id):
    gdf = gdf.to_crs(epsg=4326)
    # Crear un mapa base centrado en el centro de la geometría
    m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=10)
    
    for _, row in gdf.iterrows():
        # Asignar el color correspondiente de la paleta según la clase
        color = class_colors.get(row['class'], '#808080')  # color predeterminado si no se encuentra en la paleta
        folium.GeoJson(
            row['geometry'],
            style_function=lambda feature, color=color: {
                'fillColor': color,
                'color': 'black',
                'weight': 0.5,
                'fillOpacity': 0.8
            }
        ).add_to(m)
    
    # Guardar el mapa como archivo HTML
    map_path = os.path.join('Image_Analysis_Arauca','static', f'{map_id}.html')
    m.save(map_path)
    return map_path

@main.route('/', methods=['GET', 'POST'])
def change():
    graph_url = None
    map1_url = None 
    map2_url = None 
    if request.method == 'POST':
        # Verificar que los archivos se recibieron
        if 'file1' not in request.files or 'file2' not in request.files:
            return 'No files part'

        file1 = request.files['file1']
        file2 = request.files['file2']

        # Verificar si los archivos fueron subidos correctamente
        if file1 and file2:
            upload_folder = UPLOAD_FOLDER
            file1_path = os.path.join(upload_folder, file1.filename)
            file2_path = os.path.join(upload_folder, file2.filename)
            print(f"Saving file1: {file1.filename} to {file1_path}")  # Depuración
            print(f"Saving file2: {file2.filename} to {file2_path}")  # Depuración

            file1.save(file1_path)
            file2.save(file2_path)

            # Extraer shapefiles
            file1_shapefile = extract_shapefile(file1_path, os.path.join(upload_folder, 'file1'))
            file2_shapefile = extract_shapefile(file2_path, os.path.join(upload_folder, 'file2'))

            # Verificar si se extrajeron shapefiles correctamente
            if not file1_shapefile or not file2_shapefile:
                return "Error: No shapefiles found in the uploaded ZIP files."

            gdf1 = gpd.read_file(os.path.join(upload_folder, 'file1', file1_shapefile))
            gdf2 = gpd.read_file(os.path.join(upload_folder, 'file2', file2_shapefile))

            map1 = create_folium_map(gdf1, 'map1')
            map2 = create_folium_map(gdf2, 'map2')

            # Verificar CRS y transformar si es necesario
            if gdf1.crs.to_string() == "EPSG:4326":
                gdf1 = gdf1.to_crs(epsg=32618)

            if gdf2.crs.to_string() == "EPSG:4326":
                gdf2 = gdf2.to_crs(epsg=32618)

            # Calcular el área
            gdf1["Area"] = gdf1.geometry.area / 1000000
            gdf2["Area"] = gdf2.geometry.area / 1000000

            area_por_clase1 = gdf1.groupby("class")["Area"].sum().reset_index()
            area_por_clase2 = gdf2.groupby("class")["Area"].sum().reset_index()

            df_area = pd.merge(area_por_clase1, area_por_clase2, on="class", suffixes=('_1992', '_2012'))
            df_area["diff"] = df_area["Area_2012"] - df_area["Area_1992"]
            df_area["Change"] = df_area["diff"].apply(lambda x: "Increase" if x > 0 else "Decrease")

            # Graficar el cambio de área
            plt.figure(figsize=(10, 6))
            sns.barplot(x="class", y="diff", data=df_area, hue="Change", palette=["red", "green"])
            plt.axhline(0, color="black", linestyle="--")
            plt.xlabel("Class")
            plt.ylabel("Area (Km²)")
            plt.title("Change in Area")
            plt.xticks(rotation=45, ha="right")
            plt.legend(title="Change", loc="upper left")
            plt.tight_layout()

            graph_path = os.path.join('Image_Analysis_Arauca','static', 'images', 'area_change.png')
            plt.savefig(graph_path)
            plt.close()

            # Log de la ruta del gráfico
            print(f"Graph saved at: {graph_path}")

            # Generar la URL para el gráfico
            graph_url = url_for('static', filename='images/area_change.png')
            map1_url = url_for('static', filename='map1.html')
            map2_url = url_for('static', filename='map2.html')

    return render_template('change.html', map1_url=map1_url, map2_url=map2_url, graph_url=graph_url)