from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
from bs4 import BeautifulSoup
import csv
import requests

# 셀레니움 셋업
options = webdriver.ChromeOptions()
options.add_argument('--window-size=1920,1080')
# options.add_argument('--headless')  # 디버깅 시 주석
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

base_url = "https://slowand.com"
start_url = base_url + "/product/list.html?cate_no=66"
driver.get(start_url)
time.sleep(2)

page_count = 1
max_pages = 2
result_data = []

while page_count <= max_pages:
    print(f"{page_count} 페이지 수집 중...")

    products = driver.find_elements(By.CSS_SELECTOR, "ul.prdList li[id^='anchorBoxId_']")
    product_links = []

    for p in products:
        try:
            inner_html = p.get_attribute('innerHTML')
            soup = BeautifulSoup(inner_html, 'html.parser')

            name_tag = soup.select_one('.description .name a')
            name = name_tag.text.strip() if name_tag else '상품명 없음'

            img_tag = soup.select_one('.prdImg img')
            img = img_tag['src'] if img_tag else '이미지 없음'
            img = "https:" + img if img.startswith("//") else img

            link_tag = soup.select_one('.prdImg a')
            relative_link = link_tag['href'] if link_tag else ''
            link = base_url + relative_link

            product_links.append((name, img, link))
        except Exception as e:
            print("링크 수집 에러:", e)

    for name, img, link in product_links:
        try:
            driver.get(link)
            print(f"상세페이지 이동: {name}")
            details = {}

            # 스크롤로 lazy load 유도
            for _ in range(5):
                driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(0.5)

            # iframe 등장 기다림
            time.sleep(3)

            # iframe src 추출만 한다
            iframe = driver.find_element(By.CSS_SELECTOR, "iframe[id^='crema-fit-product-floating']")
            iframe_src = iframe.get_attribute('src')

            # iframe src에 requests 요청
            resp = requests.get(iframe_src)
            detail_soup = BeautifulSoup(resp.text, 'html.parser')

            # 상세 테이블 파싱
            rows = detail_soup.select('.fit_product_combined_fit_product__property_table_content_row')
            for row in rows:
                key = row.select_one('.fit_product_combined_fit_product__property_key').text.strip()
                selected_value = row.select_one('.fit_product_combined_fit_product__property_table_content_col--selected').text.strip()
                details[key] = selected_value

            result_data.append({
                '상품명': name,
                '이미지': img,
                '상세링크': link,
                '안감': details.get('안감', ''),
                '두께감': details.get('두께감', ''),
                '계절감': details.get('계절감', ''),
                '비침': details.get('비침', ''),
                '신축성': details.get('신축성', '')
            })

        except Exception as e:
            print("상세페이지 진입 에러:", e)

    try:
        next_button = driver.find_element(By.CSS_SELECTOR, 'a.next')
        if next_button.is_enabled():
            next_button.click()
            time.sleep(3)
            page_count += 1
        else:
            print("다음 페이지 없음. 종료")
            break
    except:
        print("다음 페이지 없음. 종료")
        break

driver.quit()
print("모든 페이지 크롤링 완료!")

keys = ['상품명', '이미지', '상세링크', '안감', '두께감', '계절감', '비침', '신축성']
with open('slowand_product_detail.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader()
    for data in result_data:
        writer.writerow(data)

print("CSV 저장 완료!")
