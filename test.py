from backend.config import device, models_cache_dir , FACE_EMBEDDING_MODEL
from backend.core.models.detectors.face_detector import crop_faces, detect_faces , embed_faces
import torch
from PIL import Image
from pathlib import Path
image1 = Path("image.png")
main = Path("image1.png")

path2box = detect_faces([image1, main])
path2crops = crop_faces(path2box)
"""for index ,(path , crops) in enumerate (path2crops.items()):
    for index2 , crop in enumerate(crops):
        crop.save(f"imagecrop{index}-{index2}.png")"""
path2embeddings = embed_faces(path2crops, batch_size=32)

all_emb = []
for index ,(path , embds) in enumerate (path2embeddings.items()):
    all_emb.extend(embds)

for index , emb1 in enumerate( all_emb):
    print(f"-----------img{index}-----------")
    for index2 , embd2 in enumerate( all_emb):
        if index!=index2:
            print(emb1.shape)
            print(embd2.shape)
            print(f"similarity between {index} and {index2} = {torch.cosine_similarity(emb1,embd2,dim=0)}")




