# Auto Learn Platform

自动化学习平台，用于自动完成在线课程学习。

## 功能

- 自动登录（支持验证码识别）
- 自动浏览课程列表
- 自动播放视频并跟踪学习进度
- 支持多页课程遍历
- 登录状态持久化
- 完整的日志记录

## 环境要求

- Python 3.8+
- Chrome 浏览器
- ChromeDriver

## 安装

1. 克隆项目
```bash
git clone 
cd auto-learn-platform
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：
```bash
cp .env.example .env
```

编辑 `.env` 文件：
```env
USERNAME=your_phone_number
PASSWORD=your_password
CAPTCHA_API_URL=https://api.example.com/captcha
CAPTCHA_API_KEY=your_api_key_here
CHROME_DRIVER_PATH=/usr/local/bin/chromedriver
MAX_PAGES=999
```

## 使用方法

### 本地运行

```bash
python main.py
```

### Docker 运行

1. 构建镜像
```bash
docker-compose build
```

2. 启动容器
```bash
docker-compose up -d
```

3. 查看日志
```bash
docker-compose logs -f
```

## 配置说明

| 配置项 | 说明 | 必填 |
|--------|------|------|
| USERNAME | 登录手机号 | 是 |
| PASSWORD | 登录密码 | 是 |
| CAPTCHA_API_URL | 验证码识别 API 地址 | 是 |
| CAPTCHA_API_KEY | 验证码识别 API 密钥 | 是 |
| CHROME_DRIVER_PATH | ChromeDriver 路径 | 否 |
| MAX_PAGES | 最大学习页数 | 否 |

## 日志

程序运行日志保存在 `auto_learn.log` 文件中。

## 注意事项

- 确保 ChromeDriver 版本与 Chrome 浏览器版本匹配
- 验证码识别需要第三方 API 支持
- 建议在稳定网络环境下运行
