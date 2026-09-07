from os.path import exists, sep
from os import listdir, getenv
from re import compile, match, findall
import pandas as pd
from PIL import Image
import numpy as np
from math import floor

EU4_DIR = getenv("EU4_INSTALL_LOCATION")
SEPARATOR = sep
MAP_DIR = EU4_DIR + SEPARATOR + 'map' + SEPARATOR

with open(MAP_DIR + 'definition.csv') as province_colour_values:
    data = []
    column_names = ['Id', 'Name', 'Red', 'Green', 'Blue']
    for line in province_colour_values.readlines():
        if line.startswith('province'):
            continue # First line defines the legend: province;red;green;blue;x;
        parts = line.strip().split(';')
        assert(len(parts) == 6)
        province_id = int(parts[0])
        red_value = int(parts[1])
        green_value = int(parts[2])
        blue_value = int(parts[3])
        province_name = parts[4]
        data.append([province_id, province_name, red_value, green_value, blue_value])
df_province_colours = pd.DataFrame(data=data, columns=column_names)
df_province_colours= df_province_colours.set_index('Id') 

province_bitmap = Image.open(MAP_DIR + 'provinces.bmp')
array_from_img = np.array(province_bitmap)
height, width, channels = array_from_img.shape
data = np.ndarray((height * width, channels + 2))
x = 0
y = 0
end_of_row = False
end_of_column = False
while y != height:
    colour = array_from_img[y,x,:]
    data[x + y * width, 0] = colour[0]
    data[x + y * width, 1] = colour[1]
    data[x + y * width, 2] = colour[2]
    data[x + y * width, 3] = x
    data[x + y * width, 4] = y
    x += 1
    if (x == width):
        x = 0
        y += 1

df_colour_positions = pd.DataFrame(data, columns=['Red', 'Green', 'Blue', 'X', 'Y'])
df_colour_positions = df_colour_positions.astype(int)

df_provinces = pd.read_csv('../data/provinces_stage1.csv', index_col=0) # Imported from file that collects province data from history file
for idx, row in df_province_colours.iterrows():
    matched_red = df_colour_positions.loc[df_colour_positions['Red'] == row.Red,:]
    matched_green = matched_red.loc[matched_red['Green'] == row.Green,:]
    matched_pixels = matched_green.loc[matched_green['Blue'] == row.Blue,:]
    matched_pixels['Province_Id'] = idx
    try:
        left_edge = min(matched_pixels['X'].values)
        right_edge = max(matched_pixels['X'].values)
        top_edge = max(matched_pixels['Y'].values)
        bottom_edge = min(matched_pixels['Y'].values)
        middle = (floor((right_edge + left_edge) / 2), floor((top_edge + bottom_edge) / 2))
        middle_X, middle_Y = middle
        df_provinces.loc[df_provinces['id'] == idx, 'middle_x_pos'] = middle_X
        df_provinces.loc[df_provinces['id'] == idx, 'middle_y_pos'] = middle_Y
    except:
        assert(matched_pixels.shape[0] < 1) # Verify the matched pixels are actually empty
df_provinces["hre"] = df_provinces["hre"] == "yes"
df_provinces["is_city"] = df_provinces["is_city"] == "yes"
df_provinces["hre"] = df_provinces["hre"].astype(bool)
df_provinces["is_city"] = df_provinces["is_city"].astype(bool)
df_provinces = df_provinces.rename(columns={"id": "province_id"})
df_provinces.to_csv("../data/provinces_stage2.csv")