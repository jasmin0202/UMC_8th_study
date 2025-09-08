from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv
from bs4 import BeautifulSoup

# 셀레니움 셋업
options = webdriver.ChromeOptions()
options.add_argument('--window-size=1920,1080')
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

base_url = "https://www.uniqlo.com/kr/ko/women/shirts-and-blouses"

driver.get(base_url)
time.sleep(3)

# 무한스크롤
SCROLL_PAUSE_TIME = 1.5
prev_height = driver.execute_script("return document.body.scrollHeight")

while True:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(SCROLL_PAUSE_TIME)
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == prev_height:
        break
    prev_height = new_height

print("스크롤 완료. 상품링크 수집 시작.")

# 상품 링크 수집
product_elements = driver.find_elements(By.CSS_SELECTOR, "div.fr-ec-product-tile-resize-wrapper a.fr-ec-tile")
product_links = [elem.get_attribute("href") for elem in product_elements]

print(f"총 {len(product_links)}개 상품 발견.\n")

result_data = []

# 상세페이지 진입
for idx, link in enumerate(product_links):
    print(f"\n[{idx+1}/{len(product_links)}] 상세페이지 수집 중: {link}")
    try:
        driver.get(link)
        time.sleep(2)  # 렌더링 대기

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 상품명
        try:
            name = soup.select_one("h1.fr-ec-display").text.strip()
        except:
            name = ''

        # 가격 (조정됨)
        try:
            price = soup.select_one("p.fr-ec-price-text").text.strip()
        except:
            price = ''

        # 기능 세부 정보 (수정된 파싱)
        features = {'비침':'', '핏':'', '포켓':''}
        feature_dd = soup.select_one('#productLongDescription-content dd')
        if feature_dd:
            lines = list(feature_dd.stripped_strings)
            for item in lines:
                if item.startswith('- '):  # '- 비침: 없음' 형태
                    parts = item[2:].split(':', 1)
                    if len(parts) == 2:
                        key, value = parts
                        key, value = key.strip(), value.strip()
                        if key in features:
                            features[key] = value
        else:
            print("※ 기능 세부정보 없음")

        # 소재
        material_dl = soup.select_one('#productMaterialDescription-content dl')
        material = ''
        if material_dl:
            for dt in material_dl.select('dt'):
                if dt.text.strip() == '소재':
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        material = dd.text.strip()

        # 디버깅 로그
        print(f"상품명: {name}")
        print(f"가격: {price}")
        print(f"비침: {features['비침']} / 핏: {features['핏']} / 포켓: {features['포켓']}")
        print(f"소재: {material}")

        result_data.append({
            '상품명': name,
            '가격': price,
            '상세링크': link,
            '비침': features['비침'],
            '핏': features['핏'],
            '포켓': features['포켓'],
            '소재': material
        })

    except Exception as e:
        print("상세페이지 수집 에러:", e)
        continue

driver.quit()

# CSV 저장
keys = ['상품명', '가격', '상세링크', '비침', '핏', '포켓', '소재']
with open('uniqlo_product_detail_fixed.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader()
    for data in result_data:
        writer.writerow(data)

print("\nCSV 저장 완료!")
