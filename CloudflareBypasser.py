import time
from DrissionPage import ChromiumPage
import os
import logging
from utils import get_browser_path, check_cf_clearance, LOG_LANG, check_turnstile_token


class CloudflareBypasser:
    def __init__(self, driver: ChromiumPage, max_retries=-1, log=True):
        self.driver = driver
        self.max_retries = max_retries
        self.log = log
        self.log_lang = LOG_LANG  # 使用全局定义的LOG_LANG

    def search_recursively_shadow_root_with_iframe(self, ele):
        if ele.shadow_root:
            if ele.shadow_root.child().tag == "iframe":
                return ele.shadow_root.child()
        else:
            for child in ele.children():
                result = self.search_recursively_shadow_root_with_iframe(child)
                if result:
                    return result
        return None

    def search_recursively_shadow_root_with_cf_input(self, ele):
        if ele.shadow_root:
            if ele.shadow_root.ele("tag:input"):
                return ele.shadow_root.ele("tag:input")
        else:
            for child in ele.children():
                result = self.search_recursively_shadow_root_with_cf_input(child)
                if result:
                    return result
        return None

    def locate_cf_button(self,turnstile=False):
        button = None
        eles = self.driver.eles("tag:input")
        for ele in eles:
            if "name" in ele.attrs.keys() and "type" in ele.attrs.keys():
                if "turnstile" in ele.attrs["name"] and ele.attrs["type"] == "hidden":
                    button = ele.parent().shadow_root.child()("tag:body").shadow_root("tag:input")
                    break

        if button:
            return button
        else:
            # If the button is not found, search it recursively
            self.log_message("基础搜索失败，正在递归查找按钮...")
            self.log_message("基础搜索失败，可能是过盾跳转太慢先检查是否已成功...")
            if check_cf_clearance(self.driver,retries=3):
                if turnstile:
                    if check_turnstile_token(self.driver):
                        return "success"
                else:
                    return "success"
            ele = self.driver.ele("tag:body")
            iframe = self.search_recursively_shadow_root_with_iframe(ele)
            if iframe:
                button = self.search_recursively_shadow_root_with_cf_input(iframe("tag:body"))
            else:
                self.log_message("未找到iframe，按钮搜索失败")
            return button

    def log_message(self, message):
        if self.log:
            if self.log_lang == "en":
                # 英文日志翻译
                translations = {
                    "基础搜索失败，正在递归查找按钮...": "Basic search failed. Searching for button recursively...",
                    "未找到iframe，按钮搜索失败": "Iframe not found. Button search failed",
                    "找到验证按钮，尝试点击...": "Verification button found. Attempting to click",
                    "未找到验证按钮": "Verification button not found",
                    "点击验证按钮时出错": "Error clicking verification button",
                    "检查页面标题时出错": "Error checking page title",
                    "超过最大重试次数，绕过失败": "Exceeded maximum retries. Bypass failed",
                    "尝试 {0}: 检测到验证页面，正在尝试绕过...": "Attempt {0}: Verification page detected. Trying to bypass...",
                    "成功绕过验证": "Bypass successful",
                    "绕过验证失败": "Bypass failed",
                    "成功绕过turnstile前的challenge验证": "Successfully bypassed challenge verification before turnstile",
                    "绕过turnstile前的challenge验证失败": "Failed to bypass challenge verification before turnstile",
                    "成功绕过turnstile验证": "Successfully bypassed turnstile verification",
                    "绕过turnstile验证失败": "Failed to bypass turnstile verification",
                    "检查turnstile时出错": "Error checking turnstile"
                }
                message = translations.get(message, message)
            logging.info(message)

    def click_verification_button(self, turnstile=False):
        try:
            button = self.locate_cf_button(turnstile)
            if button=="success":
                self.log_message("过盾成功")
                return True
            if button:
                self.log_message("找到验证按钮，尝试点击...")
                button.click()
            else:
                self.log_message("未找到验证按钮")
        except Exception as e:
            self.log_message(f"点击验证按钮时出错: {e}")

    def is_bypassed(self):
        try:
            title = self.driver.title.lower()
            title_check = "just a moment" not in title and "请稍候…" not in title
            clearance_check = False
            if title_check:
                clearance_check = check_cf_clearance(self.driver)
            return title_check or clearance_check
        except Exception as e:
            self.log_message(f"检查页面标题时出错: {e}")
            return False

    def is_turnstile(self):
        try:
            turnstile = self.driver.ele('tag:input@name=cf-turnstile-response')
            turnstile_token = turnstile.value
            if turnstile_token:
                # print(turnstile_token)
                return turnstile_token
            else:
                return ""
        except Exception as e:
            self.log_message(f"检查turnstile时出错: {e}")
            return ""

    def bypass(self):
        try_count = 0
        while not self.is_bypassed():
            if 0 < self.max_retries + 1 <= try_count:
                self.log_message("超过最大重试次数，绕过失败")
                break
            self.log_message(f"尝试 {try_count + 1}: 检测到验证页面，正在尝试绕过...")
            self.click_verification_button()
            try_count += 1
            time.sleep(2)
        if self.is_bypassed():
            self.log_message("成功绕过验证")
        else:
            self.log_message("绕过验证失败")

    def bypass_turnstile(self):
        try_count = 0
        while not self.is_bypassed():
            if 0 < self.max_retries + 1 <= try_count:
                self.log_message("超过最大重试次数，绕过失败")
                break
            self.log_message(f"尝试 {try_count + 1}: 检测到验证页面，正在尝试绕过...")
            self.click_verification_button()
            try_count += 1
            time.sleep(2)
        if self.is_bypassed():
            self.log_message("成功绕过turnstile前的challenge验证")
        else:
            self.log_message("绕过turnstile前的challenge验证失败（可能没有5秒盾，继续处理Turnstile）")
        # 处理 Turnstile：增加等待时间，因为 Turnstile 可能需要更长时间自动完成
        try_count = 0
        max_turnstile_wait = 30  # 最多等待30次（60秒）
        while not self.is_turnstile():
            if try_count >= max_turnstile_wait:
                self.log_message("Turnstile等待超时，停止等待")
                break
            if 0 < self.max_retries + 1 <= try_count:
                self.log_message("超过最大重试次数，但继续等待Turnstile自动完成...")
                # 即使超过重试次数，也继续等待，因为 Turnstile 可能需要更长时间
            if try_count == 0:
                self.log_message("等待Turnstile验证自动完成...")
            elif try_count % 5 == 0:  # 每5次（10秒）输出一次日志
                self.log_message(f"等待Turnstile验证中... (已等待 {try_count * 2} 秒)")
            self.click_verification_button(turnstile=True)
            try_count += 1
            time.sleep(2)  # 每次等待2秒
        if self.is_turnstile():
            self.log_message("成功绕过turnstile验证")
        else:
            self.log_message("绕过turnstile验证失败（可能超时或需要手动交互）")
