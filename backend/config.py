from pathlib import Path

from platformdirs import user_config_dir , user_cache_dir
import os
import torch

APP_NAME = "Glimpse"
APP_AUTHOR = "Mahdi_BA"

#DATA_DIR = Path(user_config_dir(APP_NAME, APP_AUTHOR))
#CACHE_DIR = Path(user_cache_dir(APP_NAME, APP_AUTHOR))

DATA_DIR = Path("backend/data")
CACHE_DIR = Path("backend/data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# GENERAL APP STORAGE
SQLITE_DB_PATH = DATA_DIR / "glimpse.db"
SAVED_SEARCHES_PATH = DATA_DIR / "saved_searches.json"
LIBRARY_STATE_PATH = DATA_DIR / "library_state.json"
MODEL_STATE_PATH = DATA_DIR / "model_state.json"
APP_SETTINGS_PATH = DATA_DIR / "app_settings.json"
THUMBNAIL_CACHE_DIR = CACHE_DIR / "thumbnails"
IMPORTED_LIBRARY_ROOT = DATA_DIR / "imported_library"
FACE_QUERY_UPLOAD_DIR = CACHE_DIR / "face_query_uploads"


# VECTOR STORE PATHS
VECTOR_STORE_ROOT = DATA_DIR / "vector_stores"
FACE_VS_PATH = DATA_DIR / "face_vector_store"
PERSON_VS_PATH = DATA_DIR / "person_vector_store"
IMAGE_VS_PATH = DATA_DIR / "image_vector_store"
IMAGE_META_PATH = IMAGE_VS_PATH / "meta_data.json"
VIDEO_VS_PATH = DATA_DIR / "video_vector_store"
VIDEO_META_PATH = VIDEO_VS_PATH / "meta_data.json"


def model_scoped_vs_path(model_id: str, store_type: str = "unified") -> Path:
    """Return a model-scoped vector store directory path.

    Each model gets its own namespace under VECTOR_STORE_ROOT,
    e.g. ``vector_stores/xclip-video-b32/unified/``.
    This ensures switching models never orphanes or invalidates data.
    """
    path = VECTOR_STORE_ROOT / model_id / store_type
    path.mkdir(parents=True, exist_ok=True)
    return path

# GENERAL MODEL CONFIG
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MODELS_CACHE_DIR = DATA_DIR / "cache_dir"


# FACE CONFIG
FACE_EMBEDDING_MODEL_ID = "gaunernst/vit_small_patch8_gap_112.cosface_ms1mv3"
DETECTOR_MODEL_ID = "AdamCodd/YOLOv11n-face-detection"
DETECTOR_MODEL = None
FACE_EMBEDDING_MODEL = None
FACE_DETECTION_CONFIDENCE_THRESHOLD = 0.5
FACE_MIN_BOX_SIZE = 64
FACE_PIPELINE_DBSCAN_EPS = 0.4       
FACE_PIPELINE_DBSCAN_MIN_SAMPLES = 6
FACE_QUALITY_REFERENCE_PIXELS = 4096
FACE_MAX_QUALITY_SCORE = 6.0
FACE_TOP_EXEMPLAR_COUNT = 10
