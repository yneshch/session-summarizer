
import os
import speech_recognition as sr
import shutil
import zipfile
from pydub import AudioSegment
from pydub.silence import split_on_silence
from multiprocessing import Pool, Manager
import time
import logging
from tqdm import tqdm
from datetime import datetime
import argparse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# create a file handler
log_file = logging.FileHandler('transcribe_audio.log')
log_file.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(log_file)

def print_time(prev_time):
    delta = time.time() - prev_time
    readable_time = f"{delta//3600}h {(delta//60)%60}m {delta%60:.2f}s"
    return readable_time

def split_audio_on_silence(file_name, path_to_transcript_dir, min_silence_len=300, silence_thresh=-16, keep_silence=100, min_chunk_length=1000, seek_step=1):
    #  create a directory to store the audio chunks
    folder_name = f"{path_to_transcript_dir}/audio-chunks"
    if not os.path.isdir(folder_name):
        os.mkdir(folder_name)
    sound = AudioSegment.from_file(f"{path_to_transcript_dir}/{file_name}")
    chunks = split_on_silence(
        sound,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        keep_silence=keep_silence,
        seek_step=seek_step
    )
    combined_audio = AudioSegment.silent(duration=10)
    accumulated_chunks = 0
    for audio_chunk in tqdm(chunks, desc="Splitting audio chunks"):
        # export audio chunk and save it in
        # the `folder_name` directory.
        if(len(combined_audio) < min_chunk_length):
            combined_audio += audio_chunk
            continue
        else:
            chunk_filename = os.path.join(folder_name, f"chunk_{accumulated_chunks}.wav")
            # save audio chunk and append metadata to a file
            if combined_audio.dBFS > -40:
                combined_audio.export(chunk_filename, format="wav")
                accumulated_chunks += 1
            else:
                logger.info(f"Chunk {accumulated_chunks} is too quiet so it is not being saved")
            combined_audio = AudioSegment.silent(duration=1)

def transcribe_audio_mt(path, index, result_list):
    # use the audio file as the audio source
    recognizer = sr.Recognizer()
    with sr.AudioFile(path) as source:
        audio_listened = recognizer.record(source)
        # try converting it to text
        try:
            text = recognizer.recognize_google(audio_listened)
            result_list.append((index, text))
        except sr.UnknownValueError as e:
            logger.error(f"Error in transcription: UnknownValueError at path {path}. Audio length is {source.DURATION}")

def all_zip(given_path):
    #  Finds all zip files based on name
    if os.path.isfile(given_path):
        yield given_path
    else:
        for file in os.listdir(given_path):
            if os.path.isdir(os.path.join(given_path, file)):
                yield from all_zip(os.path.join(given_path, file))
            else:
                yield f"{given_path}/{file}"

def find_correct_file(desired_file_name, file_path, path_to_transcript_dir, extract=True):
     with zipfile.ZipFile(file_path, 'r') as zip_ref:
        for name in zip_ref.namelist():
            # if there is a folder, we have to go one level deeper first
            if "/" in name:
                for sub_name in zip_ref.namelist():
                    dir_name = sub_name.split("/")[0]
                    file_name = sub_name.split("/")[-1]
                    if desired_file_name.lower() in file_name.lower():
                        if extract:
                            zip_ref.extract(sub_name, path=path_to_transcript_dir)
                            os.rename(f"{path_to_transcript_dir}/{sub_name}", f"{path_to_transcript_dir}/{file_name}")
                            shutil.rmtree(f"{path_to_transcript_dir}/{dir_name}")
                        return file_name
            elif desired_file_name.lower() in name.lower():
                if extract:
                    zip_ref.extract(name, path=path_to_transcript_dir)
                return name
        return ""    

