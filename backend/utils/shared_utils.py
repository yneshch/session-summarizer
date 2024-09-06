import os

def check_if_exists(path):
    if not os.path.exists(path):
        return False
    return True
