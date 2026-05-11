import re
import requests
from typing import Optional

GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"}

SCREENSHOT_PATTERNS = [
    "screenshot",
    "screen.?shot",
    "snip",
    "capture",
    "img_",
    "screen.?grab",
    "printscr",
    "prtsc",
    "screencap",
]


def is_image_file(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return f".{ext}" in IMAGE_EXTENSIONS


def looks_like_screenshot(filename: str) -> bool:
    name_lower = filename.lower()
    for pattern in SCREENSHOT_PATTERNS:
        if re.search(pattern, name_lower):
            return True
    return False


def score_filename(filename: str) -> int:
    return 50 if looks_like_screenshot(filename) else 0


def scan_onedrive(auth, folder_path: str = "/drive/root") -> list[dict]:
    items = []
    url = f"{GRAPH_API_ENDPOINT}/me/drive/root/children"

    if folder_path != "/drive/root":
        url = f"{GRAPH_API_ENDPOINT}/me/drive/root:{folder_path}:/children"

    while url:
        try:
            data = auth.graph_get(url)
            for item in data.get("value", []):
                is_folder = "folder" in item
                item_name = item.get("name", "")

                if is_folder and not item_name.startswith("."):
                    folder_path_full = f"{folder_path}/{item_name}" if folder_path != "/drive/root" else f"/{item_name}"
                    sub_items = scan_onedrive(auth, folder_path_full)
                    items.extend(sub_items)
                elif is_image_file(item_name):
                    item_info = {
                        "id": item["id"],
                        "name": item_name,
                        "path": f"{folder_path}/{item_name}" if folder_path != "/drive/root" else f"/{item_name}",
                        "size": item.get("size", 0),
                        "lastModified": item.get("lastModifiedDateTime", ""),
                        "folder": folder_path,
                        "download_url": item.get("@microsoft.graph.downloadUrl", None),
                        "file_type": item_name.rsplit(".", 1)[-1].lower() if "." in item_name else "",
                    }
                    items.append(item_info)
            url = data.get("@odata.nextLink")
        except Exception as e:
            break

    return items


def download_image(auth, item: dict) -> Optional[bytes]:
    try:
        item_id = item["id"]
        url = f"{GRAPH_API_ENDPOINT}/me/drive/items/{item_id}/content"
        headers = auth.get_headers()
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.content
    except Exception:
        if item.get("download_url"):
            try:
                resp = requests.get(item["download_url"])
                resp.raise_for_status()
                return resp.content
            except Exception:
                return None
        return None


def get_thumbnail(auth, item: dict) -> Optional[bytes]:
    try:
        item_id = item["id"]
        url = f"{GRAPH_API_ENDPOINT}/me/drive/items/{item_id}/thumbnails/0/medium/content"
        headers = auth.get_headers()
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None