def transriber(
        rec_base_path, #path to recording
        base_path, #path to base folder
        desired_file_name, #name of the file to transcribe
        transcript_name=None, #name of the transcript
        min_silence_len=2000, 
        silence_thresh=-100, 
        keep_silence=100, 
        min_chunk_length=1000, 
        seek_step=1
    ):
    start = time.time()
    list_of_files = list(all_zip(rec_base_path))
    for i in tqdm(list_of_files, desc="Transcribing audio files"):
        if i.endswith(".zip"):
            next_time_start = time.time()
            session_name = i.split("/")[-1].split(".")[0]
            logger.info(f"Ran on day {datetime.today().strftime('%Y-%m-%d')} at {datetime.today().strftime('%H:%M:%S')}")
            logger.info(f"Starting {session_name}")
            tokens = 0
            if(transcript_name is None):
                # path_to_transcript = f"{new_path}/transcript-{session_name}.txt"
                transcript_name = f"{session_name.replace(' ', '-')}"
            path_to_transcript_dir = f"{base_path}/{transcript_name}"
            path_to_transcript_file = f"{path_to_transcript_dir}/{transcript_name}.txt"
                
            if not os.path.isdir(path_to_transcript_dir):
                os.mkdir(path_to_transcript_dir)
            # path_to_temp = new_path+f"/temp-{session_name}"
            name = find_correct_file(desired_file_name, i, path_to_transcript_dir)
            # Extract file
            if not os.path.isfile(f"{path_to_transcript_dir}/{name}"):
                # zip_ref.extract(name, path=path_to_temp)
                logger.info(f"Extracted {name} to {path_to_transcript_dir} in {print_time(next_time_start)} seconds")
            else:
                logger.info(f"{name} already extracted")
            next_time_start = time.time()
            # do transcription
            # 1. split on silence
            # Splits the large audio file into chunks
            split_audio_on_silence(
                name, 
                path_to_transcript_dir,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
                keep_silence=keep_silence,
                min_chunk_length=min_chunk_length,
                seek_step=seek_step
            )
            logger.info(f"Split {name} in {print_time(next_time_start)} seconds")
            next_time_start = time.time()
                        
            # 2. transcribe
            # Order the chunks of audio by their index and transcribes them
            # Performs this in a multi-threaded manner
            manager = Manager()
            results = manager.list()
            chunks_folder_name = f"{path_to_transcript_dir}/audio-chunks/"
            ordered_list = sorted(os.listdir(chunks_folder_name), key=lambda x: int(x.split("_")[1].split(".")[0]))
            temp_paths = []
            for file in ordered_list:
                temp_paths.append(os.path.join(chunks_folder_name, file))
            with Pool() as pool:
                pool.starmap(transcribe_audio_mt, [(path, i, results) for i, path in enumerate(temp_paths)])
            final_result = sorted(results, key=lambda x: x[0])
            logger.info(f"Transcribed {name} in {print_time(next_time_start)} seconds")
            next_time_start = time.time()

            # 3. save and clean up
            # Writes the results to a file
            if(os.path.isfile(path_to_transcript_file)):
                os.remove(path_to_transcript_file)
            for result in final_result:
                if(len(result[1].split(" ")) > 10):
                    tokens += len(result[1].split(" "))
                with open(path_to_transcript_file, "a") as f: #change names
                    f.write(result[1] + "\n")
            logger.info(f"Saved {name} in {print_time(next_time_start)} seconds")
            next_time_start = time.time()
            logger.info(f"Finished {session_name} in {print_time(start)} seconds with {tokens} words")
            logger.info(f"Saved at {path_to_transcript_file}")

def cleanup(rec_base_path):
    # List all subdirectories in the given directory
    subdirs = [d for d in os.listdir(rec_base_path) if os.path.isdir(os.path.join(rec_base_path, d)) and "temp" in d]

    # Display the subdirectories and ask for user input
    print("Subdirectories found:")
    for idx, subdir in enumerate(subdirs, 1):
        print(f"{idx}. {subdir}")
    print(f"{len(subdirs) + 1}. All")

    # Get the user's choice
    choice = input("Enter the number of the directory to delete (or 'All' to delete everything): ")

    # Validate and process the choice
    if choice.isdigit() and 1 <= int(choice) <= len(subdirs):
        # Delete the selected subdirectory
        # print(f"Deleting {subdirs[int(choice) - 1]}...")
        chosen = os.path.join(rec_base_path, subdirs[int(choice) - 1],"audio-chunks")
        # print(chosen)
        shutil.rmtree(chosen)
    elif choice.lower() == 'all':
        # Delete all subdirectories
        # print("Deleting all subdirectories...")
        for subdir in subdirs:
            # print(f"Deleting {subdir}...")
            chosen = os.path.join(rec_base_path, subdir,"audio-chunks")
            # print(chosen)
            shutil.rmtree(chosen)
    else:
        print("Invalid input. No directories were deleted.")

def main():    
    parser = argparse.ArgumentParser(description='Transcribe audio files')
    parser.add_argument('-r','--rec_base_path', type=str, help='path to the recording folder', required=True)
    parser.add_argument('-b','--base_path', type=str, help='path to the base folder', required=True)
    parser.add_argument('-d','--desired_file_name', type=str, help='name of the file to transcribe', required=True)
    parser.add_argument('-t','--transcript_name', type=str, help='name of the transcript')
    parser.add_argument('-ms','--min_silence_len', type=int, help='min_silence_len', default=2000)
    parser.add_argument('-st','--silence_thresh', type=int, help='silence_thresh', default=-100)
    parser.add_argument('-k','--keep_silence', type=int, help='keep_silence', default=100)
    parser.add_argument('-mc','--min_chunk_length', type=int, help='min_chunk_length', default=1000)
    parser.add_argument('-ss','--seek_step', type=int, help='seek_step', default=1000)
    parser.add_argument('-c','--clean', type=bool, help='clean', default=False)
    args = parser.parse_args()
    if args.clean:
        cleanup(args.rec_base_path)
    else:
        try:
            transriber(args.rec_base_path, 
                    args.base_path, 
                    args.desired_file_name, 
                    args.transcript_name, 
                    args.min_silence_len, 
                    args.silence_thresh, 
                    args.keep_silence, 
                    args.min_chunk_length, 
                    args.seek_step
            )
        except Exception as e:
            logger.error(e)
        logger.info(f"Params: min_silence_len={args.min_silence_len}, silence_thresh={args.silence_thresh}, keep_silence={args.keep_silence}, min_chunk_length={args.min_chunk_length}, seek_step={args.seek_step}")
        logger.info("--------------------------------------------------")
    
if __name__ == "__main__":
    main()