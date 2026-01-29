# Auto Learn Platform

浙里学习自动化学习平台，用于自动完成在线课程学习。

## 功能

- 自动登录（支持验证码自动识别或手动输入）
- 自动浏览课程列表
- 自动播放视频并跟踪学习进度
- 支持多页课程遍历
- 登录状态持久化
- 完整的日志记录

## 快速开始（Docker 方式，推荐）

**前置要求：** 安装 [Docker](https://www.docker.com/get-started) 和 Docker Compose

```bash
# 1. 克隆项目
git clone <repo-url>
cd auto-learn-platform

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填写 USERNAME, PASSWORD, CAPTCHA_API_URL, CAPTCHA_API_KEY

# 3. 启动
docker-compose up -d

# 4. 查看日志
docker-compose logs -f
```

## 本地运行

### 环境要求

- Python 3.8+
- Chrome 浏览器
- ChromeDriver（版本需与 Chrome 匹配）

### 安装步骤

1. 克隆项目
```bash
git clone <repo-url>
cd auto-learn-platform
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件填写配置
```

4. 运行
```bash
python main.py
```

## 验证码模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `auto` | 调用 API 自动识别验证码 | Docker 部署、后台运行 |
| `manual` | 弹出图片，用户手动输入验证码 | 本地运行、无 API |

- Docker 模式固定使用 `auto` 模式
- 本地运行时，若未配置 API 会自动切换到 `manual` 模式

## 配置说明

| 配置项 | 说明 | 必填 |
|--------|------|------|
| USERNAME | 登录手机号 | 是 |
| PASSWORD | 登录密码 | 是 |
| CAPTCHA_MODE | 验证码模式（auto/manual） | 否，默认 auto |
| CAPTCHA_API_URL | 验证码识别 API 地址 | auto 模式必填 |
| CAPTCHA_API_KEY | 验证码识别 API 密钥 | auto 模式必填 |
| CHROME_DRIVER_PATH | ChromeDriver 路径 | 否 |
| MAX_PAGES | 最大学习页数 | 否，默认 999 |

## Docker 命令

```bash
# 构建镜像
docker-compose build

# 启动容器（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止容器
docker-compose down

# 重新构建并启动
docker-compose up -d --build
```

## 日志

程序运行日志保存在 `auto_learn.log` 文件中（Docker 模式下在 `./logs/` 目录）。

## 注意事项

- 确保 ChromeDriver 版本与 Chrome 浏览器版本匹配（本地运行时）
- Docker 模式需要配置验证码识别 API
- 建议在稳定网络环境下运行
