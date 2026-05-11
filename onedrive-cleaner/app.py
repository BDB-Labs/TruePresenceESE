import streamlit as st
from onedrive_cleaner.auth import OneDriveAuth
from onedrive_cleaner.scanner import scan_onedrive, score_filename, download_image, get_thumbnail
from onedrive_cleaner.ocr import run_ocr
from onedrive_cleaner.cleanup import move_to_archive, move_to_recycle_bin
import logging
import time
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="logs/app.log",
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="OneDrive Screenshot Cleaner",
    page_icon="🧹",
    layout="wide",
)

if "auth" not in st.session_state:
    st.session_state.auth = OneDriveAuth()
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "processed" not in st.session_state:
    st.session_state.processed = {}
if "scan_complete" not in st.session_state:
    st.session_state.scan_complete = False

st.title("🧹 OneDrive Screenshot Cleaner")
st.markdown("Scan your OneDrive for screenshots and chat conversation screenshots, then safely archive them.")

with st.sidebar:
    st.header("Controls")

    if not st.session_state.auth.is_authenticated():
        if st.button("🔑 Login to OneDrive", use_container_width=True):
            with st.spinner("Starting device login flow..."):
                try:
                    flow = st.session_state.auth.login()
                    st.info(
                        f"### Device Code Login\n\n"
                        f"1. Go to [microsoft.com/link](https://microsoft.com/link)\n"
                        f"2. Enter code: **{flow['user_code']}**\n"
                        f"3. Complete authentication\n\n"
                        f"Waiting for authentication..."
                    )
                    st.session_state.auth.complete_login(flow)
                    st.success("✅ Authenticated!")
                    user_info = st.session_state.auth.get_user_info()
                    st.session_state.user_name = user_info.get("displayName", "User")
                    st.rerun()
                except Exception as e:
                    st.error(f"Authentication failed: {e}")
    else:
        user_name = st.session_state.get("user_name", "User")
        st.success(f"✅ Logged in as **{user_name}**")

        if st.button("🔍 Scan OneDrive", use_container_width=True, type="primary"):
            st.session_state.scan_results = []
            st.session_state.processed = {}
            st.session_state.scan_complete = False

            with st.spinner("Scanning OneDrive for images..."):
                try:
                    items = scan_onedrive(st.session_state.auth)
                    st.session_state.scan_results = items
                    st.session_state.scan_complete = True
                    st.success(f"Found {len(items)} image files")
                    st.rerun()
                except Exception as e:
                    st.error(f"Scan failed: {e}")

    min_confidence = st.slider(
        "Min confidence score",
        min_value=0,
        max_value=100,
        value=50,
        step=10,
        help="Only show items with at least this confidence score",
    )

    if st.session_state.scan_complete and st.session_state.scan_results:
        st.divider()
        st.subheader("Actions")

        selected_ids = [
            item_id for item_id, data in st.session_state.processed.items()
            if data.get("selected", False)
        ]

        st.text(f"Selected: {len(selected_ids)} files")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📦 Archive Selected", use_container_width=True, type="primary"):
                if not selected_ids:
                    st.warning("No files selected")
                else:
                    progress = st.progress(0, text="Archiving...")
                    success_count = 0
                    for i, item_id in enumerate(selected_ids):
                        ok = move_to_archive(st.session_state.auth, item_id)
                        if ok:
                            success_count += 1
                            if item_id in st.session_state.processed:
                                st.session_state.processed[item_id]["archived"] = True
                        progress.progress(
                            (i + 1) / len(selected_ids),
                            text=f"Archiving {i + 1}/{len(selected_ids)}..."
                        )
                        time.sleep(0.1)
                    st.success(f"Archived {success_count}/{len(selected_ids)} files to /Archive/ScreenshotCleanup")
                    st.rerun()

        with col2:
            if st.button("🗑️ Delete Selected", use_container_width=True):
                if not selected_ids:
                    st.warning("No files selected")
                else:
                    st.warning("Files will be moved to OneDrive recycle bin, not permanently deleted.")
                    progress = st.progress(0, text="Moving to recycle bin...")
                    success_count = 0
                    for i, item_id in enumerate(selected_ids):
                        ok = move_to_recycle_bin(st.session_state.auth, item_id)
                        if ok:
                            success_count += 1
                            if item_id in st.session_state.processed:
                                st.session_state.processed[item_id]["deleted"] = True
                        progress.progress(
                            (i + 1) / len(selected_ids),
                            text=f"Deleting {i + 1}/{len(selected_ids)}..."
                        )
                        time.sleep(0.1)
                    st.success(f"Moved {success_count}/{len(selected_ids)} files to recycle bin")
                    st.rerun()

        if st.button("Clear Results", use_container_width=True):
            st.session_state.scan_results = []
            st.session_state.processed = {}
            st.session_state.scan_complete = False
            st.rerun()

