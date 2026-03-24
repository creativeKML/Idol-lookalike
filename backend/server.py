"""
FastAPI 서버  ─  v2 성능 개선 버전

변경사항 (v1 → v2):
  - prototype 키 우선 사용 → 없으면 평균 임베딩 fallback
  - L2 정규화 프로토타입 방식으로 유사도 정확도 향상
  - GPU 우선 실행 (CUDAExecutionProvider → CPUExecutionProvider fallback)
  - 🔥 CUDA / cuDNN DLL 선 로딩으로 GPU 안정성 향상
  - 🔥 numpy dot 연산으로 cosine 계산 (속도 개선)
  - 🔥 상대경로(Path) 적용 → OS 독립 실행 가능
  - 유사도 점수 범위 개선: cosine -1~1 → 0~100% 변환
  - 얼굴 감지 실패 시 에러 메시지 개선

유지사항:
  - POST /api/match: 이미지 업로드 → 닮은 연예인 Top-3 반환
  - GET /images/...: 연예인 사진 정적 서빙
  - gender 파라미터로 female/male 필터링
  - CORS: http://localhost:5173
  
- 크롭 경로: data/idol_faces_cropped_v2/female|male/폴더명/
- DB 경로: backend/embeddings_v2.pkl
- 백엔드 실행: python -m uvicorn server:app --reload
- 프론트 실행: npm run dev (front 폴더에서)
"""

# ─────────────────────────────────────────────
# CUDA DLL 경로 (GPU 안정성)
# ─────────────────────────────────────────────
import os
import sys

if sys.platform == "win32":
    os.add_dll_directory(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3\bin")

# ─────────────────────────────────────────────
# ONNX Runtime (GPU 확인)
# ─────────────────────────────────────────────
import onnxruntime as ort

providers = ort.get_available_providers()
print("🔥 ONNX Providers:", providers)

if "CUDAExecutionProvider" in providers:
    print("🚀 GPU 활성화 완료")
else:
    print("⚠️ GPU 미사용 (CPU fallback)")

# ─────────────────────────────────────────────
# 기본 라이브러리
# ─────────────────────────────────────────────
import pickle
from typing import Optional
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from insightface.app import FaceAnalysis

# ─────────────────────────────────────────────
# 경로 설정 (상대경로)
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

CROPPED_DIR = DATA_DIR / "idol_faces_cropped_v2"
DB_PATH     = BASE_DIR / "embeddings_v2.pkl"

# 폴더 없으면 생성 (서버 크래시 방지)
os.makedirs(CROPPED_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# FastAPI 설정
# ─────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/images", StaticFiles(directory=str(CROPPED_DIR)), name="images")

# ─────────────────────────────────────────────
# 모델 로딩
# ─────────────────────────────────────────────
print("🔄 InsightFace 모델 로딩 중...")

face_app = FaceAnalysis(
    name="buffalo_sc",
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
)

face_app.prepare(ctx_id=0, det_size=(640, 640))

print("✅ 모델 로딩 완료")

# ─────────────────────────────────────────────
# DB 로딩
# ─────────────────────────────────────────────
if not DB_PATH.exists():
    raise RuntimeError(f"❌ embeddings DB 없음: {DB_PATH}")

with open(DB_PATH, "rb") as f:
    db = pickle.load(f)

# ─────────────────────────────────────────────
# DB 구성
# ─────────────────────────────────────────────
def get_representative_photo(gender: str, folder: str) -> str | None:
    """연예인 폴더에서 대표 사진 경로 반환"""
    folder_path = CROPPED_DIR / gender / folder

    if not folder_path.exists():
        return None

    imgs = sorted([f for f in os.listdir(folder_path) if f.endswith(".jpg")])
    if not imgs:
        return None

    return f"/images/{gender}/{folder}/{imgs[0]}"


def build_idol_db(db: dict) -> list[dict]:
    """
    DB 로드 후 IDOL_DB 구성
    - prototype 우선 사용
    - 없으면 평균 임베딩 fallback
    """
    result = []

    for key, val in db.items():
        # prototype 우선 사용
        if "prototype" in val:
            proto = val["prototype"]
        else:
            embeddings = np.array(val["embeddings"])
            proto = embeddings.mean(axis=0)
            norm = np.linalg.norm(proto)
            proto = proto / norm if norm > 0 else proto

        gender = val.get("gender", "unknown")
        folder = val.get("folder", key)

        result.append({
            "key": key,
            "folder": folder,
            "gender": gender,
            "embedding": proto,
            "photo": get_representative_photo(gender, folder),
        })

    return result


IDOL_DB = build_idol_db(db)
print(f"✅ 연예인 DB 로드 완료: {len(IDOL_DB)}명")

# 임베딩 행렬 캐싱 (속도 핵심)
IDOL_EMBS = np.array([idol["embedding"] for idol in IDOL_DB])

# ─────────────────────────────────────────────
# 유틸 함수
# ─────────────────────────────────────────────
THRESHOLD = 0.15

def cosine_to_percent(sim: float) -> float:
    clipped = max(0.0, float(sim))
    return round(clipped * 100, 1)

# ─────────────────────────────────────────────
# API
# ─────────────────────────────────────────────
@app.post("/api/match")
async def match_face(
    file: UploadFile = File(...),
    gender: Optional[str] = Form(None),
):
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="이미지를 읽을 수 없습니다.")

    # 얼굴 감지
    faces = face_app.get(img)
    if not faces:
        raise HTTPException(
            status_code=400,
            detail="얼굴을 감지하지 못했습니다. 정면 얼굴 사진을 사용해 주세요."
        )

    # 가장 큰 얼굴 선택
    face = max(
        faces,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
    )

    # 사용자 임베딩 (L2 정규화)
    user_emb = face.embedding
    norm = np.linalg.norm(user_emb)

    if norm == 0:
        raise HTTPException(status_code=400, detail="얼굴 특징을 추출할 수 없습니다.")

    user_emb = user_emb / norm

    # numpy dot (cosine similarity)
    sims = IDOL_EMBS @ user_emb

    # 성별 필터
    filtered_db = IDOL_DB
    filtered_sims = sims

    if gender in ("female", "male"):
        idxs = [i for i, idol in enumerate(IDOL_DB) if idol["gender"] == gender]
        filtered_db = [IDOL_DB[i] for i in idxs]
        filtered_sims = sims[idxs]

    if not filtered_db:
        raise HTTPException(status_code=400, detail="해당 성별 데이터가 없습니다.")

    # threshold 체크
    top_idx = filtered_sims.argmax()
    
    if filtered_sims[top_idx] < THRESHOLD:
        return {
            "results": [],
            "message": "닮은 연예인을 찾지 못했습니다."
        }
    
    # Top-3
    top3_idx = filtered_sims.argsort()[::-1][:3]

    results = []
    for idx in top3_idx:
        idol = filtered_db[idx]
        results.append({
            "key": idol["key"],
            "folder": idol["folder"],
            "gender": idol["gender"],
            "similarity": cosine_to_percent(filtered_sims[idx]),
            "photo": idol["photo"],
        })

    return {"results": results}


# ─────────────────────────────────────────────
@app.get("/")
def health_check():
    return {"status": "ok", "idol_count": len(IDOL_DB)}