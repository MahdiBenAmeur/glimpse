import torch



# VECTOR STORE PATHS
FACE_VS_PATH = "backend/data/face_vector_store/"
PERSON_VS_PATH = "backend/data/person_vector_store/"
IMAGE_VS_PATH = "backend/data/image_vector_store/"

# GENERAL MODEL CONFIG
device=torch.device("cuda" if torch.cuda.is_available() else "cpu")

models_cache_dir = "backend/data/cache_dir/"


# FACE CONFIG
DETECTOR_MODEL = None
FACE_EMBEDDING_MODEL = None
FACE_MERGE_THRESHOLD = 0.25
FACE_MIN_BOX_SIZE = 25
FACE_ASSIGNMENT_TOP_K = 8
FACE_BATCH_CLUSTER_THRESHOLD = 0.30
FACE_STRONG_MATCH_THRESHOLD = 0.33
FACE_POST_MERGE_THRESHOLD = 0.31
FACE_QUALITY_REFERENCE_PIXELS = 4096
