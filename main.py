import asyncio
import time
import aiohttp
import tomllib
import aiofiles
import json
import random
import signal
import shutil

from pathlib import Path
from utils.logging import create_logger
from utils.time import format_duration

logger = create_logger("Forget")


Path("cache/").mkdir(exist_ok=True)
settings_path = Path("settings.toml")
if not settings_path.exists():
    shutil.copy(Path("settings.default.toml"), settings_path)

with open(settings_path) as f:
    config = tomllib.loads(f.read())

if not config["token"]:
    logger.critical("Please set your Discord token in settings.toml")
    exit()
if not config["channel_id"]:
    logger.critical("Please set the channel id in settings.toml")
    exit()

shutdown_now = False

async def delete_message(session: aiohttp.ClientSession, message_id):
    async with session.delete(
        f"https://discord.com/api/v9/channels/{config["channel_id"]}/messages/{message_id}",
    ) as res:
        if not res.ok:
            if res.status == 429:
                retry_after = float(res.headers.get("retry-after"))
                human_delay = random.randrange(25, 100) / 100

                logger.warning(f"Rate-limited, Discord has requested we wait {retry_after} second(s). Adding human delay of {human_delay} second(s).")
                await asyncio.sleep(retry_after + human_delay)
                await delete_message(session, message_id)
                return
            if res.status == 404:
                logger.warning(f"Message {message_id} not found, it must already be deleted.")
                return
            logger.critical(f"Failed to delete message {message_id}, quitting early. (status {res.status})")
            exit()

async def save_cache(cache, path):
    try:
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(cache, indent=4))
    except Exception:
        logger.critical("SAVE WAS INTERRUPTED, DATA MAY BE LOST :(")

async def main(session: aiohttp.ClientSession):
    async with session.get("https://discord.com/api/v9/users/@me") as res:
        if not res.ok:
            logger.critical("Failed to request information about current user.")
            return
        current_user: dict = await res.json()

    params = {
        "limit": 50,
    }
    cache = {}

    lock_file = Path(f"cache/{config["channel_id"]}.json.lock")
    if lock_file.exists():
        logger.critical("Lock file is present, this usually means another instance is running already.")
        logger.critical(f"If you are SURE there is not another instance running, please delete {lock_file.absolute()}")
        return

    lock_file.touch()

    cache_file = Path(f"cache/{config["channel_id"]}.json")
    if cache_file.exists():
        async with aiofiles.open(cache_file) as f:
            cache = json.loads(await f.read())

        params["before"] = cache["last_before"]

        logger.info(f"Loaded previous save state from cache, at message {params["before"]}")

    start = time.time()
    while not shutdown_now:
        async with session.get(
            f"https://discord.com/api/v9/channels/{config["channel_id"]}/messages",
            params=params,
        ) as res:
            if not res.ok:
                logger.critical(f"Failed to query messages with error {res.status}")
                return
            messages = await res.json()

            if not messages:
                logger.info("Empty message list, assuming we're done. Moving to deletion step.")
                break
            
            if not cache.get("messages"): 
                cache["messages"] = []
            cache["messages"].extend(messages)
            cache["last_before"] = messages[-1]["id"]
            params["before"] = messages[-1]["id"]

        logger.info(f"Discovered {len(cache["messages"])} message(s), {round(time.time() - start)} second(s) elapsed. Saving..")
        # await save_cache(cache, cache_file)

        await asyncio.sleep(config["discover_delay"])

    top_to_bottom_deletion = True

    logger.info("User input required!!")
    answer = input("Delete messages from top to bottom? [Y/n]: ")
    if answer.lower() not in ("", "y", "yes", "n", "no"):
        logger.critical("Response not clear, quitting.")
        return
    
    if answer.lower() in ("n", "no"):
        top_to_bottom_deletion = False

    if not cache.get("deleted_messages"):
        cache["deleted_messages"] = []

    messages = list(cache["messages"].__reversed__() if top_to_bottom_deletion else cache["mesages"])
    messages_to_delete = [msg for msg in messages if msg["author"]["id"] == current_user["id"]]

    length = len(messages_to_delete) + len(cache["deleted_messages"])

    avg_message_delete_times = []

    for i, message in enumerate(messages_to_delete):
        if shutdown_now:
            break
        if message["author"]["id"] != current_user["id"]:
            continue
        if message["type"] not in (0, 19):
            continue

        average_start = time.time()

        await delete_message(session, message["id"])

        cache["messages"].remove(message)
        cache["deleted_messages"].append(message)
        # await save_cache(cache, cache_file)

        avg_message_delete_times.append((time.time() - average_start) + config["delete_delay"])
        if len(avg_message_delete_times) > 20:
            avg_message_delete_times.pop(0)

        average_delete_time = sum(avg_message_delete_times) / len(avg_message_delete_times)
        remaining_messages = length - len(cache["deleted_messages"])
        estimated_remaining_time = average_delete_time * remaining_messages

        logger.info(f"Deleted {len(cache["deleted_messages"])} of {length}.. (estimated {format_duration(estimated_remaining_time)} left) (avg {round(average_delete_time, 2)}s per delete)")
        
        await asyncio.sleep(config["delete_delay"])

    if not shutdown_now:
        logger.info("Finished. All of your messages are now deleted!")
        logger.info(f"To restart this process, delete cache/{config['channel_id']}.json and re-run this script!")
    else:
        logger.info("Terminated early due to a termination signal being fired.")

    lock_file.unlink()

    return cache, cache_file

async def main_wrapper():
    session = aiohttp.ClientSession(
        headers={
            "Authorization": config["token"]
        }
    )

    cache = {}
    cache_file = None
    try:
        res = await main(session)
        if res:
            cache, cache_file = res
    except KeyboardInterrupt:
        logger.warning("Handling Ctrl+C gracefully..")
    finally:
        if cache and cache_file:
            await save_cache(cache, cache_file)
        await session.close()

def handle_shutdown(*_):
    logger.warning("Handling close signal...")

    global shutdown_now
    shutdown_now = True


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_shutdown)   # ctrl+c
    signal.signal(signal.SIGTERM, handle_shutdown)  # systemd stop

    asyncio.run(main_wrapper())
