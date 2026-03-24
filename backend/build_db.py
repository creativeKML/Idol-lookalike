"""
연예인 임베딩 DB 생성  ─  v2 성능 개선 버전
변경사항 (v1 → v2):
  - prototype 키 우선 사용 → 없으면 평균 임베딩 fallback
  - 개별 임베딩 L2 정규화 후 평균 → 재정규화 (프로토타입 품질 향상)
  - augmentation 3배 (원본 + 좌우반전 + 밝기+20) → 데이터 부족 보완
  - DB에 prototype 키 추가 저장 (server.py에서 우선 사용)
  - 임베딩 수 MIN_EMBEDDINGS 미만 시 경고 출력
  - 🔥 CUDA / cuDNN DLL 선 로딩 (GPU 안정성 향상)
  - 🔥 onnxruntime 선 로딩 → CUDAExecutionProvider 안정화
  - 저장: backend/embeddings_v2.pkl (v1 보존)
유지사항:
  - venv 체크
  - female/male 성별 폴더 구조
  - ✅ [저장] / ❌ [스킵] 출력
  - DB 구조 동일 (embeddings, gender, folder 키)
- 원본: data/idol_faces_cropped_v2/female|male/폴더명/
- 저장: backend/embeddings_v2.pkl
- 실행: python build_db.py
"""

# ─────────────────────────────────────────────
# CUDA DLL 경로 (🔥 중요)
# ─────────────────────────────────────────────
import os
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
import sys
import pickle
import cv2
import numpy as np
from insightface.app import FaceAnalysis

# ─────────────────────────────────────────────
# venv 체크
# ─────────────────────────────────────────────
if sys.prefix == sys.base_prefix:
    print("❌ venv가 활성화되지 않았습니다!")
    print("  source venv/Scripts/activate")
    sys.exit(1)
else:
    print(f"✅ venv 활성화 확인: {sys.prefix}")

# ─────────────────────────────────────────────
# [1] 설정
# ─────────────────────────────────────────────
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

SRC_DIR = DATA_DIR / "idol_faces_cropped_v2"
SAVE_PATH = BASE_DIR / "embeddings_v2.pkl"

MIN_EMBEDDINGS = 5
N_AUGMENT      = 2

# ─────────────────────────────────────────────
# [2] InsightFace 초기화
# ─────────────────────────────────────────────
print("🔄 InsightFace 모델 로딩 중...")

app = FaceAnalysis(
    name="buffalo_sc",
    providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
)

app.prepare(ctx_id=0, det_size=(640, 640))

print("✅ 모델 로딩 완료")

# ─────────────────────────────────────────────
# [3] Augmentation 함수
# ─────────────────────────────────────────────
def augment_images(img: np.ndarray) -> list:
    """
    원본 + 좌우반전 + 밝기 +20 → 최대 3장 반환
    """
    results = [img]
    results.append(cv2.flip(img, 1))

    bright = np.clip(img.astype(np.int32) + 20, 0, 255).astype(np.uint8)
    results.append(bright)

    return results

# ─────────────────────────────────────────────
# [4] 임베딩 추출 함수
# ─────────────────────────────────────────────
def get_embedding(img: np.ndarray):
    """
    이미지 → ArcFace 임베딩
    """
    if img is None:
        return None

    try:
        faces = app.get(img)
        if len(faces) == 0:
            return None

        face = max(
            faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
        )

        emb = face.embedding
        emb = emb / np.linalg.norm(emb)

        return emb

    except Exception:
        return None

# ─────────────────────────────────────────────
# [5] 전체 실행
# ─────────────────────────────────────────────
def main():
    db = {}

    total = ok = skip = 0
    warn_list = []

    for gender in ["female", "male"]:
        src_gender = os.path.join(SRC_DIR, gender)
        if not os.path.exists(src_gender):
            continue

        for idol_folder in sorted(os.listdir(src_gender)):
            src_folder = os.path.join(src_gender, idol_folder)
            if not os.path.isdir(src_folder):
                continue

            key  = f"{gender}/{idol_folder}"
            imgs = [f for f in os.listdir(src_folder) if f.endswith(".jpg")]

            print(f"\n📁 {key} ({len(imgs)}장 → 최대 {len(imgs)*3}장)")

            embeddings = []

            for img_name in sorted(imgs):
                img_path = os.path.join(src_folder, img_name)
                img = cv2.imread(img_path)

                if img is None:
                    skip += 1
                    print(f"  ❌ [스킵] {img_name}")
                    continue

                aug_ok = 0

                for aug_img in augment_images(img):
                    total += 1
                    emb = get_embedding(aug_img)

                    if emb is not None:
                        embeddings.append(emb)
                        ok += 1
                        aug_ok += 1
                    else:
                        skip += 1

                if aug_ok > 0:
                    print(f"  ✅ {img_name} ({aug_ok}개)")
                else:
                    print(f"  ❌ [스킵] {img_name}")

            # ── 임베딩 부족 경고 ──
            if len(embeddings) < MIN_EMBEDDINGS:
                warn_list.append(f"{key}: {len(embeddings)}개")

            # ── prototype 생성 ──
            if embeddings:
                emb_array = np.array(embeddings)

                mean_emb  = emb_array.mean(axis=0)
                prototype = mean_emb / np.linalg.norm(mean_emb)

                db[key] = {
                    "embeddings": embeddings,
                    "prototype": prototype,
                    "gender": gender,
                    "folder": idol_folder,
                }

    # 저장
    with open(SAVE_PATH, "wb") as f:
        pickle.dump(db, f)

    print("\n" + "="*40)
    print(f"✅ 완료: {ok}/{total}")
    print(f"❌ 스킵: {skip}")
    print(f"👥 연예인 수: {len(db)}명")
    print(f"💾 저장 경로: {SAVE_PATH}")

    if warn_list:
        print(f"\n⚠️ 임베딩 부족 ({MIN_EMBEDDINGS}개 미만):")
        for w in warn_list:
            print(f"  - {w}")

# ─────────────────────────────────────────────
if __name__ == "__main__":
    main()