import os
from loguru import logger
from openai import OpenAI
from backend.utils.shared_utils import check_if_exists

def openai_massage(path_to_current, path_to_prev, debug = False, verbose = False):
    desired_summary_name = os.getenv("DESIRED_SUMMARY_NAME", "summary")
    model = os.getenv("OPENAI_MODEL", None)
    if not model:
        logger.error("Model not found")
        raise Exception("Model not found")
    if check_if_exists(f"{path_to_current}{desired_summary_name}.txt"):
        logger.info("Summary already exists")
        return
    with open(f"{os.path.dirname(__file__)}/prompt_file.txt", "r") as f:
        prompt = f.read()
    logger.info(f"OpenAI massage start")
    if path_to_prev:
        try:
            with open(f"{path_to_prev}{desired_summary_name}.txt", "r") as f:
                prompt += "\nPrevious Session Summary: \n"
                for line in f:
                    prompt += line
        except Exception as e:
            logger.error(f"Exception: {e}")
    messages = [
        {"role": "system", "content": prompt},
    ]
    if verbose:
        logger.debug(f"Path to transcript {path_to_current}")
        logger.debug(f"Path to previous transcript {path_to_prev}")
        logger.debug(f"Messages: {messages}")
        logger.debug(f"Prompt: {prompt}")
    if debug:
        logger.info(f"OpenAI massage end")
        return
    with open(f"{path_to_current}deepgram-transcription.txt", "r") as res:
        text = res.read()
        messages.append({"role": "user", "content": text})
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )
    response = client.chat.completions.create(model = model, messages = messages)
    with open(f"{path_to_current}{desired_summary_name}.txt", "w") as file:
        file.write(response.choices[0].message.content)
        logger.info(f"OpenAI massage end")
