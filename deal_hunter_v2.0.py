import json
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 설정/상태 파일명
CONFIG_FILE = "config.json"
STATE_FILE = "last_prices.json"

# -----------------------------------------------------------------
# 1. 파일 관리 기능 (v1.0과 동일)
# -----------------------------------------------------------------
def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ '{CONFIG_FILE}'을 찾을 수 없습니다. 예시로 대체합니다.")
        return [{
            "id": "ccdak", "name": "CCDak 닭갈비 (네이버)",
            "url": "https://brand.naver.com/ccdakgalbi/products/10119281365",
            "target_price": 15000, "css_selector": "span.product_price__2N-Kl",
            "stock_keyword": "품절"
        }]

def load_last_prices():
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_last_prices(prices_state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(prices_state, f, indent=2)

# -----------------------------------------------------------------
# 2. 웹 드라이버 설정 (v2.0 핵심)
# -----------------------------------------------------------------
def setup_driver():
    """Selenium Chrome 드라이버를 설정하고 반환합니다."""
    print("... 🌐 Selenium 웹 드라이버를 설정합니다 ...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 브라우저 창을 숨김 (테스트 시에는 이 줄을 주석 처리)
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # webdriver-manager가 자동으로 드라이버를 다운로드/관리
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    print("... ✅ 드라이버 설정 완료 ...")
    return driver

# -----------------------------------------------------------------
# 3. 핵심 기능: 스크래핑 (v2.0)
# -----------------------------------------------------------------
def get_product_info_selenium(driver, url, css_selector, stock_keyword):
    """
    Selenium을 사용해 URL에 접속하고 정보를 가져옵니다.
    """
    try:
        driver.get(url)
        # 1. 재고 확인 (v2.0: 페이지 전체 텍스트에서 키워드 확인)
        page_text = driver.page_source
        if stock_keyword and stock_keyword in page_text:
            return "품절", None
            
        # 2. 가격 정보 추출 (CSS 선택자 기반)
        #    최대 10초간 해당 요소(css_selector)가 나타날 때까지 기다림
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        price_element = driver.find_element(By.CSS_SELECTOR, css_selector)
        
        price_text = price_element.text
        # 가격 텍스트에서 숫자만 추출
        price_digits = re.sub(r"[^\d\.]", "", price_text)
        
        if price_digits:
            return "재고있음", float(price_digits)
            
    except Exception as e:
        print(f"  [오류] 데이터 분석 실패: {e}")
        return "분석오류", None
        
    return "정보없음", None

# -----------------------------------------------------------------
# 4. 알림 기능 (v1.0과 동일)
# -----------------------------------------------------------------
def send_alert(item, reason, current_price, last_price=None, target_price=None):
    """알림을 보냅니다. (v2.0은 print로 대체)"""
    print("="*40)
    print(f"🎉 ** 가격 변동 알림 ** 🎉")
    print(f"상품: {item['name']}")
    
    if reason == "PRICE_DROP":
        print(f"사유: 가격 하락! ({last_price} -> {current_price})")
    elif reason == "TARGET_HIT":
        print(f"사유: 목표 가격 달성! ({current_price} <= {target_price})")
    
    print(f"링크: {item['url']}")
    print("="*40)

# -----------------------------------------------------------------
# v2.0 실행 (Main)
# -----------------------------------------------------------------
if __name__ == "__main__":
    print("--- Deal-Hunter v2.0 (Selenium) 실행 ---")
    
    config_items = load_config()
    last_prices = load_last_prices()
    new_prices_state = last_prices.copy()
    
    # 드라이버는 한 번만 설정해서 재사용
    driver = setup_driver()

    for item in config_items:
        print(f"\n[추적 중] {item['name']}...")
        
        status, current_price = get_product_info_selenium(
            driver, item['url'], item['css_selector'], item['stock_keyword']
        )
        
        if status == "재고있음":
            print(f"  [확인] 현재 가격: {current_price}")
            
            item_id = item['id']
            last_price = last_prices.get(item_id)
            target_price = item.get('target_price')
            
            if last_price and current_price < last_price:
                send_alert(item, "PRICE_DROP", current_price, last_price=last_price)
            
            if target_price and current_price <= target_price:
                send_alert(item, "TARGET_HIT", current_price, target_price=target_price)
            
            new_prices_state[item_id] = current_price
            
        else:
            print(f"  [확인] 상태: {status}")
            
    driver.quit() # 모든 작업 완료 후 브라우저 종료
    save_last_prices(new_prices_state)
    
    print("\n--- 모든 작업 완료 ---")
