from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import StaleElementReferenceException
import time
import csv

# 셀레니움 셋업
options = webdriver.ChromeOptions()
options.add_argument('--window-size=1920,1080')
options.add_argument('--headless')  
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 유니클로 WOMEN 상의 URL
start_url = "https://www.uniqlo.com/kr/ko/women/tops"
driver.get(start_url)
time.sleep(5)  # 첫 로딩 대기

# 스크롤 로딩 함수
def scroll_down_until_end():
    prev_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # 로딩 시간 여유
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == prev_height:
            print("더 이상 로드할 상품 없음. 스크롤 완료.")
            break
        prev_height = new_height

# 스크롤 다운 수행
scroll_down_until_end()

# 모든 상품 가져오기
products = driver.find_elements(By.CSS_SELECTOR, ".fr-ec-product-tile-resize-wrapper")

print(f"총 상품 개수: {len(products)}")

result_data = []

for p in products:
    try:
        name = p.find_element(By.CSS_SELECTOR, "h3.fr-ec-product-tile__end-product-name").text.strip()
        price = p.find_element(By.CSS_SELECTOR, "p.fr-ec-price-text").text.strip()
        img = p.find_element(By.CSS_SELECTOR, ".fr-ec-product-tile__image img").get_attribute("src")
        detail_relative_link = p.find_element(By.CSS_SELECTOR, "a.fr-ec-tile").get_attribute("href")
        detail_link = "https://www.uniqlo.com" + detail_relative_link if detail_relative_link.startswith("/kr/") else detail_relative_link

        try:
            rating = p.find_element(By.CSS_SELECTOR, ".fr-ec-rating-average-product-tile").text.strip()
            review_count = p.find_element(By.CSS_SELECTOR, ".fr-ec-rating-static__count-product-tile").text.strip().replace("(", "").replace(")", "")
        except:
            rating = ""
            review_count = ""

        print(f"상품명: {name}, 가격: {price}, 리뷰: {rating} ({review_count}), 이미지: {img}")

        result_data.append({
            "상품명": name,
            "가격": price,
            "리뷰평점": rating,
            "리뷰수": review_count,
            "이미지": img,
            "상세링크": detail_link
        })

    except StaleElementReferenceException:
        print("Stale element 발생. 스킵")
    except Exception as e:
        print("상품 수집 중 에러:", e)

driver.quit()

# CSV 저장
keys = ['상품명', '가격', '리뷰평점', '리뷰수', '이미지', '상세링크']
with open('uniqlo_full_scroll.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader()
    for data in result_data:
        writer.writerow(data)

print("CSV 저장 완료!")
