import base64
import os
import re
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from dotenv import load_dotenv

ZJCE_VIDEO_LIST_PATH = "https://www.zjce.gov.cn/videos"
load_dotenv()

def main():
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    chrome_service = Service("/Users/tommenx/Package/chromedriver-mac-arm64/chromedriver")
    chrome_options = Options()
    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

    # 尝试复用登录状态
    cookies_path = "cookies.pkl"
    if os.path.exists(cookies_path):
        driver.get(ZJCE_VIDEO_LIST_PATH)
        import pickle
        with open(cookies_path, "rb") as f:
            cookies = pickle.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
        driver.refresh()
        time.sleep(2)
        if is_logged_in(driver):
            print("已复用登录状态，无需重新登录。")
        else:
            print("登录状态失效，重新登录。")
            login_and_save_cookies(driver, username, password, cookies_path)
    else:
        login_and_save_cookies(driver, username, password, cookies_path)
    page_num = 1
    while True:
        print(f"当前页码: {page_num}")
        courses = find_courses(driver)
        learn_courses(driver, courses)
        # 尝试点击下一页
        driver.get(ZJCE_VIDEO_LIST_PATH)
        page_num += 1
        page_btn = driver.find_element(By.CSS_SELECTOR, f"li[title='{page_num}']")
        page_btn.click()
        time.sleep(5)


def learn_courses(driver, courses):
    for course in courses:
        course.click()
        time.sleep(2)
        window_handles = driver.window_handles  # 每次点击后重新获取
        driver.switch_to.window(window_handles[-1])
        learn_one_course(driver)
        time.sleep(5)
        driver.switch_to.window(window_handles[0])


def learn_one_course(driver):
    time.sleep(5)
    set_name = driver.find_element(By.CLASS_NAME, "set-name").text
    print(f"开始学习{set_name}")
    video_list = driver.find_element(By.CLASS_NAME, "scroll-set").find_elements(By.TAG_NAME, "li")
    for video in video_list:
        video.click()
        time.sleep(1)
        video_title = video.find_element(By.CLASS_NAME, "set-title").text
        video_progress = video.find_element(By.CLASS_NAME, "set-progress").text
        cur_percent = int(re.search(r"\d+", video_progress).group())
        print(f"正在学习视频: {video_title},{video_progress}")
        if cur_percent == 100:
            print(f"{video_title}视频已完成，跳过")
            continue
        time.sleep(2)
        while cur_percent < 100:
            print(f"当前视频进度: {cur_percent}%")
            last_precent = cur_percent
            time.sleep(60)
            video_progress = video.find_element(By.CLASS_NAME, "set-progress").text
            cur_percent = int(re.search(r"\d+", video_progress).group())
        if  last_precent >= cur_percent:
            print(f"视频进度未变化，疑似暂停，点击播放视频...{cur_percent}%")
            cur_play_video = driver.find_element(By.CLASS_NAME, "dplayer-video-wrap").find_element(By.TAG_NAME, "video")
            cur_play_video.click()
        

def login(driver, username, password):
    driver.get(ZJCE_VIDEO_LIST_PATH)
    time.sleep(2)
    # 1. 选择密码登录
    login_types = driver.find_element(By.CLASS_NAME,"section-type").find_elements(By.TAG_NAME, "span")
    print(len(login_types))
    if len(login_types) == 6:
        print("找到密码登录选项，正在切换...")
        login_types[2].click()  # 点击“密码登录”
    else:
        print("未找到密码登录选项，请检查页面结构。")
        return
    time.sleep(1)
    # 2. 填充手机号和密码
    phone_input = driver.find_element(By.XPATH, "//input[@placeholder='请输入手机号码']")
    phone_input.send_keys(username)
    time.sleep(1)
    pwd_input = driver.find_element(By.XPATH, "//input[@placeholder='请输入密码']")
    pwd_input.send_keys(password)
    time.sleep(1)
    # 获取验证码图片并识别
    captcha_img = driver.find_element(By.XPATH, "//img[@alt='图形验证码']")
    captcha_img.screenshot("./captcha.png")
    captcha_code = verify("./captcha.png")
    if not captcha_code:
        print("验证码识别失败，请重试")
        return
    captcha_input = driver.find_element(By.XPATH, "//input[@placeholder='请输入图形验证码']")
    captcha_input.send_keys(captcha_code)
    time.sleep(2)
    # 3. 点击登录按钮
    login_btn = driver.find_element(By.XPATH, "//button[contains(.,'登 录')]")
    login_btn.click()
    print("已点击“登录”按钮。")
    time.sleep(5)
    driver.get(ZJCE_VIDEO_LIST_PATH)
    print("登录成功")

def verify(captcha_png_path):
    response = None
    with open(captcha_png_path, 'rb') as f:
        b = base64.b64encode(f.read()).decode()
        url = os.getenv("CAPTCHA_API_URL")
        data = {
            "token": os.getenv("CAPTCHA_API_KEY"),
            "type": "10110",
            "image": b,
        }
        _headers = {
            "Content-Type": "application/json"
        }
        response = requests.request("POST", url, headers=_headers, json=data).json()
        print(response)
    if response and response['code'] == 10000:
        return response['data']['data']
    return None

def find_courses(driver):
    print("开始查找课程")
    driver.get(ZJCE_VIDEO_LIST_PATH)
    time.sleep(2)
    try:
        course_list = driver.find_element(By.CLASS_NAME, "video-wrapper").find_elements(By.TAG_NAME, "li")
        print(f"共找到{len(course_list)}个课程")
        return course_list
    except Exception as e:
        print(f"查找课程时发生异常: {e}")
        return []
    finally:
        time.sleep(2)

def is_logged_in(driver):
    try:
        # 根据实际页面内容调整判断条件
        driver.find_element(By.XPATH, "//*[contains(text(),'热门榜单')]")
        return True
    except:
        return False

def login_and_save_cookies(driver, username, password, cookies_path):
    login(driver, username, password)
    # 登录后保存cookies
    import pickle
    cookies = driver.get_cookies()
    with open(cookies_path, "wb") as f:
        pickle.dump(cookies, f)
    print("登录状态已保存，下次可复用。")

if __name__ == "__main__":
    main()