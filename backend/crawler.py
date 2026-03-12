"""
연예인 이미지 크롤러
- Google 이미지 검색으로 연예인 사진 자동 다운로드
- 1명당 50장 목표 (jpg 형식만 저장)
- 빈 번호 채우기 방식 (삭제된 사진 번호부터 재수집)
- 단체사진 제외 (얼굴 1개만)
- 탭 즉시 닫기
- 중복 URL 제외
- 유튜브/동영상 제외
- 사용법: python crawler.py
"""

import os
import time
import requests
import base64
import sys
import numpy as np
import cv2
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

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
SAVE_DIR     = r"C:\workspace\idol_lookalike\data\idol_faces"
TARGET_COUNT = 50

BLOCKED_DOMAINS = [
    "youtube.com", "ytimg.com",
    "tiktok.com", "tiktokcdn.com",
    "twimg.com", "twitter.com",
    "cdninstagram.com",
]

# -----------------------------------------------
# [2] 연예인 목록
# -----------------------------------------------
IDOL_LIST = {
    "장원영 아이브 얼굴":           ("female", "ive_jangwonyoung"),
    "안유진 아이브 얼굴":           ("female", "ive_anyujin"),
    "카리나 에스파 얼굴":           ("female", "aespa_karina"),
    "윈터 에스파 얼굴":             ("female", "aespa_winter"),
    "지젤 에스파 얼굴":             ("female", "aespa_giselle"),
    "닝닝 에스파 얼굴":             ("female", "aespa_ningning"),
    "사쿠라 르세라핌 얼굴":         ("female", "lesserafim_sakura"),
    "김채원 르세라핌 얼굴":         ("female", "lesserafim_chaewon"),
    "허윤진 르세라핌 얼굴":         ("female", "lesserafim_yunjin"),
    "민지 뉴진스 얼굴":             ("female", "newjeans_minji"),
    "하니 뉴진스 얼굴":             ("female", "newjeans_hanni"),
    "해린 뉴진스 얼굴":             ("female", "newjeans_haerin"),
    "다니엘 뉴진스 얼굴":           ("female", "newjeans_danielle"),
    "혜인 뉴진스 얼굴":             ("female", "newjeans_hyein"),
    "미연 여자아이들 얼굴":         ("female", "gidle_miyeon"),
    "소연 여자아이들 얼굴":         ("female", "gidle_soyeon"),
    "아이린 레드벨벳 얼굴":         ("female", "redvelvet_irene"),
    "지수 블랙핑크 얼굴":           ("female", "blackpink_jisoo"),
    "제니 블랙핑크 얼굴":           ("female", "blackpink_jennie"),
    "로제 블랙핑크 얼굴":           ("female", "blackpink_rose"),
    "차은우 아스트로 얼굴":         ("male",   "astro_chaeunwoo"),
    "뷔 방탄소년단 얼굴":           ("male",   "bts_v"),
    "정국 방탄소년단 얼굴":         ("male",   "bts_jungkook"),
    "지민 방탄소년단 얼굴":         ("male",   "bts_jimin"),
    "RM 방탄소년단 얼굴":           ("male",   "bts_rm"),
    "태용 nct 얼굴":                ("male",   "nct_taeyong"),
    "마크 nct 얼굴":                ("male",   "nct_mark"),
    "재현 nct 얼굴":                ("male",   "nct_jaehyun"),
    "도영 nct 얼굴":                ("male",   "nct_doyoung"),
    "성찬 라이즈 얼굴":             ("male",   "riize_sungchan"),
    "원빈 라이즈 얼굴":             ("male",   "riize_wonbin"),
    "성한빈 제로베이스원 얼굴":     ("male",   "zb1_sunghanbin"),
    "장하오 제로베이스원 얼굴":     ("male",   "zb1_zhanghao"),
    "박성훈 엔하이픈 얼굴":         ("male",   "enhypen_parksung"),
    "니키 엔하이픈 얼굴":           ("male",   "enhypen_niki"),
    "연준 투모로우바이투게더 얼굴": ("male",   "txt_yeonjun"),
    "수빈 투모로우바이투게더 얼굴": ("male",   "txt_soobin"),
    "필릭스 스트레이키즈 얼굴":     ("male",   "skz_felix"),
    "현진 스트레이키즈 얼굴":       ("male",   "skz_hyunjin"),
    "방찬 스트레이키즈 얼굴":       ("male",   "skz_bangchan"),
}


# -----------------------------------------------
# [3] 얼굴 감지 (단체사진 제외)
# -----------------------------------------------
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

def has_single_face(img_bytes):
    """얼굴이 정확히 1개인 사진만 True"""
    try:
        img_array = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            return False
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
        return len(faces) == 1
    except Exception:
        return False


