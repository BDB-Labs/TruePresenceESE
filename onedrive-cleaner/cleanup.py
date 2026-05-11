import logging

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
ARCHIVE_PATH = "/drive/root:/Archive/ScreenshotCleanup"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="logs/cleanup.log",
)
logger = logging.getLogger(__name__)


def ensure_archive_folder(auth) -> str | None:
    try:
        url = f"{GRAPH_API_ENDPOINT}/me/drive/root:/Archive/ScreenshotCleanup"
        try:
            auth.graph_get(url)
            return "Archive/ScreenshotCleanup"
        except Exception:
            pass

        create_url = f"{GRAPH_API_ENDPOINT}/me/drive/root:/Archive:/children"
        folder_data = {
            "name": "ScreenshotCleanup",
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail",
        }

        try:
            create_url_parent = f"{GRAPH_API_ENDPOINT}/me/drive/root:/Archive:/children"
            try:
                auth.graph_get(f"{GRAPH_API_ENDPOINT}/me/drive/root:/Archive")
            except Exception:
                archive_create = f"{GRAPH_API_ENDPOINT}/me/drive/root:/children"
                archive_folder = {
                    "name": "Archive",
                    "folder": {},
                    "@microsoft.graph.conflictBehavior": "fail",
                }
                headers = auth.get_headers()
                headers["Content-Type"] = "application/json"
                import requests
                resp = requests.post(archive_create, headers=headers, json=archive_folder)
                resp.raise_for_status()

            headers = auth.get_headers()
            headers["Content-Type"] = "application/json"
            import requests
            resp = requests.post(create_url_parent, headers=headers, json=folder_data)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Could not create archive folder: {e}")
            return None

        return "Archive/ScreenshotCleanup"
    except Exception as e:
        logger.error(f"Failed to ensure archive folder: {e}")
        return None


def move_to_archive(auth, item_id: str) -> bool:
    try:
        archive_folder = ensure_archive_folder(auth)
        if not archive_folder:
            logger.error("Archive folder not available")
            return False

        url = f"{GRAPH_API_ENDPOINT}/me/drive/items/{item_id}"
        data = {
            "parentReference": {
                "path": ARCHIVE_PATH
            }
        }
        auth.graph_patch(url, data)
        logger.info(f"Moved item {item_id} to archive")
        return True
    except Exception as e:
        logger.error(f"Failed to move item {item_id} to archive: {e}")
        return False


def move_to_recycle_bin(auth, item_id: str) -> bool:
    try:
        url = f"{GRAPH_API_ENDPOINT}/me/drive/items/{item_id}"
        auth.graph_delete(url)
        logger.info(f"Moved item {item_id} to recycle bin")
        return True
    except Exception as e:
        logger.error(f"Failed to move item {item_id} to recycle bin: {e}")
        return False
