import torch



device=torch.device("cuda" if torch.cuda.is_available() else "cpu")

DETECTOR_MODEL = None
FACE_EMBEDDING_MODEL = None
models_cache_dir = "backend/data/cache_dir/"