# -----------------------------------------------
# [4] 이미지 저장 (jpg 변환)
# -----------------------------------------------
def save_image(url, filepath):
    try:
        if url.startswith("data:image"):
            header, data = url.split(",", 1)
            img_bytes = base64.b64decode(data)
        else:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code != 200:
                return False
            img_bytes = response.content

        # 얼굴 1개 체크
        if not has_single_face(img_bytes):
            return False

        # jpg로 변환 저장
        img_array = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            return False
        cv2.imwrite(filepath, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return True

    except Exception:
        return False


# -----------------------------------------------
# [5] 빈 슬롯 찾기
# -----------------------------------------------
def get_missing_slots(save_path, target):
    """1~target 중 없는 번호 리스트 반환"""
    existing = set(
        int(f.split(".")[0]) for f in os.listdir(save_path)
        if f.lower().endswith(".jpg") and f.split(".")[0].isdigit()
    )
    return [i for i in range(1, target + 1) if i not in existing]


# -----------------------------------------------
# [6] 탭 정리
# -----------------------------------------------
def close_extra_tabs(driver, main_tab):
    try:
        for handle in driver.window_handles:
            if handle != main_tab:
                driver.switch_to.window(handle)
                driver.close()
        driver.switch_to.window(main_tab)
    except Exception:
        try:
            driver.switch_to.window(driver.window_handles[0])
        except Exception:
            pass


# -----------------------------------------------
# [7] 크롬 드라이버
# -----------------------------------------------
def get_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--lang=ko-KR")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return driver


# -----------------------------------------------
# [8] 크롤링
# -----------------------------------------------
def crawl_google_images(driver, query, save_path, target=50):
    os.makedirs(save_path, exist_ok=True)

    # 빈 슬롯 확인
    missing_slots = get_missing_slots(save_path, target)
    if not missing_slots:
        print(f"  [SKIP] 이미 {target}장 ✅")
        return target

    print(f"  빈 슬롯 {len(missing_slots)}개 → 채우기 시작")

    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbm=isch&hl=ko"
    driver.get(url)
    time.sleep(1.5)

    saved = 0
    scroll_count = 0
    seen_urls = set()
    main_tab = driver.window_handles[0]

    while missing_slots and scroll_count < 20:

        # 탭 3개 이상 쌓이면 강제 정리
        try:
            if len(driver.window_handles) >= 3:
                close_extra_tabs(driver, main_tab)
            main_tab = driver.window_handles[0]
        except Exception:
            break

        thumbnails = driver.find_elements(By.CSS_SELECTOR, "img.YQ4gaf")

        for thumb in thumbnails:
            if not missing_slots:
                break
            try:
                driver.execute_script("arguments[0].click();", thumb)
                time.sleep(0.5)

                img_elements = driver.find_elements(
                    By.CSS_SELECTOR, "img.sFlh5c, img.r48jcc"
                )
                for img_el in img_elements:
                    src = img_el.get_attribute("src")
                    if not src or ("http" not in src and not src.startswith("data:")):
                        continue

                    # 동영상 도메인 제외
                    if any(d in src for d in BLOCKED_DOMAINS):
                        continue

                    # 중복 제외
                    if src in seen_urls:
                        continue
                    seen_urls.add(src)

                    # 빈 슬롯에 저장
                    slot = missing_slots[0]
                    filepath = os.path.join(save_path, f"{slot:04d}.jpg")
                    if save_image(src, filepath):
                        missing_slots.pop(0)
                        saved += 1
                        print(f"  [{slot:04d}.jpg] 저장 ({len(missing_slots)}개 남음)")
                        close_extra_tabs(driver, main_tab)
                        break
                    else:
                        print(f"  [SKIP] 단체사진 또는 얼굴 없음")

            except Exception:
                continue

        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
            time.sleep(1.5)
        except Exception:
            break

        scroll_count += 1

        try:
            more_btn = driver.find_element(By.CSS_SELECTOR, ".mye4qd")
            driver.execute_script("arguments[0].click();", more_btn)
            time.sleep(1.5)
        except Exception:
            pass

    close_extra_tabs(driver, main_tab)
    total = target - len(missing_slots)
    print(f"  → 완료: {total}장 ✅")
    return total


# -----------------------------------------------
# [9] 메인
# -----------------------------------------------
def main():
    print("=" * 50)
    print("연예인 이미지 크롤러 시작")
    print(f"총 {len(IDOL_LIST)}명 | 1명당 {TARGET_COUNT}장 목표")
    print("=" * 50)

    driver = get_driver()

    try:
        for idx, (query, (gender, folder_name)) in enumerate(IDOL_LIST.items(), 1):
            save_path = os.path.join(SAVE_DIR, gender, folder_name)
            print(f"\n[{idx}/{len(IDOL_LIST)}] {query} → {gender}/{folder_name}/")
            crawl_google_images(driver, query, save_path, target=TARGET_COUNT)
    finally:
        driver.quit()

    print("\n" + "=" * 50)
    print("크롤링 완료!")
    print(f"저장 경로: {SAVE_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    main()
