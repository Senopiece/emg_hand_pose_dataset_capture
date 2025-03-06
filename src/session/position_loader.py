import json
import os

default_pos = [100, 100]

def save_position(filepath, x, y):
    with open(filepath + ".json", "w") as f:
        json.dump({"x": x, "y": y}, f)

def load_position(filepath):
    filepath += ".json"
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            pos = json.load(f)
            x, y = pos.get("x", default_pos[0]), pos.get("y", default_pos[1])
            return x, y
    return default_pos