tab1, tab2 = st.tabs(["Review", "Stats"])

with tab1:
    if not st.session_state.scan_complete:
        st.info("👈 Log in and click **Scan OneDrive** to get started.")
    elif not st.session_state.scan_results:
        st.warning("No image files found in your OneDrive.")
    else:
        results_to_show = []
        for item in st.session_state.scan_results:
            item_id = item["id"]
            filename = item["name"]
            name_score = score_filename(filename)

            if item_id not in st.session_state.processed:
                st.session_state.processed[item_id] = {
                    "name_score": name_score,
                    "ocr_score": 0,
                    "ocr_text": "",
                    "selected": False,
                    "archived": False,
                    "deleted": False,
                    "ocr_done": False,
                }

            proc = st.session_state.processed[item_id]
            total_score = proc["name_score"] + proc["ocr_score"]

            if total_score >= min_confidence:
                results_to_show.append((item, proc, total_score))

        results_to_show.sort(key=lambda x: x[2], reverse=True)

        if not results_to_show:
            st.info(f"No items found with confidence >= {min_confidence}. Try lowering the threshold.")
        else:
            st.subheader(f"Found {len(results_to_show)} items (confidence ≥ {min_confidence})")

            cols = st.columns(3)
            for idx, (item, proc, total_score) in enumerate(results_to_show):
                filename = item["name"]
                item_id = item["id"]

                with cols[idx % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{filename}**")
                        st.caption(f"Size: {_format_size(item['size'])}")

                        thumbnail_bytes = get_thumbnail(st.session_state.auth, item)
                        if thumbnail_bytes:
                            st.image(thumbnail_bytes, use_container_width=True)
                        else:
                            img_bytes = download_image(st.session_state.auth, item)
                            if img_bytes:
                                st.image(img_bytes, use_container_width=True)
                        st.progress(total_score / 100, text=f"Confidence: {total_score}%")

                        if not proc["ocr_done"]:
                            with st.spinner("Running OCR..."):
                                img_bytes = download_image(st.session_state.auth, item)
                                if img_bytes:
                                    ocr_text, ocr_score = run_ocr(img_bytes)
                                    proc["ocr_text"] = ocr_text[:500]
                                    proc["ocr_score"] = ocr_score
                                    proc["ocr_done"] = True
                                    total_score = proc["name_score"] + proc["ocr_score"]

                        if proc["ocr_text"]:
                            with st.expander("OCR Preview"):
                                st.text(proc["ocr_text"][:300])
                        else:
                            st.caption("No text detected")

                        st.caption(f"Filename: {proc['name_score']}% | OCR Chat: {proc['ocr_score']}%")

                        disabled = proc.get("archived", False) or proc.get("deleted", False)
                        if disabled:
                            if proc.get("archived"):
                                st.success("✅ Archived")
                            elif proc.get("deleted"):
                                st.warning("🗑️ Deleted")
                        else:
                            selected = st.checkbox(
                                "Select for action",
                                key=f"sel_{item_id}",
                                value=proc.get("selected", False),
                            )
                            proc["selected"] = selected

with tab2:
    if st.session_state.scan_complete and st.session_state.scan_results:
        total = len(st.session_state.scan_results)
        processed_count = sum(1 for p in st.session_state.processed.values() if p.get("ocr_done"))
        screenshot_likely = sum(
            1 for p in st.session_state.processed.values()
            if p.get("name_score", 0) >= 50 and p.get("ocr_done")
        )
        chat_likely = sum(
            1 for p in st.session_state.processed.values()
            if p.get("ocr_score", 0) >= 30 and p.get("ocr_done")
        )
        archived = sum(1 for p in st.session_state.processed.values() if p.get("archived"))
        deleted = sum(1 for p in st.session_state.processed.values() if p.get("deleted"))

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Images", total)
        col2.metric("Scanned with OCR", processed_count)
        col3.metric("Screenshots", screenshot_likely)
        col4.metric("Chat Screenshots", chat_likely)
        col5.metric("Cleaned Up", archived + deleted)
    else:
        st.info("No scan data yet. Run a scan first.")

st.divider()
st.caption("OneDrive Screenshot Cleaner MVP | Files are moved to Archive folder, never permanently deleted.")


def _format_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"
