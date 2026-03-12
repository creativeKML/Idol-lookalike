"""
FastAPI 서버
- POST /api/match: 얼굴 이미지 업로드 → 닮은 연예인 Top 5 반환
- GET  /images/...: 연예인 사진 서빙
- 실행 : python -m uvicorn server:app --reload
"""

import os
import pickle
from typing import Optional
import numpy as np
import cv2
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from insightface.app import FaceAnalysis
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CROPPED_DIR = r"C:\workspace\idol_project\data\idol_faces_cropped"
app.mount("/images", StaticFiles(directory=CROPPED_DIR), name="images")

print("🔄 InsightFace 모델 로딩 중...")
face_app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
face_app.prepare(ctx_id=0, det_size=(640, 640))
print("✅ 모델 로딩 완료")

DB_PATH = os.path.join(os.path.dirname(__file__), "embeddings.pkl")
with open(DB_PATH, "rb") as f:
    db = pickle.load(f)


def get_representative_photo(gender: str, folder: str) -> str | None:
    folder_path = os.path.join(CROPPED_DIR, gender, folder)
    if not os.path.exists(folder_path):
        return None
    imgs = sorted([f for f in os.listdir(folder_path) if f.endswith(".jpg")])
    if not imgs:
        return None
    return f"/images/{gender}/{folder}/{imgs[0]}"


def build_idol_db(db: dict) -> list[dict]:
    result = []
    for key, val in db.items():
        embeddings = np.array(val["embeddings"])
        mean_emb = embeddings.mean(axis=0)
        mean_emb = mean_emb / np.linalg.norm(mean_emb)
        gender = val["gender"]
        folder = val["folder"]
        result.append({
            "key": key,
            "folder": folder,
            "gender": gender,
            "embedding": mean_emb,
            "photo": get_representative_photo(gender, folder),
        })
    return result


IDOL_DB = build_idol_db(db)


@app.post("/api/match")
async def match_face(
    file: UploadFile = File(...),
    gender: Optional[str] = Form(None),  # "female" | "male" | None(전체)
):
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")

    faces = face_app.get(img)
    if not faces:
        raise HTTPException(status_code=400, detail="얼굴을 감지하지 못했습니다.")

    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    user_emb = face.embedding / np.linalg.norm(face.embedding)

    # 성별 필터링
    filtered_db = IDOL_DB
    if gender in ("female", "male"):
        filtered_db = [idol for idol in IDOL_DB if idol["gender"] == gender]

    if not filtered_db:
        raise HTTPException(status_code=400, detail="해당 성별 데이터가 없습니다.")

    idol_embs = np.array([idol["embedding"] for idol in filtered_db])
    sims = cosine_similarity([user_emb], idol_embs)[0]

    top5_idx = sims.argsort()[::-1][:5]
    results = []
    for idx in top5_idx:
        idol = filtered_db[idx]
        results.append({
            "key": idol["key"],
            "folder": idol["folder"],
            "gender": idol["gender"],
            "similarity": round(float(sims[idx]) * 100, 1),
            "photo": idol["photo"],
        })

    return {"results": results}


@app.get("/")
def health_check():
    return {"status": "ok"}
