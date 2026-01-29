import base64
import os
import re
import time
import requests
import logging
import pickle
from functools import wraps
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_learn.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

ZJCE_VIDEO_LIST_PATH = "https://www.zjce.gov.cn/videos"
COOKIES_PATH = "cookies.pkl"
MAX_RETRIES = 3
TIMEOUT = 10
load_dotenv()


def retry_on_exception(max_retries=MAX_RETRIES, delay=2):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"{func.__name__} 第 {attempt + 1} 次尝试失败: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} 失败，已达最大重试次数")
                        raise
        return wrapper
    return decorator


def safe_find_element(driver, by, value, timeout=TIMEOUT, required=True):
    """安全查找元素，带超时和异常处理"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        logger.debug(f"成功找到元素: {by}={value}")
        return element
    except TimeoutException:
        if required:
            logger.error(f"超时：无法找到元素 {by}={value}")
            raise
        logger.warning(f"未找到元素 {by}={value}，返回 None")
        return None
    except Exception as e:
        logger.error(f"查找元素时发生异常: {by}={value}, 错误: {str(e)}")
        if required:
            raise
        return None


def safe_find_elements(driver, by, value, timeout=TIMEOUT):
    """安全查找多个元素"""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        elements = driver.find_elements(by, value)
        logger.debug(f"成功找到 {len(elements)} 个元素: {by}={value}")
        return elements
    except TimeoutException:
        logger.warning(f"超时：未找到元素 {by}={value}")
        return []
    except Exception as e:
        logger.error(f"查找元素时发生异常: {by}={value}, 错误: {str(e)}")
        return []


def safe_click(element, description="元素"):
    """安全点击元素"""
    try:
        element.click()
        logger.info(f"成功点击: {description}")
        return True
    except Exception as e:
        logger.error(f"点击失败 {description}: {str(e)}")
        return False


def main():
    logger.info("程序启动")
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    if not username or not password:
        logger.error("缺少用户名或密码配置")
        return

    # 配置 Chrome Driver
    chrome_driver_path = os.getenv("CHROME_DRIVER_PATH", "/usr/local/bin/chromedriver")
    chrome_service = Service(chrome_driver_path)
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # chrome_options.add_argument("--headless")  # 可选：启用无界面模式

    driver = None
    try:
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
        logger.info("Chrome 浏览器启动成功")

        # 处理登录
        if not ensure_logged_in(driver, username, password):
            logger.error("登录失败，程序退出")
            return

        # 开始学习课程
        page_num = 1
        max_pages = int(os.getenv("MAX_PAGES", "999"))  # 最大页数限制

        while page_num <= max_pages:
            try:
                logger.info(f"当前页码: {page_num}")
                courses = find_courses(driver)

                if not courses:
                    logger.warning(f"第 {page_num} 页没有找到课程")
                    break

                learn_courses(driver, courses)

                # 尝试翻到下一页
                if not go_to_next_page(driver, page_num + 1):
                    logger.info("没有更多页面，学习完成")
                    break

                page_num += 1
                time.sleep(3)

            except Exception as e:
                logger.error(f"处理第 {page_num} 页时发生错误: {str(e)}")
                # 检查登录状态，如果掉线则重新登录
                if not is_logged_in(driver):
                    logger.warning("检测到登录状态失效，尝试重新登录")
                    if not ensure_logged_in(driver, username, password):
                        logger.error("重新登录失败，程序退出")
                        break
                continue

    except Exception as e:
        logger.error(f"程序运行时发生严重错误: {str(e)}", exc_info=True)
    finally:
        if driver:
            driver.quit()
            logger.info("浏览器已关闭")
        logger.info("程序结束")


def ensure_logged_in(driver, username, password):
    """确保已登录，如果未登录则尝试登录"""
    # 尝试复用登录状态
    if os.path.exists(COOKIES_PATH):
        try:
            logger.info("尝试复用登录状态")
            driver.get(ZJCE_VIDEO_LIST_PATH)
            time.sleep(2)

            with open(COOKIES_PATH, "rb") as f:
                cookies = pickle.load(f)
                for cookie in cookies:
                    try:
                        driver.add_cookie(cookie)
                    except Exception as e:
                        logger.debug(f"添加 cookie 失败: {str(e)}")

            driver.refresh()
            time.sleep(3)

            if is_logged_in(driver):
                logger.info("登录状态有效，成功复用")
                return True
            else:
                logger.info("登录状态似乎已失效，重新加载页面再次确认...")
                # 重新加载页面，再次检查
                driver.get(ZJCE_VIDEO_LIST_PATH)
                time.sleep(3)

                if is_logged_in(driver):
                    logger.info("重新加载后确认登录状态有效")
                    return True
                else:
                    logger.info("确认登录状态已失效，需要重新登录")
        except Exception as e:
            logger.error(f"复用登录状态时发生错误: {str(e)}")

    # 执行登录
    return login_and_save_cookies(driver, username, password)


def go_to_next_page(driver, page_num):
    """尝试翻到下一页"""
    try:
        driver.get(ZJCE_VIDEO_LIST_PATH)
        time.sleep(2)

        page_btn = safe_find_element(
            driver,
            By.CSS_SELECTOR,
            f"li[title='{page_num}']",
            timeout=5,
            required=False
        )

        if page_btn:
            safe_click(page_btn, f"第 {page_num} 页按钮")
            time.sleep(3)
            return True
        else:
            logger.info(f"未找到第 {page_num} 页的按钮")
            return False
    except Exception as e:
        logger.error(f"翻页到第 {page_num} 页失败: {str(e)}")
        return False


def learn_courses(driver, courses):
    """学习所有课程"""
    logger.info(f"准备学习 {len(courses)} 个课程")

    for idx, course in enumerate(courses):
        try:
            logger.info(f"点击第 {idx + 1}/{len(courses)} 个课程")
            window_handles_before = driver.window_handles

            if not safe_click(course, f"课程 {idx + 1}"):
                logger.warning(f"无法点击课程 {idx + 1}，跳过")
                continue

            time.sleep(2)

            # 切换到新窗口
            window_handles_after = driver.window_handles
            if len(window_handles_after) > len(window_handles_before):
                driver.switch_to.window(window_handles_after[-1])
                learn_one_course(driver)
                time.sleep(3)

                # 关闭当前窗口并切回原窗口
                driver.close()
                driver.switch_to.window(window_handles_before[0])
            else:
                logger.warning("没有打开新窗口，可能点击失败")

        except Exception as e:
            logger.error(f"学习第 {idx + 1} 个课程时发生错误: {str(e)}")
            # 尝试切回主窗口
            try:
                driver.switch_to.window(driver.window_handles[0])
            except Exception as switch_error:
                logger.error(f"切换窗口失败: {str(switch_error)}")
            continue


def learn_one_course(driver):
    """学习单个课程的所有视频"""
    try:
        time.sleep(3)

        # 获取课程名称
        set_name_elem = safe_find_element(driver, By.CLASS_NAME, "set-name", timeout=5, required=False)
        set_name = set_name_elem.text if set_name_elem else "未知课程"
        logger.info(f"开始学习课程: {set_name}")

        # 获取视频列表
        scroll_set = safe_find_element(driver, By.CLASS_NAME, "scroll-set", timeout=5, required=False)
        if not scroll_set:
            logger.warning("未找到视频列表容器")
            return

        video_list = scroll_set.find_elements(By.TAG_NAME, "li")
        if not video_list:
            logger.warning("课程中没有视频")
            return

        logger.info(f"找到 {len(video_list)} 个视频")

        for idx, video in enumerate(video_list):
            try:
                # 点击视频
                if not safe_click(video, f"视频 {idx + 1}"):
                    logger.warning(f"无法点击视频 {idx + 1}，跳过")
                    continue

                time.sleep(2)

                # 获取视频信息
                video_title_elem = video.find_element(By.CLASS_NAME, "set-title")
                video_title = video_title_elem.text if video_title_elem else f"视频 {idx + 1}"

                video_progress_elem = video.find_element(By.CLASS_NAME, "set-progress")
                video_progress_text = video_progress_elem.text if video_progress_elem else "0%"

                # 提取进度百分比
                match = re.search(r"\d+", video_progress_text)
                cur_percent = int(match.group()) if match else 0

                logger.info(f"正在学习视频: {video_title}, 当前进度: {video_progress_text}")

                if cur_percent >= 100:
                    logger.info(f"视频 {video_title} 已完成，跳过")
                    continue

                # 等待视频播放
                time.sleep(2)
                last_percent = cur_percent
                check_count = 0
                max_checks = 120  # 最多检查 120 次（约 2 小时）

                while cur_percent < 100 and check_count < max_checks:
                    logger.info(f"视频 {video_title} 当前进度: {cur_percent}%")
                    time.sleep(60)  # 每分钟检查一次

                    # 重新获取进度
                    try:
                        video_progress_elem = video.find_element(By.CLASS_NAME, "set-progress")
                        video_progress_text = video_progress_elem.text
                        match = re.search(r"\d+", video_progress_text)
                        cur_percent = int(match.group()) if match else cur_percent

                        # 如果进度没变化，尝试点击播放
                        if cur_percent <= last_percent:
                            logger.warning(f"视频进度未变化 ({cur_percent}%)，尝试点击播放")
                            try:
                                video_wrap = safe_find_element(
                                    driver,
                                    By.CLASS_NAME,
                                    "dplayer-video-wrap",
                                    timeout=3,
                                    required=False
                                )
                                if video_wrap:
                                    cur_play_video = video_wrap.find_element(By.TAG_NAME, "video")
                                    cur_play_video.click()
                                    logger.info("已点击视频播放")
                            except Exception as play_error:
                                logger.error(f"点击播放失败: {str(play_error)}")

                        last_percent = cur_percent
                        check_count += 1

                    except StaleElementReferenceException:
                        logger.warning("元素已过期，重新获取")
                        break
                    except Exception as progress_error:
                        logger.error(f"获取进度时发生错误: {str(progress_error)}")
                        break

                if cur_percent >= 100:
                    logger.info(f"视频 {video_title} 学习完成")
                else:
                    logger.warning(f"视频 {video_title} 未完成，当前进度 {cur_percent}%")

            except StaleElementReferenceException:
                logger.warning(f"视频 {idx + 1} 元素已过期，跳过")
                continue
            except Exception as video_error:
                logger.error(f"学习视频 {idx + 1} 时发生错误: {str(video_error)}")
                continue

    except Exception as e:
        logger.error(f"学习课程时发生错误: {str(e)}")
        

@retry_on_exception(max_retries=3, delay=3)
def login(driver, username, password):
    """执行登录流程"""
    logger.info("开始登录流程")
    driver.get(ZJCE_VIDEO_LIST_PATH)
    time.sleep(3)

    # 1. 选择密码登录
    section_type = safe_find_element(driver, By.CLASS_NAME, "section-type", timeout=10)
    if not section_type:
        raise Exception("未找到登录类型选择区域")

    login_types = section_type.find_elements(By.TAG_NAME, "span")
    logger.info(f"找到 {len(login_types)} 个登录选项")

    if len(login_types) >= 3:
        logger.info("切换到密码登录")
        if not safe_click(login_types[2], "密码登录选项"):
            raise Exception("无法点击密码登录选项")
    else:
        logger.warning(f"登录选项数量异常: {len(login_types)}")

    time.sleep(2)

    # 2. 填充手机号和密码
    phone_input = safe_find_element(driver, By.XPATH, "//input[@placeholder='请输入手机号码']")
    if not phone_input:
        raise Exception("未找到手机号输入框")

    phone_input.clear()
    phone_input.send_keys(username)
    logger.info("已输入手机号")
    time.sleep(1)

    pwd_input = safe_find_element(driver, By.XPATH, "//input[@placeholder='请输入密码']")
    if not pwd_input:
        raise Exception("未找到密码输入框")

    pwd_input.clear()
    pwd_input.send_keys(password)
    logger.info("已输入密码")
    time.sleep(1)

    # 3. 获取并识别验证码
    captcha_img = safe_find_element(driver, By.XPATH, "//img[@alt='图形验证码']")
    if not captcha_img:
        raise Exception("未找到验证码图片")

    try:
        captcha_img.screenshot("./captcha.png")
        logger.info("已保存验证码图片")
    except Exception as screenshot_error:
        raise Exception(f"保存验证码图片失败: {str(screenshot_error)}")

    captcha_code = verify("./captcha.png")
    if not captcha_code:
        raise Exception("验证码识别失败")

    logger.info(f"验证码识别成功: {captcha_code}")

    captcha_input = safe_find_element(driver, By.XPATH, "//input[@placeholder='请输入图形验证码']")
    if not captcha_input:
        raise Exception("未找到验证码输入框")

    captcha_input.clear()
    captcha_input.send_keys(captcha_code)
    logger.info("已输入验证码")
    time.sleep(2)

    # 4. 点击登录按钮
    login_btn = safe_find_element(driver, By.XPATH, "//button[contains(.,'登 录')]")
    if not login_btn:
        raise Exception("未找到登录按钮")

    if not safe_click(login_btn, "登录按钮"):
        raise Exception("点击登录按钮失败")

    logger.info("已点击登录按钮，等待登录完成")

    # 5. 等待并检查是否有错误提示（验证码错误等）
    time.sleep(3)

    # 检查是否有错误提示
    try:
        error_msg = safe_find_element(
            driver,
            By.XPATH,
            "//*[contains(text(),'验证码错误') or contains(text(),'验证码不正确') or contains(text(),'图形验证码错误')]",
            timeout=2,
            required=False
        )
        if error_msg:
            logger.warning(f"检测到验证码错误提示: {error_msg.text}")
            raise Exception("验证码错误，需要重新识别")
    except TimeoutException:
        # 没有错误提示，继续
        pass

    # 6. 轮询检查登录是否成功（最多等待30秒）
    logger.info("轮询检查登录状态...")
    max_wait_time = 30  # 最多等待30秒
    check_interval = 2  # 每2秒检查一次
    elapsed_time = 0

    while elapsed_time < max_wait_time:
        try:
            # 访问视频列表页面
            driver.get(ZJCE_VIDEO_LIST_PATH)
            time.sleep(2)

            # 检查登录状态
            if is_logged_in(driver):
                logger.info("登录成功")
                return True

            logger.info(f"登录尚未完成，继续等待... ({elapsed_time}/{max_wait_time}秒)")
            time.sleep(check_interval)
            elapsed_time += check_interval + 2  # 加上访问页面的等待时间

        except Exception as check_error:
            logger.warning(f"检查登录状态时发生错误: {str(check_error)}")
            time.sleep(check_interval)
            elapsed_time += check_interval

    # 超时仍未登录成功，抛出异常触发重试
    logger.error(f"登录超时（{max_wait_time}秒内未成功），可能是验证码错误或网络问题")
    raise Exception("登录超时，未能在规定时间内完成登录")

def verify(captcha_png_path):
    """识别验证码，根据配置选择自动识别或手动输入"""
    captcha_mode = os.getenv("CAPTCHA_MODE", "auto").lower()

    # 检查是否需要自动切换到手动模式
    if captcha_mode == "auto":
        url = os.getenv("CAPTCHA_API_URL")
        token = os.getenv("CAPTCHA_API_KEY")
        if not url or not token:
            logger.warning("验证码 API 未配置，自动切换到手动输入模式")
            captcha_mode = "manual"

    if captcha_mode == "manual":
        return verify_manual(captcha_png_path)
    else:
        return verify_auto(captcha_png_path)


def verify_manual(captcha_png_path):
    """手动输入验证码"""
    try:
        import subprocess
        import sys

        logger.info("请查看验证码图片并手动输入验证码")
        logger.info(f"验证码图片路径: {os.path.abspath(captcha_png_path)}")

        # 尝试打开验证码图片（支持多平台）
        try:
            if sys.platform == "darwin":  # macOS
                subprocess.Popen(["open", captcha_png_path])
            elif sys.platform == "win32":  # Windows
                subprocess.Popen(["start", "", captcha_png_path], shell=True)
            else:  # Linux
                subprocess.Popen(["xdg-open", captcha_png_path])

            logger.info("已自动打开验证码图片")
        except Exception as e:
            logger.warning(f"无法自动打开验证码图片: {str(e)}")
            logger.info("请手动打开验证码图片查看")

        # 等待用户输入验证码
        print("\n" + "=" * 50)
        print("请输入验证码（输入后按回车）:")
        print("=" * 50)
        captcha_code = input().strip()

        if captcha_code:
            logger.info(f"用户输入的验证码: {captcha_code}")
            return captcha_code
        else:
            logger.error("验证码输入为空")
            return None

    except Exception as e:
        logger.error(f"手动输入验证码时发生错误: {str(e)}")
        return None


def verify_auto(captcha_png_path):
    """自动识别验证码（调用 API）"""
    try:
        with open(captcha_png_path, 'rb') as f:
            b = base64.b64encode(f.read()).decode()
            url = os.getenv("CAPTCHA_API_URL")
            token = os.getenv("CAPTCHA_API_KEY")

            if not url or not token:
                logger.error("验证码 API 配置缺失")
                return None

            data = {
                "token": token,
                "type": "10110",
                "image": b,
            }
            headers = {
                "Content-Type": "application/json"
            }

            logger.info("发送验证码识别请求")
            response = requests.post(url, headers=headers, json=data, timeout=30).json()
            logger.debug(f"验证码 API 响应: {response}")

            if response and response.get('code') == 10000:
                captcha_result = response.get('data', {}).get('data')
                logger.info(f"验证码识别成功: {captcha_result}")
                return captcha_result
            else:
                logger.error(f"验证码识别失败: {response}")
                return None

    except requests.exceptions.Timeout:
        logger.error("验证码识别请求超时")
        return None
    except Exception as e:
        logger.error(f"验证码识别时发生错误: {str(e)}")
        return None

def find_courses(driver):
    """查找当前页面的所有课程"""
    try:
        logger.info("开始查找课程")
        driver.get(ZJCE_VIDEO_LIST_PATH)
        time.sleep(2)

        video_wrapper = safe_find_element(
            driver,
            By.CLASS_NAME,
            "video-wrapper",
            timeout=10,
            required=False
        )

        if not video_wrapper:
            logger.warning("未找到课程容器")
            return []

        course_list = video_wrapper.find_elements(By.TAG_NAME, "li")
        logger.info(f"找到 {len(course_list)} 个课程")
        return course_list

    except Exception as e:
        logger.error(f"查找课程时发生异常: {str(e)}")
        return []


def is_logged_in(driver):
    """检查是否已登录，使用多种方式验证"""
    time.sleep(2)
    try:
        logger.info("开始检查登录状态...")

        # 方法1: 检查是否存在登录表单（未登录时才有）
        login_form = safe_find_element(
            driver,
            By.XPATH,
            "//input[@placeholder='请输入手机号码']",
            timeout=3,
            required=False
        )
        if login_form:
            logger.info("检测到登录表单，判定为未登录")
            return False
        logger.info("未检测到登录表单")

        # 方法2: 检查是否存在密码登录选项（未登录时才有）
        section_type = safe_find_element(
            driver,
            By.CLASS_NAME,
            "section-type",
            timeout=3,
            required=False
        )
        if section_type:
            logger.info("检测到登录选项区域，判定为未登录")
            return False
        logger.info("未检测到登录选项区域")

        # 方法3: 检查页面标题或其他已登录标识
        # 尝试多个可能的已登录元素
        logged_in_indicators = [
            ("xpath", "//*[contains(text(),'热门榜单')]", "热门榜单"),
            ("xpath", "//*[contains(@class, 'user')]", "用户信息"),
            ("xpath", "//a[contains(@href, 'logout') or contains(text(), '退出')]", "退出按钮"),
            ("xpath", "//*[contains(text(),'个人中心')]", "个人中心"),
        ]

        for by_type, selector, description in logged_in_indicators:
            by = By.XPATH if by_type == "xpath" else By.CLASS_NAME
            element = safe_find_element(
                driver,
                by,
                selector,
                timeout=3,
                required=False
            )
            if element:
                logger.info(f"检测到已登录标识: {description}，判定为已登录")
                return True
            else:
                logger.debug(f"未找到已登录标识: {description}")

        # 如果没有登录表单，但也没找到明确的已登录标识
        # 保守判断：可能已登录（因为没有登录表单）
        logger.warning("未找到明确的已登录标识，但也没有登录表单，保守判定为已登录")

        # 打印当前页面信息用于调试
        try:
            current_url = driver.current_url
            page_title = driver.title
            logger.info(f"当前页面 URL: {current_url}")
            logger.info(f"当前页面标题: {page_title}")
        except:
            pass

        return True

    except Exception as e:
        logger.error(f"检查登录状态时发生错误: {str(e)}")
        return False


def login_and_save_cookies(driver, username, password):
    """登录并保存 cookies"""
    try:
        # login函数现在会在失败时抛出异常，成功时返回True
        login(driver, username, password)

        # 保存 cookies
        try:
            cookies = driver.get_cookies()
            with open(COOKIES_PATH, "wb") as f:
                pickle.dump(cookies, f)
            logger.info(f"登录状态已保存到 {COOKIES_PATH}")
            return True
        except Exception as save_error:
            logger.error(f"保存 cookies 失败: {str(save_error)}")
            # 即使保存失败，登录本身是成功的
            return True

    except Exception as e:
        logger.error(f"登录并保存 cookies 时发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    main()