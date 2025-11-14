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
# 1. 파일 관리 기능 (v2.0과 동일)
# -----------------------------------------------------------------
def load_config():
    """설정 파일(config.json)을 읽어옴"""
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
    """이전 가격 상태 파일(last_prices.json)을 읽어옴"""
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_last_prices(prices_state):
    """현재 가격을 상태 파일에 저장"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(prices_state, f, indent=2)

# -----------------------------------------------------------------
# 2. 웹 드라이버 설정 (v2.0과 동일)
# -----------------------------------------------------------------
def setup_driver():
    """Selenium Chrome 드라이버를 설정하고 반환합니다."""
    print("... 🌐 Selenium 웹 드라이버를 설정합니다 ...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 브라우저 창을 숨김
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox") # Linux '봇' 환경에서 필수
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # webdriver-manager가 자동으로 드라이버를 다운로드/관리
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    print("... ✅ 드라이버 설정 완료 ...")
    return driver

# -----------------------------------------------------------------
# 3. 핵심 기능: 스크래핑 (v2.0과 동일)
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
# 4. 알림 기능 (v2.5: 로그 파일 생성)
# -----------------------------------------------------------------
def send_alert(item, reason, current_price, last_price=None, target_price=None):
    """
    v2.5: 이메일 대신 'alert.log' 파일을 생성하여
    GitHub Actions가 커밋 메시지로 사용할 수 있게 합니다.
    """
    print(f"🎉 ** 알림 조건 충족! ** ({item['name']})") # Actions 로그용
    
    alert_message = ""
    if reason == "PRICE_DROP":
        alert_message = f"🎉 가격 하락! {item['name']}: {last_price}원 -> {current_price}원"
    elif reason == "TARGET_HIT":
        alert_message = f"🎯 목표가 달성! {item['name']}: {current_price}원 (목표가: {target_price}원)"
        
    # 'alert.log' 파일에 알림 메시지를 덮어씁니다.
    try:
        with open("alert.log", "w", encoding="utf-8") as f:
            f.write(alert_message)
        print(f"✅ 'alert.log' 파일 생성: {alert_message}")
    except Exception as e:
        print(f"❌ 'alert.log' 파일 생성 실패: {e}")

# -----------------------------------------------------------------
# v2.5 실행 (Main)
# -----------------------------------------------------------------
if __name__ == "__main__":
    print("--- Deal-Hunter v2.5 (Commit Alert) 실행 ---")
    
    config_items = load_config()
    last_prices = load_last_prices()
    new_prices_state = last_prices.copy()
    
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
            
            # (중복 알림 방지) 목표가 달성 알림은 '이전 가격'이 없거나 목표가보다 높았을 때만 보냄
            if last_price and current_price < last_price:
                send_alert(item, "PRICE_DROP", current_price, last_price=last_price)
            elif target_price and current_price <= target_price:
                 if not last_price or last_price > target_price:
                     send_alert(item, "TARGET_HIT", current_price, target_price=target_price)
            
            new_prices_state[item_id] = current_price
            
        else:
            print(f"  [확인] 상태: {status}")
            
    driver.quit()
    save_last_prices(new_prices_state)
    
    print("\n--- 모든 작업 완료 ---")
