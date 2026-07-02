# 小红书爆文图文执行包生成器

这是一个本地可运行的 Streamlit 工具，用来根据产品图片和产品资料生成「复制给 ChatGPT 的执行包」。

它不会生成图片，不接入 OpenAI API，不接入任何 IMAGE_API_ENDPOINT，也不会调用任何 AI 图片接口。上传的产品图片只用于本地预览，并提醒你后续需要把产品图一起上传给 ChatGPT。

## 功能

- 上传多张 `jpg/png/webp` 产品图并本地预览
- 填写产品名称、品牌、品类、使用场景、痛点、卖点、功效数据等资料
- 自动整理痛点和卖点
- 自动套用洗衣凝珠类产品的使用步骤
- 生成 Markdown 格式的 ChatGPT 可执行指令包
- 额外输出文章单独复制版、5 张图逐张复制版、JSON 备份版
- 支持下载 Markdown 和 JSON

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

运行后浏览器会打开本地地址，例如：

```text
http://localhost:8501
```

## 封装成 Windows exe

`.exe` 必须在 Windows 电脑上打包。把整个项目文件夹复制到 Windows 后，双击运行：

```text
build_windows.bat
```

打包完成后会生成：

```text
dist\XHS_Package_Generator.exe
```

把这个 exe 发给别人即可。对方双击后会自动启动本地服务，并打开浏览器页面。

注意：

- exe 启动后，本质上仍是在对方电脑本地运行 Streamlit。
- 上传图片和导出的 Markdown/JSON 会保存在 exe 同目录下的 `uploads/` 和 `output/`。
- 如果 Windows 弹出防火墙提示，选择允许本机访问即可。默认只监听 `127.0.0.1`，不会主动对公网开放。

## 封装成当前 Mac 可执行文件

如果是在 macOS 上想生成当前系统可运行的文件，可以执行：

```bash
chmod +x build_macos.sh
./build_macos.sh
```

生成文件在：

```text
dist/XHS_Package_Generator
```

## 使用方式

1. 上传产品图片。
2. 填写产品资料。
3. 点击「生成 ChatGPT 执行包」。
4. 下载或复制 Markdown 执行包。
5. 把执行包和产品图片一起发送给 ChatGPT。

## 项目结构

```text
.
├── app.py
├── launcher.py
├── requirements.txt
├── requirements-build.txt
├── xhs_package_generator.spec
├── build_windows.bat
├── build_macos.sh
├── README.md
├── uploads/
└── output/
```
