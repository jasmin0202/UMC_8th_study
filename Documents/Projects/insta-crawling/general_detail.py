from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import csv

# 셀레니움 브라우저 설정
options = webdriver.ChromeOptions()
options.add_argument('--window-size=1920,1080')
options.add_argument('--headless')  # 디버깅시 끄기
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 시작 URL
base_url = "https://www.generalidea.co.kr"
start_url = base_url + "/product/list.html?cate_no=353&sort_method=5#Product_ListMenu"
driver.get(start_url)
time.sleep(3)

page_count = 1
max_pages = 2

result_data = []

# 천천히 스크롤 끝까지 내려주는 실전용
import time

def slow_scroll_to_bottom(driver, step_size=300, pause_time=0.3):
    last_height = driver.execute_script("return document.body.scrollHeight")
    current_position = 0
    
    while current_position < last_height:
        # 조금씩 내려감
        driver.execute_script(f"window.scrollTo(0, {current_position});")
        time.sleep(pause_time)
        current_position += step_size

        # 현재 페이지 높이 계속 업데이트 (중간에 높이 늘어날 수 있음)
        last_height = driver.execute_script("return document.body.scrollHeight")
    
    # 마지막으로 완전히 내려줌 (혹시 부족할 수 있으니까)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)



while page_count <= max_pages:
    print(f"{page_count} 페이지 수집 중...")

    products = driver.find_elements(By.CSS_SELECTOR, "ul.prdList li[id^='anchorBoxId_']")

    product_links = []
    for p in products:
        try:
            inner_html = p.get_attribute('innerHTML')
            soup = BeautifulSoup(inner_html, 'html.parser')

            # 이미지 (thumber_2 우선, 없으면 thumber_1)
            img_tag = soup.select_one('.thumbnail .prdImg img.thumber_2') or soup.select_one('.thumbnail .prdImg img.thumber_1')
            img = img_tag['src'] if img_tag else '이미지 없음'
            if img.startswith("//"):
                img = "https:" + img

            # 상품명
            name_tag = soup.select_one('.description .name a')
            if name_tag:
                name_raw = name_tag.text
                name = name_raw.split(':')[-1].strip()
            else:
                name = '상품명 없음'

            # 가격
            price_li = soup.select_one('li.product_price')
            if price_li:
                full_text = price_li.get_text(separator=' ', strip=True)
                price_candidates = [part for part in full_text.split() if '₩' in part]
                price = price_candidates[0] if price_candidates else '가격 없음'
            else:
                price = '가격 없음'

            # 상세페이지 링크
            link_tag = soup.select_one('div.prdImg a')
            relative_link = link_tag['href'] if link_tag else ''
            link = base_url + relative_link

            product_links.append((name, price, img, link))

        except Exception as e:
            print("리스트 수집 에러:", e)

    # 상세페이지 진입
    for name, price, img, link in product_links:
        try:
            driver.get(link)
            time.sleep(2)

            slow_scroll_to_bottom(driver)

            detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
            prd_detail = detail_soup.select_one('#prdDetailContentLazy')

            if prd_detail:
                img_tags = prd_detail.select('img')
                if len(img_tags) >= 2:
                    detail_img = img_tags[-2].get('src')
                    if detail_img.startswith("//"):
                        detail_img = "https:" + detail_img
                else:
                    detail_img = '상세 이미지 부족'
            else:
                detail_img = '상세정보 없음'

            print(f"상품명: {name} | 가격: {price} | 썸네일: {img} | 상세이미지: {detail_img}\n")

            result_data.append({
                '상품명': name,
                '가격': price,
                '썸네일이미지': img,
                '상세이미지': detail_img,
                '상세페이지링크': link
            })

            # 다시 리스트 페이지로 복귀
            driver.get(start_url)
            time.sleep(3)

            # 원래 페이지까지 다시 넘어가기
            for _ in range(page_count - 1):
                next_buttons = driver.find_elements(By.CSS_SELECTOR, 'a.first_nt')
                if len(next_buttons) >= 2:
                    next_buttons[1].click()
                    time.sleep(2)

        except Exception as e:
            print("상세페이지 진입 에러:", e)

    # 다음 페이지 이동
    try:
        next_buttons = driver.find_elements(By.CSS_SELECTOR, 'a.first_nt')
        if len(next_buttons) >= 2:
            next_buttons[1].click()
            time.sleep(3)
            page_count += 1
        else:
            print("다음 페이지 없음. 종료")
            break
    except Exception as e:
        print("페이지 이동 중 에러:", e)
        break

driver.quit()
print("모든 페이지 크롤링 완료!")

# CSV 저장
keys = ['상품명', '가격', '썸네일이미지', '상세이미지', '상세페이지링크']
with open('generalidea_product_detail.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader()
    for data in result_data:
        writer.writerow(data)

print("CSV 저장 완료!")

