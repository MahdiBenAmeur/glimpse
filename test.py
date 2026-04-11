from pathlib import Path

from huggingface_hub import hf_hub_download
from PIL import Image
from ultralytics import YOLO

from backend.config import models_cache_dir


model_path = hf_hub_download(
    repo_id="AdamCodd/YOLOv11n-face-detection",
    filename="model.pt",
    cache_dir=models_cache_dir,
)

model = YOLO(model_path)

image_path = Path("image.png")
results = model.predict(str(image_path), save=False)

result = results[0]
print(result)

if result.boxes is not None:
    for index, box in enumerate(result.boxes, start=1):
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        confidence = float(box.conf[0]) if box.conf is not None else 0.0
        print(
            f"Box {index}: "
            f"({x1:.1f}, {y1:.1f}) -> ({x2:.1f}, {y2:.1f}) "
            f"confidence={confidence:.3f}"
        )

annotated_bgr = result.plot()
annotated_rgb = annotated_bgr[..., ::-1]
annotated_image = Image.fromarray(annotated_rgb)
annotated_image.show(title="Detection Result")
