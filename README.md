# 得物图文工作流提示词生成器

这是一个本地可运行、也可部署到 Streamlit Cloud 的结构化提示词生成工具。

工具不直接生成图片，不接图片接口，也不需要 OpenAI API Key。它根据用户输入的产品信息，输出一份可以交给 ChatGPT 继续生成「5张图 + 1篇文章」的得物图文内容提示词包。

## 功能

- 上传产品图并本地预览
- 支持 `jpg/jpeg/png/webp/heic/heif`
- HEIC/HEIF 可自动转换为 JPG
- 输入产品名称、品牌名、核心卖点
- 可补充目标人群、使用场景、功效依据、包装重点、禁用词、额外要求
- 支持风格选择器：
  - `ALL`：默认输出 `STYLE_01` 到 `STYLE_10`
  - 单选：只输出一个指定风格
  - 多选：按用户选择顺序输出
- 每组包含：
  - 风格名称
  - 风格说明
  - 5 张图提示词
  - 1 篇文章
  - 8~12 个标签
  - 5~10 个备选标题
- 支持一键复制 Markdown
- 支持导出 Markdown
- 支持导出 JSON
- 本地保存最近一次结果

## 内置风格

- `STYLE_01` 卖点爆点冲击型
- `STYLE_02` 囤货清单推荐型
- `STYLE_03` 脏污救场对比型
- `STYLE_04` 故事带入氛围型
- `STYLE_05` 敏感友好信任型
- `STYLE_06` 真人首图带入型
- `STYLE_07` 萌娃/家庭安全感型
- `STYLE_08` 长期主义效率型
- `STYLE_09` 拼贴生活流型
- `STYLE_10` 高颜值高级感型
- `STYLE_11` 测评对比活力排版型
- `STYLE_12` 宿舍/租房党省心型

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

打开：

```text
http://localhost:8501
```

## Streamlit Cloud 部署

仓库根目录需要包含：

```text
app.py
requirements.txt
README.md
```

部署参数：

```text
Branch: main
Main file path: app.py
```

继续推送到同一个 GitHub 仓库后，Streamlit Cloud 会自动更新，公网网址保持不变。

## HEIC/HEIF

项目通过 `pillow-heif` 转换 HEIC/HEIF。如果部署环境安装失败，工具仍可运行，但会提示用户手动转换 JPG。

```bash
pip install pillow-heif
```
