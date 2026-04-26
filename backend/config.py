import torch
from pathlib import Path

from platformdirs import user_config_dir , user_cache_dir
import os

APP_NAME = "Glimpse"
APP_AUTHOR = "Glimpse_one"

DATA_DIR = Path(user_config_dir(APP_NAME, APP_AUTHOR))
CACHE_DIR = Path(user_cache_dir(APP_NAME, APP_AUTHOR))

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
THUMBNAIL_CACHE_DIR = CACHE_DIR / "thumbnails"
IMPORTED_LIBRARY_ROOT = DATA_DIR / "imported_library"
FACE_QUERY_UPLOAD_DIR = CACHE_DIR / "face_query_uploads"


# VECTOR STORE PATHS
FACE_VS_PATH = DATA_DIR / "face_vector_store"
PERSON_VS_PATH = DATA_DIR / "person_vector_store"
IMAGE_VS_PATH = DATA_DIR / "image_vector_store"
IMAGE_META_PATH = IMAGE_VS_PATH / "meta_data.json"

# GENERAL MODEL CONFIG
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

models_cache_dir = DATA_DIR / "cache_dir"


# FACE CONFIG
DETECTOR_MODEL = None
FACE_EMBEDDING_MODEL = None
FACE_MERGE_THRESHOLD = 0.25
FACE_MIN_BOX_SIZE = 25
FACE_ASSIGNMENT_TOP_K = 8
FACE_BATCH_CLUSTER_THRESHOLD = 0.30
FACE_STRONG_MATCH_THRESHOLD = 0.30
FACE_POST_MERGE_THRESHOLD = 0.35
FACE_QUALITY_REFERENCE_PIXELS = 4096
FACE_TOP_EXEMPLAR_COUNT = 10
FACE_FINAL_MERGE_CENTROID_THRESHOLD = 0.35
FACE_FINAL_MERGE_EXEMPLAR_THRESHOLD = 0.35
FACE_FINAL_MERGE_AVG_EXEMPLAR_THRESHOLD = 0.35
