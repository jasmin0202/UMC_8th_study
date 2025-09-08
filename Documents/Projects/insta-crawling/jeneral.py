from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

# 셀레니움 브라우저 설정
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 시작 URL
base_url = "https://www.generalidea.co.kr"
start_url = base_url + "/product/list.html?cate_no=353&sort_method=5&page=1"
driver.get(start_url)
time.sleep(3)

page_count = 1
max_pages = 2

while page_count <= max_pages:
    print(f"{page_count} 페이지 수집 중...")

    products = driver.find_elements(By.CSS_SELECTOR, "ul.prdList li")
    for p in products:
        try:
            # 이미지 (우선 thumber_2, 없으면 thumber_1)
            img_tags = p.find_elements(By.CSS_SELECTOR, 'img.thumber_2, img.thumber_1')
            img = img_tags[0].get_attribute('src') if img_tags else "이미지 없음"

            # 상품명
            name_spans = p.find_elements(By.CSS_SELECTOR, '.description .name a span[style]').text

            name = name_spans[0].text if name_spans else "상품명 없음"

            # 가격
            price = p.find_element(By.CSS_SELECTOR, 'div.description > ul > li.product_price.xans-record- > span:nth-child(2)').text

            # 상세 링크 (상대경로 → 절대경로 변환)
            relative_link = p.find_element(By.CSS_SELECTOR, 'div.prdImg a').get_attribute('href')
            link = "https://www.generalidea.co.kr" + relative_link

            print(f"상품명: {name} | 가격: {price} | 링크: {link} | 이미지: {img}")

        except Exception as e:
            print("에러 발생:", e)
            break



    # 다음 페이지 이동 (네가 페이지 이동 방식 확인 필요)
    try:
        next_button = driver.find_element(By.CSS_SELECTOR, 'a.first_nt')
        next_button.click()
        time.sleep(3)
        page_count += 1
    except:
        print("다음 페이지 없음. 종료")
        break

driver.quit()
print("모든 페이지 크롤링 완료!")

