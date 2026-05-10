from pathlib import Path

from platformdirs import user_config_dir , user_cache_dir
import os

APP_NAME = "Glimpse"
APP_AUTHOR = "Glimpse_one"

#DATA_DIR = Path(user_config_dir(APP_NAME, APP_AUTHOR))
#CACHE_DIR = Path(user_cache_dir(APP_NAME, APP_AUTHOR))

DATA_DIR = Path("backend/data")
CACHE_DIR = Path("backend/data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# Backwards-compatible aliases used by model loaders.
data_dir = DATA_DIR
cache_dir = CACHE_DIR

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
FACE_VS_PATH = DATA_DIR / "face_vector_store"
PERSON_VS_PATH = DATA_DIR / "person_vector_store"
IMAGE_VS_PATH = DATA_DIR / "image_vector_store"
IMAGE_META_PATH = IMAGE_VS_PATH / "meta_data.json"

# GENERAL MODEL CONFIG
device = "cpu"

models_cache_dir = DATA_DIR / "cache_dir"


# FACE CONFIG
DETECTOR_MODEL = None
FACE_EMBEDDING_MODEL = None
FACE_DETECTION_CONFIDENCE_THRESHOLD = 0.50
FACE_MIN_BOX_SIZE = 64

# FACE CONFIG
DETECTOR_MODEL = None
FACE_EMBEDDING_MODEL = None
FACE_DETECTION_CONFIDENCE_THRESHOLD = 0.5
FACE_PIPELINE_DBSCAN_EPS = 0.4       
FACE_PIPELINE_DBSCAN_MIN_SAMPLES = 6
FACE_QUALITY_REFERENCE_PIXELS = 4096
FACE_MAX_QUALITY_SCORE = 6.0
FACE_TOP_EXEMPLAR_COUNT = 10
