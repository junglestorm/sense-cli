import shutil
import os

def main():
    path = "data/db/rag_vector_store"
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f"已删除 {path}")
    else:
        print(f"{path} 不存在")