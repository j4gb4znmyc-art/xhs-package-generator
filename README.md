# 得物图文风格执行包生成器

这是一个本地可运行、也可部署到 Streamlit Cloud 的图文执行包生成工具。

工具目标不是直接生成图片，也不接入 OpenAI API 或图片生成接口。它会根据用户上传的产品图和补充资料，生成一份可以复制给 ChatGPT 的「得物图文执行包」。用户把执行包和产品图一起发给 ChatGPT 后，可让 ChatGPT 按不同风格输出图文内容。

## 核心功能

- 上传 `jpg/jpeg/png/webp/heic/heif` 产品图
- 自动保存原图到 `uploads/`
- 自动校正图片方向
- HEIC/HEIF 转 JPG，转换后保存到 `uploads/converted/`
- 图片预览
- 填写产品名称、品牌、品类、卖点、目标人群、使用场景、检测/专利/认证信息
- 内置 14 组得物图文风格库
- 自动匹配默认 10 组不同风格
- 每组生成 1 篇种草文章和 5 张独立图片提示词
- 输出用户摘要、ChatGPT 执行包、JSON 备份
- 支持复制、导出 Markdown、导出 JSON
- 本地保存最近一次结果到 `output/latest_dewu_package.json`

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

运行后打开：

```text
http://localhost:8501
```

## HEIC/HEIF 支持

项目通过 `pillow-heif` 支持 HEIC/HEIF 转 JPG。如果安装失败，工具仍可运行，但 HEIC/HEIF 会提示用户手动转换为 JPG 后再上传。

手动安装：

```bash
pip install pillow-heif
```

## 部署到 Streamlit Cloud

仓库根目录需要包含：

```text
app.py
requirements.txt
README.md
```

Streamlit Cloud 部署参数：

```text
Branch: main
Main file path: app.py
```

只要继续推送到同一个 GitHub 仓库，Streamlit Cloud 会自动更新，公网网址保持不变。

## 项目结构

```text
.
├── app.py
├── requirements.txt
├── README.md
├── uploads/
│   └── converted/
└── output/
```

## 合规说明

- 本工具不读取图片中文字，不做 AI 识别。
- 用户未填写、图片不可确认的信息，会写为“图片不可确认”。
- 检测、专利、认证、功效数据只使用用户明确输入的信息。
- 输出执行包会强调产品包装、LOGO、颜色、形状、规格和可见文字以用户上传图为准。
