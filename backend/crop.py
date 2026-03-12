"""
연예인 얼굴 Crop
- InsightFace(ArcFace)로 얼굴 감지 + crop
- 얼굴 1개인 사진만 저장 (단체사진 제외)
- 저화질 제외 (100x100 이하)
- 원본: data/idol_faces/female|male/폴더명/
- 저장: data/idol_faces_cropped/female|male/폴더명/
- 사용법: python crop.py
"""

import os
import sys
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
SRC_DIR  = r"C:\workspace\idol_project\data\idol_faces"
DST_DIR  = r"C:\workspace\idol_project\data\idol_faces_cropped"
MIN_SIZE = 100   # 얼굴 최소 크기 (px)
MARGIN   = 30    # 얼굴 주변 여백 (px)

# -----------------------------------------------
# [2] InsightFace 초기화
# -----------------------------------------------
print("🔄 InsightFace 모델 로딩 중...")
app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640))
print("✅ 모델 로딩 완료")

# -----------------------------------------------
# [3] Crop 함수
# -----------------------------------------------
def crop_face(img_path, save_path):
    img = cv2.imread(img_path)
    if img is None:
        return "error"

    try:
        faces = app.get(img)
    except Exception:
        return "error"

    if len(faces) == 0:
        return "no_face"
    if len(faces) > 1:
        return "multi_face"

    face = faces[0]
    x1, y1, x2, y2 = [int(v) for v in face.bbox]

    # 여백 추가
    h, w = img.shape[:2]
    x1 = max(0, x1 - MARGIN)
    y1 = max(0, y1 - MARGIN)
    x2 = min(w, x2 + MARGIN)
    y2 = min(h, y2 + MARGIN)

    cropped = img[y1:y2, x1:x2]

    # 저화질 체크
    ch, cw = cropped.shape[:2]
    if ch < MIN_SIZE or cw < MIN_SIZE:
        return "small"

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    cv2.imwrite(save_path, cropped, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return "ok"

# -----------------------------------------------
# [4] 전체 실행
# -----------------------------------------------
def main():
    total = ok = no_face = multi_face = small = error = 0

    for gender in ["female", "male"]:
        src_gender = os.path.join(SRC_DIR, gender)
        if not os.path.exists(src_gender):
            continue

        for idol_folder in sorted(os.listdir(src_gender)):
            src_folder = os.path.join(src_gender, idol_folder)
            dst_folder = os.path.join(DST_DIR, gender, idol_folder)

            if not os.path.isdir(src_folder):
                continue

            imgs = [f for f in os.listdir(src_folder) if f.endswith(".jpg")]
            print(f"\n📁 {gender}/{idol_folder} ({len(imgs)}장)")

            for img_name in sorted(imgs):
                src_path = os.path.join(src_folder, img_name)
                dst_path = os.path.join(dst_folder, img_name)

                # 이미 crop된 파일은 스킵
                if os.path.exists(dst_path):
                    print(f"  [SKIP] {img_name}")
                    ok += 1
                    total += 1
                    continue

                result = crop_face(src_path, dst_path)
                total += 1

                if result == "ok":
                    ok += 1
                    print(f"  ✅ {img_name}")
                elif result == "no_face":
                    no_face += 1
                    print(f"  ❌ [얼굴없음] {img_name}")
                elif result == "multi_face":
                    multi_face += 1
                    print(f"  ❌ [단체사진] {img_name}")
                elif result == "small":
                    small += 1
                    print(f"  ❌ [저화질] {img_name}")
                elif result == "error":
                    error += 1
                    print(f"  ❌ [에러] {img_name}")

    print(f"\n{'='*40}")
    print(f"✅ 완료: {ok}/{total}장")
    print(f"❌ 얼굴없음: {no_face} | 단체사진: {multi_face} | 저화질: {small} | 에러: {error}")
    print(f"📁 저장 경로: {DST_DIR}")

def print_stats(min_count=30):
    """crop된 사진 수량 확인 (min_count 미만인 연예인 출력)"""
    print(f"\n{'='*40}")
    print(f"📊 crop 결과 통계 ({min_count}장 미만만 표시)")
    print(f"{'='*40}")
    for gender in ["female", "male"]:
        path = os.path.join(DST_DIR, gender)
        if not os.path.exists(path):
            continue
        for folder in sorted(os.listdir(path)):
            imgs = len([f for f in os.listdir(os.path.join(path, folder)) if f.endswith(".jpg")])
            if imgs < min_count:
                print(f"  ⚠️  {gender}/{folder}: {imgs}장")
    print("✅ 통계 완료")

if __name__ == "__main__":
    main()
    print_stats()
