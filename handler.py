from os import sep
from DataExtraction.province import main as province_main
entrypoint = None
if __name__ == '__main__':
    path_parts = __file__.split(sep)
    filename = path_parts[len(path_parts) - 1]
    entrypoint = filename
    DATADIR = r'.\Data'
province_main(DATADIR)
print(entrypoint)