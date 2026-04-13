from backend.core.indexing.index import index_folder
from backend.core.models.vision_language.siglip import SiglipEmbeddingModel

def test_index_folder():
    folder_path = "test_images"
    siglipmodel = SiglipEmbeddingModel()
    stats = index_folder(folder_path, image_model=siglipmodel, batch_size=4, save_after_batch=False)

    print(stats)

def test_search():
    from backend.core.search.search import search_by_text
    siglipmodel = SiglipEmbeddingModel()

    query = "guy wearing a button up shirt"
    results = search_by_text(query, siglipmodel, top_k=10)
    print(results)

if __name__ == "__main__":
    test_search()