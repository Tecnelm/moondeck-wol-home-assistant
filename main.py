# autopep8: off
def get_plugin_dir():
    from pathlib import Path
    return Path(__file__).parent.resolve()

def add_plugin_to_path():
    import sys

    plugin_dir = get_plugin_dir()
    directories = [["./"], ["python"], ["python", "lib"], ["python", "externals"]]
    for dir in directories:
        sys.path.append(str(plugin_dir.joinpath(*dir)))

add_plugin_to_path()

import asyncio
import pathlib
import aiohttp
import python.lib.hostinfo as hostinfo
import python.lib.constants as constants
import python.lib.utils as utils

from typing import Any, Dict
from python.lib.settings import settings_manager, UserSettings
from python.lib.logger import logger, set_log_filename
from python.lib.buddyrequests import SteamUiMode
from python.lib.buddyclient import BuddyClient, HelloResult, PcStateChange
from python.lib.utils import wake_on_lan, change_moondeck_runner_ready_state, TimedPooler
from python.lib.runnerresult import Result, RunnerError, set_result, get_result
# autopep8: on

set_log_filename(constants.LOG_FILE, rotate=True)


class Plugin:
    def __cleanup_states(self):
        set_result(None)
        change_moondeck_runner_ready_state(False)

    @utils.async_scope_log(logger.info)
    async def _main(self):
        self.__cleanup_states()

    @utils.async_scope_log(logger.info)
    async def _unload(self):
        self.__cleanup_states()

    @utils.async_scope_log(logger.info)
    async def set_runner_ready(self):
        change_moondeck_runner_ready_state(True)

    @utils.async_scope_log(logger.info)
    async def get_runner_result(self):
        result = get_result()
        # Cleanup is needed to differentiate between moondeck launches
        set_result(None)
        return result

    @utils.async_scope_log(logger.info)
    async def get_user_settings(self):
        try:
            return await settings_manager.get()
        except Exception:
            logger.exception("Unhandled exception")
            return None

    @utils.async_scope_log(logger.info)
    async def set_user_settings(self, data: Dict[str, Any]):
        try:
            await settings_manager.set(utils.from_dict(UserSettings, data))
        except Exception:
            logger.exception("Unhandled exception")

    @utils.async_scope_log(logger.info)
    async def scan_for_hosts(self, timeout: float):
        try:
            return await hostinfo.scan_for_hosts(timeout=timeout)
        except Exception:
            logger.exception("Unhandled exception")
            return []

    @utils.async_scope_log(logger.info)
    async def find_host(self, host_id: str, timeout: float):
        try:
            return await hostinfo.find_host(host_id, timeout=timeout)
        except Exception:
            logger.exception("Unhandled exception")
            return None

    @utils.async_scope_log(logger.info)
    async def get_server_info(self, address: str, port: int, timeout: float):
        try:
            return await hostinfo.get_server_info(address, port, timeout=timeout)
        except Exception:
            logger.exception("Unhandled exception")
            return None

    @utils.async_scope_log(logger.info)
    async def get_buddy_info(self, address: str, buddy_port: int, client_id: str, timeout: float):
        try:
            async with BuddyClient(address, buddy_port, client_id, timeout) as client:
                info_or_status = await client.get_host_info()
                if not isinstance(info_or_status, dict):
                    return {"status": info_or_status.name, "info": None}

                return {"status": "Online", "info": info_or_status}

        except Exception:
            logger.exception("Unhandled exception")
            return HelloResult.Exception.name

    @utils.async_scope_log(logger.info)
    async def start_pairing(self, address: str, buddy_port: int, client_id: str, pin: int, timeout: float):
        try:
            async with BuddyClient(address, buddy_port, client_id, timeout) as client:
                status = await client.start_pairing(pin)
                if status:
                    return status.name

                return "PairingStarted"

        except Exception:
            logger.exception("Unhandled exception")
            return HelloResult.Exception.name

    @utils.async_scope_log(logger.info)
    async def abort_pairing(self, address: str, buddy_port: int, client_id: str, timeout: float):
        try:
            async with BuddyClient(address, buddy_port, client_id, timeout) as client:
                status = await client.abort_pairing()
                if status:
                    logger.error(f"While aborting pairing: {status}")

        except Exception:
            logger.exception("Unhandled exception")
            
    @utils.async_scope_log(logger.info)
    async def call_home_assistant_script_async(self,host_url, token, script_id, payload=None, timeout=300):
        """
        Call a script on Home Assistant server asynchronously using aiohttp
        
        Parameters:
        host_url (str): The URL of your Home Assistant instance
        token (str): Long-lived access token for Home Assistant
        script_id (str): The ID of the script to call
        payload (dict, optional): Additional data to send with the request
        timeout (int, optional): Timeout in seconds for the request (default: 300)
        
        Returns:
        dict: Response from Home Assistant API or None if error
        """
        # Ensure the URL has the correct format
        if not host_url.endswith('/'):
            host_url += '/'
        
        # Create the URL for the script service
        url = f"{host_url}api/services/script/{script_id}"
        
        # Set up the headers with authentication
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Make the async request to Home Assistant using aiohttp
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                async with session.post(
                    url, 
                    headers=headers, 
                    json=payload if payload else {},
                    ssl=False
                ) as response:
                    if response.status >= 400:
                        logger.info(f"Error: HTTP {response.status} - {response.reason}")
                        return None
                    return await response.json()
        except asyncio.TimeoutError:
            logger.info(f"Request timed out after {timeout} seconds. The script may still be running on Home Assistant.")
            return {"status": "unknown", "message": "Request timed out but script execution may have started"}
        except aiohttp.ClientError as e:
            logger.info(f"Error calling Home Assistant script: {e}")
            return None
    
    
    @utils.async_scope_log(logger.info)
    async def wake_on_lan(self, address: str, mac: str):
        try:
            home_assistant_url = "<Home Assistant URL>"
            long_lived_token = "<Your Long-Lived Token>"
            script_name = "<Your Script Name>"
            await self.call_home_assistant_script_async(
                home_assistant_url, 
                long_lived_token, 
                script_name, 
                {},
                timeout=60  # Increase the timeout if needed
            )
        except Exception:
            logger.exception("Unhandled exception")

    @utils.async_scope_log(logger.info)
    async def change_pc_state(self, address: str, buddy_port: int, client_id: str, state: str, timeout: float):
        try:
            state_enum = PcStateChange[state]
            async with BuddyClient(address, buddy_port, client_id, timeout) as client:
                status = await client.change_pc_state(state_enum)
                if status:
                    logger.error(f"While changing PC state to {state}: {status}")

        except Exception:
            logger.exception("Unhandled exception")

    @utils.async_scope_log(logger.info)
    async def get_moondeckrun_path(self):
        try:
            return str(get_plugin_dir().joinpath("python", "moondeckrun.sh"))
        except Exception:
            logger.exception("Unhandled exception")

    @utils.async_scope_log(logger.info)
    async def get_home_dir(self):
        try:
            return str(pathlib.Path("/home", constants.CURRENT_USER))
        except Exception:
            logger.exception("Unhandled exception")

    @utils.async_scope_log(logger.info)
    async def kill_runner(self, app_id: int):
        try:
            logger.info("Killing reaper and moonlight!")
            kill_proc = await asyncio.create_subprocess_shell(f"pkill -f -e -i \"AppId={app_id}|moonlight\"",
                                                              stdout=asyncio.subprocess.PIPE,
                                                              stderr=asyncio.subprocess.STDOUT)
            output, _ = await kill_proc.communicate()
            newline = "\n"
            logger.info(f"pkill output: {newline}{output.decode().strip(newline)}")

        except Exception:
            logger.exception("Unhandled exception")

    @utils.async_scope_log(logger.info)
    async def is_runner_active(self, app_id: int):
        try:
            kill_proc = await asyncio.create_subprocess_shell(f"pgrep -f -i \"AppId={app_id}\"",
                                                              stdout=asyncio.subprocess.PIPE,
                                                              stderr=asyncio.subprocess.DEVNULL)
            output, _ = await kill_proc.communicate()
            return any(chr.isdigit() for chr in output.decode())

        except Exception:
            logger.exception("Unhandled exception")

    @utils.async_scope_log(logger.info)
    async def close_steam(self, address: str, buddy_port: int, client_id: str, timeout: float):
        try:
            async with BuddyClient(address, buddy_port, client_id, timeout) as client:
                status = await client.close_steam()
                if status:
                    logger.error(f"While closing Steam on host PC: {status}")

        except Exception:
            logger.exception("Unhandled exception")

    @utils.async_scope_log(logger.info)
    async def get_gamestream_app_names(self, address: str, buddy_port: int, client_id: str, timeout: float):
        try:
            async with BuddyClient(address, buddy_port, client_id, timeout) as client:
                names_or_status = await client.get_gamestream_app_names()
                if names_or_status and not isinstance(names_or_status, list):
                    logger.error(f"While retrieving gamestream app names: {names_or_status}")
                    return None

                return names_or_status

        except Exception:
            logger.exception("Unhandled exception")
            return None
        
    @utils.async_scope_log(logger.info)
    async def get_non_steam_app_data(self, address: str, buddy_port: int, client_id: str, user_id: str,
                                     buddy_timeout: float, ready_timeout: int):
        try:
            async with BuddyClient(address, buddy_port, client_id, buddy_timeout) as client:
                logger.info(f"Sending request to launch Steam if needed")
                RunnerError.maybe_raise(await client.launch_steam(big_picture_mode=False))

                logger.info("Waiting for Steam to be ready")
                pooler = TimedPooler(retries=ready_timeout,
                                     error_on_retry_out=Result.SteamDidNotReadyUpInTime)

                async for req in pooler(client.get_steam_ui_mode):
                    mode = req["mode"]
                    if mode != SteamUiMode.Unknown:
                        break

                data = await client.get_non_steam_app_data(user_id=user_id)
                if data and not isinstance(data, list):
                    raise RunnerError(data)

                return data

        except RunnerError as err:
            logger.error(f"While retrieving non-Steam app data: {err.result}")
            return None

        except Exception:
            logger.exception("Unhandled exception")
            return None
