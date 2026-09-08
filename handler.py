from os import sep
entrypoint = None
if __name__ == '__main__':
    path_parts = __file__.split(sep)
    filename = path_parts[len(path_parts) - 1]
    entrypoint = filename
print(entrypoint)