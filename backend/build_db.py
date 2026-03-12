"""
연예인 임베딩 DB 생성
- InsightFace(ArcFace)로 512차원 임베딩 추출
- crop된 사진 기반으로 DB 구축
- 저장: backend/embeddings.pkl
- 사용법: python build_db.py
"""

import os
import sys
import pickle
import cv2
import numpy as np
from insightface.app import FaceAnalysis

# venv 체크
if sys.prefix == sys.base_prefix:
    print("❌ venv가 활성화되지 않았습니다!")
    print("  source venv/Scripts/activate")
    sys.exit(1)
else:
    print(f"✅ venv 활성화 확인: {sys.prefix}")

# -----------------------------------------------
# [1] 설정
# -----------------------------------------------
SRC_DIR  = r"C:\workspace\idol_project\data\idol_faces_cropped"
SAVE_PATH = os.path.join(os.path.dirname(__file__), "embeddings.pkl")

# -----------------------------------------------
# [2] InsightFace 초기화
# -----------------------------------------------
print("🔄 InsightFace 모델 로딩 중...")
app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640))
print("✅ 모델 로딩 완료")

# -----------------------------------------------
# [3] 임베딩 추출 함수
# -----------------------------------------------
def get_embedding(img_path):
    """이미지에서 ArcFace 512d 임베딩 추출"""
    img = cv2.imread(img_path)
    if img is None:
        return None
    try:
        faces = app.get(img)
        if len(faces) != 1:
            return None
        emb = faces[0].embedding
        # 정규화
        emb = emb / np.linalg.norm(emb)
        return emb
    except Exception:
        return None

# -----------------------------------------------
# [4] 전체 실행
# -----------------------------------------------
def main():
    """
    DB 구조:
    {
        "female/ive_jangwonyoung": {
            "embeddings": [np.array, ...],  # 512d 임베딩 리스트
            "name": "장원영",
            "group": "IVE",
            "gender": "female"
        },
        ...
    }
    """
    db = {}
    total = ok = skip = 0

    for gender in ["female", "male"]:
        src_gender = os.path.join(SRC_DIR, gender)
        if not os.path.exists(src_gender):
            continue

        for idol_folder in sorted(os.listdir(src_gender)):
            src_folder = os.path.join(src_gender, idol_folder)
            if not os.path.isdir(src_folder):
                continue

            key = f"{gender}/{idol_folder}"
            imgs = [f for f in os.listdir(src_folder) if f.endswith(".jpg")]
            print(f"\n📁 {key} ({len(imgs)}장)")

            embeddings = []
            for img_name in sorted(imgs):
                img_path = os.path.join(src_folder, img_name)
                emb = get_embedding(img_path)
                total += 1
                if emb is not None:
                    embeddings.append(emb)
                    ok += 1
                    print(f"  ✅ {img_name}")
                else:
                    skip += 1
                    print(f"  ❌ [스킵] {img_name}")

            if embeddings:
                db[key] = {
                    "embeddings": embeddings,
                    "gender": gender,
                    "folder": idol_folder,
                }

    # 저장
    with open(SAVE_PATH, "wb") as f:
        pickle.dump(db, f)

    print(f"\n{'='*40}")
    print(f"✅ 완료: {ok}/{total}장 임베딩 추출")
    print(f"❌ 스킵: {skip}장")
    print(f"👥 연예인 수: {len(db)}명")
    print(f"💾 저장 경로: {SAVE_PATH}")

if __name__ == "__main__":
    main()
