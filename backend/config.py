import torch



device=torch.device("cuda" if torch.cuda.is_available() else "cpu")


models_cache_dir = "backend/data/cache_dir/"