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
FACE_MERGE_THRESHOLD = 0.3
