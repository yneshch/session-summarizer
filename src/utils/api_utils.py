import os

def _extract_session_number(path):
    path_to_dir_transcript = os.getenv("TRANSCRIPT_PATH")
    if os.path.isdir(f"{path_to_dir_transcript}/{path}"):
        return int(path.split(" ")[-1])
    return -1
