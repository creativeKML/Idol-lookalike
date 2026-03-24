"""
연예인 얼굴 Crop + 임베딩 생성 ─  v4 최종 완성 버전

최종 목표:
  - 데이터 품질 관리 + GPU + 임베딩 + DB 생성 ALL-IN-ONE

변경사항:
  - CUDA / cuDNN DLL 경로 명시 (GPU 안정화)
  - onnxruntime 선 로딩 → CUDAExecutionProvider 강제 활성화
  - GPU 우선 실행 (CUDA → CPU fallback)
  - 임베딩 + prototype 생성 (L2 정규화)
  - 데이터 품질 필터링 추가
      - 얼굴 없음 제거
      - 단체사진 제거
      - 저화질 제거
  - 통계 출력 유지

기존 유지:
  - 비율 기반 padding (10%)
  - 224x224 리사이즈 (ArcFace 입력)
  - 성별 폴더 구조
  - 중복 crop 스킵

경로:
  - 원본: data/idol_faces_raw/female|male/
  - 저장: data/idol_faces_cropped_v2/female|male/
  - DB: backend/embeddings_v2.pkl

실행:
  python crop.py
"""

# ─────────────────────────────────────────────
# 1. CUDA DLL 로딩
# ─────────────────────────────────────────────
import os
os.add_dll_directory(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3\bin")

# ─────────────────────────────────────────────
# 2. ONNX Runtime (GPU 확인)
# ─────────────────────────────────────────────
import onnxruntime as ort

providers = ort.get_available_providers()
print("🔥 ONNX Providers:", providers)

if "CUDAExecutionProvider" in providers:
    print("🚀 GPU 활성화 완료")
else:
    print("⚠️ GPU 미사용 (CPU fallback)")

# ─────────────────────────────────────────────
# 3. InsightFace
# ─────────────────────────────────────────────
from insightface.app import FaceAnalysis

# ─────────────────────────────────────────────
# 기타 라이브러리
# ─────────────────────────────────────────────
import cv2
import numpy as np
import pickle
from tqdm import tqdm

# ─────────────────────────────────────────────
# 설정값
# ─────────────────────────────────────────────
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

INPUT_DIR  = DATA_DIR / "idol_faces"
OUTPUT_DIR = DATA_DIR / "idol_faces_cropped_v2"
DB_PATH    = BASE_DIR / "embeddings_v2.pkl"

PAD_RATIO  = 0.10
MIN_SIZE   = 40
RESIZE_TO  = (224, 224)

VALID_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# 모델 로딩
# ─────────────────────────────────────────────
print("🔄 InsightFace 모델 로딩 중...")

face_app = FaceAnalysis(
    name="buffalo_sc",
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
)

face_app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.5)

print("✅ 모델 로딩 완료")

# ─────────────────────────────────────────────
# Crop + Embedding 함수
# ─────────────────────────────────────────────
def process_image(img_path, save_path):
    img = cv2.imread(img_path)
    if img is None:
        return "error", None

    try:
        faces = face_app.get(img)
    except Exception:
        return "error", None

    # ❗ 얼굴 없음
    if len(faces) == 0:
        return "no_face", None

    # ❗ 단체사진 제거
    if len(faces) > 1:
        return "multi_face", None

    face = faces[0]

    x1, y1, x2, y2 = map(int, face.bbox)

    # padding
    h, w = img.shape[:2]
    pad = int(PAD_RATIO * max(x2 - x1, y2 - y1))

    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w - 1, x2 + pad)
    y2 = min(h - 1, y2 + pad)

    cropped = img[y1:y2, x1:x2]

    # ❗ 저화질 제거
    ch, cw = cropped.shape[:2]
    if ch < MIN_SIZE or cw < MIN_SIZE:
        return "small", None

    # resize
    cropped = cv2.resize(cropped, RESIZE_TO)

    # 저장
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    cv2.imwrite(save_path, cropped)

    # embedding
    emb = face.embedding
    emb = emb / np.linalg.norm(emb)

    return "ok", emb


# ─────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────
def main():
    db = {}

    total = ok = no_face = multi_face = small = error = 0

    for gender in ["female", "male"]:
        src_gender = os.path.join(INPUT_DIR, gender)
        dst_gender = os.path.join(OUTPUT_DIR, gender)

        if not os.path.exists(src_gender):
            continue

        for person in os.listdir(src_gender):
            src_folder = os.path.join(src_gender, person)
            dst_folder = os.path.join(dst_gender, person)

            if not os.path.isdir(src_folder):
                continue

            embeddings = []

            print(f"\n👤 처리 중: {gender}/{person}")

            for img_name in tqdm(os.listdir(src_folder)):
                if os.path.splitext(img_name)[1].lower() not in VALID_EXTS:
                    continue

                src_path = os.path.join(src_folder, img_name)
                dst_path = os.path.join(dst_folder, img_name)

                # 이미 존재하면 skip
                if os.path.exists(dst_path):
                    total += 1
                    ok += 1
                    continue

                result, emb = process_image(src_path, dst_path)
                total += 1

                if result == "ok":
                    ok += 1
                    embeddings.append(emb)
                elif result == "no_face":
                    no_face += 1
                elif result == "multi_face":
                    multi_face += 1
                elif result == "small":
                    small += 1
                else:
                    error += 1

            # ── prototype 생성 ──
            if embeddings:
                embeddings = np.array(embeddings)

                proto = embeddings.mean(axis=0)
                proto = proto / np.linalg.norm(proto)

                db[person] = {
                    "embeddings": embeddings,
                    "prototype": proto,
                    "gender": gender,
                    "folder": person,
                }

    # DB 저장
    with open(DB_PATH, "wb") as f:
        pickle.dump(db, f)

    # 통계 출력
    print("\n" + "="*50)
    print(f"✅ 완료: {ok}/{total}")
    print(f"❌ 얼굴없음: {no_face}")
    print(f"❌ 단체사진: {multi_face}")
    print(f"❌ 저화질: {small}")
    print(f"❌ 에러: {error}")
    print(f"💾 DB 저장 완료: {DB_PATH}")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    main()