from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import streamlit as st
from PIL import Image


BASE_DIR = Path(os.environ.get("XHS_GENERATOR_DATA_DIR", Path(__file__).resolve().parent)).resolve()
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

DEFAULT_REFERENCE_STYLE = "小红书家清爆文，真实手机实拍，大字报，痛点红叉，蓝点卖点，Before/After，强种草风格"
DEFAULT_FORBIDDEN_WORDS = [
    "最强",
    "第一",
    "100%",
    "永久",
    "彻底",
    "无毒",
    "零伤害",
    "医学级",
    "医院级",
    "根治",
    "神药",
]
MISPLACED_SELLING_POINT_KEYWORDS = [
    "香氛",
    "留香",
    "婴童可用",
    "118颗大桶装",
    "一颗搞定",
]
LAUNDRY_POD_PAINS = [
    "汗味残留",
    "衣服闷味",
    "宿舍洗衣麻烦",
    "洗衣液倒多倒少",
    "衣服洗完不够香",
    "贴身衣物卫生困扰",
]
LAUNDRY_POD_STEPS = [
    "取1颗凝珠",
    "放入洗衣机内筒",
    "放入衣物后启动洗涤",
]


@dataclass
class ProductInput:
    product_name: str
    brand_name: str
    category: str
    usage_scene: str
    target_user: str
    pain_points: list[str]
    selling_points: list[str]
    safe_claims: list[str]
    scent_or_experience: str
    usage_method: str
    package_visible_info: str
    forbidden_words: list[str]
    reference_style: str


@dataclass
class GeneratedPackage:
    created_at: str
    uploaded_images: list[str]
    normalized_input: ProductInput
    markdown_package: str
    article_copy: str
    image_copies: dict[str, str]


def split_lines(value: str) -> list[str]:
    parts = re.split(r"[\n\r；;]+", value or "")
    return [part.strip(" \t-•、") for part in parts if part.strip(" \t-•、")]


def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def is_laundry_pod(category: str, product_name: str = "") -> bool:
    text = f"{category} {product_name}"
    return any(keyword in text for keyword in ["洗衣凝珠", "凝珠", "洗衣珠"])


def remove_forbidden_words(text: str, forbidden_words: list[str]) -> str:
    cleaned = text or ""
    for word in forbidden_words:
        word = word.strip()
        if word:
            cleaned = cleaned.replace(word, "")
    return re.sub(r"\s+", " ", cleaned).strip()


def sanitize_items(items: Iterable[str], forbidden_words: list[str]) -> list[str]:
    return unique_keep_order(remove_forbidden_words(item, forbidden_words) for item in items)


def normalize_product_input(raw: ProductInput) -> tuple[ProductInput, list[str]]:
    notes: list[str] = []
    forbidden_words = unique_keep_order([*DEFAULT_FORBIDDEN_WORDS, *raw.forbidden_words])

    pain_points: list[str] = []
    selling_points = list(raw.selling_points)

    for item in raw.pain_points:
        if any(keyword in item for keyword in MISPLACED_SELLING_POINT_KEYWORDS):
            selling_points.append(item)
            notes.append(f"已将「{item}」从痛点调整到卖点。")
        else:
            pain_points.append(item)

    if is_laundry_pod(raw.category, raw.product_name):
        if not pain_points:
            pain_points = LAUNDRY_POD_PAINS.copy()
            notes.append("检测到洗衣凝珠类产品，已补充常见洗衣痛点。")
        raw_usage_method = "\n".join(LAUNDRY_POD_STEPS)
        notes.append("检测到洗衣凝珠类产品，使用步骤已固定为凝珠正确使用方式。")
    else:
        raw_usage_method = raw.usage_method

    normalized = ProductInput(
        product_name=remove_forbidden_words(raw.product_name, forbidden_words),
        brand_name=remove_forbidden_words(raw.brand_name, forbidden_words),
        category=remove_forbidden_words(raw.category, forbidden_words),
        usage_scene=remove_forbidden_words(raw.usage_scene, forbidden_words),
        target_user=remove_forbidden_words(raw.target_user, forbidden_words),
        pain_points=sanitize_items(pain_points, forbidden_words),
        selling_points=sanitize_items(selling_points, forbidden_words),
        safe_claims=sanitize_items(raw.safe_claims, forbidden_words),
        scent_or_experience=remove_forbidden_words(raw.scent_or_experience, forbidden_words),
        usage_method=remove_forbidden_words(raw_usage_method, forbidden_words),
        package_visible_info=remove_forbidden_words(raw.package_visible_info, forbidden_words),
        forbidden_words=forbidden_words,
        reference_style=remove_forbidden_words(raw.reference_style, forbidden_words) or DEFAULT_REFERENCE_STYLE,
    )

    return normalized, unique_keep_order(notes)


def bullet_lines(items: list[str], fallback: str = "请根据用户输入和产品图片合理提炼，不要编造数据") -> str:
    clean = [item for item in items if item]
    if not clean:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in clean)


def numbered_lines(items: list[str]) -> str:
    clean = [item for item in items if item]
    return "\n".join(f"{index}. {item}" for index, item in enumerate(clean, start=1)) or "请按产品实际使用方式说明"


def pick_items(items: list[str], count: int, fallback: list[str]) -> list[str]:
    picked = [item for item in items if item][:count]
    for item in fallback:
        if len(picked) >= count:
            break
        if item not in picked:
            picked.append(item)
    return picked[:count]


def make_article_copy(data: ProductInput) -> str:
    return f"""# 文章单独复制版

请根据我上传的产品图片和以下资料，先输出一篇完整的小红书种草文章。

产品名称：{data.product_name}
品牌：{data.brand_name}
品类：{data.category}
使用场景：{data.usage_scene}
目标人群：{data.target_user}

核心痛点：
{bullet_lines(data.pain_points)}

核心卖点：
{bullet_lines(data.selling_points)}

可使用功效数据：
{bullet_lines(data.safe_claims, "未提供可使用功效数据，请不要编造")}

香味/使用体验：{data.scent_or_experience}

使用方法：
{numbered_lines(split_lines(data.usage_method))}

包装可见信息：{data.package_visible_info}

禁用词：{"、".join(data.forbidden_words)}

文章要求：
1. 标题要有爆文感，可以用“不删”“终于找到”“宿舍党”“懒人”“宝妈”等表达。
2. 开头先讲真实痛点，不要直接介绍产品。
3. 中段自然引出产品。
4. 卖点用 ✅ 展开。
5. 使用方法要简单清楚。
6. 结尾强调省心、干净感、香味、常备。
7. 标签 8-12 个。
8. 口吻要像真人分享，不要像官方详情页。
9. 不要夸大功效，不要编造数据。
"""


def make_image_copies(data: ProductInput) -> dict[str, str]:
    selling_points = pick_items(data.selling_points, 4, ["一颗搞定", "省时省力", "香味好闻", "日常常备"])
    image_1_pains = pick_items(data.pain_points, 3, ["汗味残留", "洗衣麻烦", "不够留香"])

    return {
        "第1张图：封面强点击图": f"""## 第1张图：封面强点击图

只生成第1张图，不要生成其他图，不要拼图。

图片目的：
制造点击欲望，突出产品解决日常洗衣痛点。

画面构图：
竖版 3:4 或 4:5。
真实宿舍洗衣区/阳台洗衣区/家用洗衣机旁。
产品放在画面中下方，包装正面清晰。
顶部放大字标题。
底部放 3 个红叉痛点标签。

图中文字：
主标题：
终于找到好用的{data.category}了！！

底部红叉：
× {image_1_pains[0]}
× {image_1_pains[1]}
× {image_1_pains[2]}

图片生成提示词：
请生成一张独立的小红书封面图，不要拼图，不要合集。画面是{data.target_user}在{data.usage_scene}中会遇到的真实洗衣场景，背景有洗衣机、脏衣篮、叠好的衣服或宿舍洗衣区。请使用我上传的产品图片作为真实产品主体参考，保持产品包装、LOGO、瓶型/桶型、标签、颜色、规格、可见文字一致，不要重新设计包装，不要改写品牌和包装信息。产品放在画面中下方，包装正面清晰。顶部大字写“终于找到好用的{data.category}了！！”，底部红叉标签写“{image_1_pains[0]}、{image_1_pains[1]}、{image_1_pains[2]}”。整体风格参考小红书家清爆文，真实手机实拍，大字报标题，黑色粗描边，红叉痛点贴纸，强种草感。

负面提示词：
不要生成拼图，不要生成合集，不要九宫格，不要长图，不要小红书水印，不要账号ID，不要二维码，不要改包装，不要改LOGO，不要改标签，不要虚假功效，不要过度商业棚拍。
""",
        "第2张图：卖点总览图": f"""## 第2张图：卖点总览图

只生成第2张图，不要生成其他图，不要拼图。

图片目的：
让用户一眼看懂产品为什么好用。

画面构图：
竖版 3:4 或 4:5。
手持产品，或者产品放在洗衣机/衣物/宿舍桌面旁。
左侧放蓝点卖点卡片。
底部放一句体验感文案。

图中文字：
标题：
{data.brand_name}{data.scent_or_experience or selling_points[0]}{data.category}

蓝点卖点：
● {selling_points[0]}
● {selling_points[1]}
● {selling_points[2]}
● {selling_points[3]}

底部文案：
洗完衣服香香的，真的省心很多

图片生成提示词：
请生成一张独立的小红书卖点总览图，不要拼图，不要合集。画面是产品在真实洗衣场景中，手持或摆放在洗衣机、衣物、宿舍洗衣区旁边。请使用我上传的产品图片作为真实产品主体参考，保持产品包装、LOGO、瓶型/桶型、标签、颜色、规格、可见文字一致，不要重新设计包装，不要改写品牌和包装信息。左侧设计蓝色圆点卖点卡片，分别写：{selling_points[0]}、{selling_points[1]}、{selling_points[2]}、{selling_points[3]}。底部写“洗完衣服香香的，真的省心很多”。整体真实、明亮、生活化，有小红书强种草感。

负面提示词：
不要生成拼图，不要生成合集，不要九宫格，不要长图，不要小红书水印，不要账号ID，不要二维码，不要改包装，不要改LOGO，不要改标签，不要虚假功效。
""",
        "第3张图：Before / After 对比图": """## 第3张图：Before / After 对比图

只生成第3张图，不要生成其他图，不要拼图。

图片目的：
强化清洁前后对比，但不要夸大效果。

画面构图：
竖版 3:4 或 4:5。
上下分屏。
上半部分 Before：衣服有汗味、闷味、轻微发黄或脏感。
下半部分 After：衣服更干净、更清爽。
产品放在画面右下角或中间作为解决方案。

图中文字：
Before
汗味残留 / 衣服闷味 / 洗完不清爽

After
干净感上来了 / 香香软软 / 清爽很多

底部小字：
效果图为视觉示意，实际效果以使用情况为准

图片生成提示词：
请生成一张独立的小红书 Before / After 对比图，不要拼图，不要合集，不要把5张图合成在一起。画面上下分屏，上方是 Before：宿舍或日常洗衣场景中的衣物，有汗味、闷味、轻微发黄或不清爽的视觉提示，但不要夸张。下方是 After：衣物更白净、更清爽、更柔软。请使用我上传的产品图片作为真实产品主体参考，保持产品包装、LOGO、瓶型/桶型、标签、颜色、规格、可见文字一致，不要重新设计包装。产品放在右下角或分屏中间。添加文字 Before、After，以及“效果图为视觉示意，实际效果以使用情况为准”。整体像真实小红书测评图。

负面提示词：
不要生成拼图，不要合集，不要九宫格，不要夸张污渍，不要虚假效果，不要医疗化表达，不要小红书水印，不要账号ID，不要二维码，不要改包装。
""",
        "第4张图：使用步骤图": """## 第4张图：使用步骤图

只生成第4张图，不要生成其他图，不要拼图。

图片目的：
让用户一眼知道怎么用。

画面构图：
竖版 3:4 或 4:5。
三步骤流程图。
可以用三段式排版，但必须是一张独立的步骤图，不要和其他主题混在一起。

图中文字：
标题：
懒人洗衣真的很方便

步骤1：
取1颗凝珠

步骤2：
放入洗衣机内筒

步骤3：
放入衣物后启动洗涤

小提示：
请将凝珠放入洗衣机内筒，再放衣物哦

图片生成提示词：
请生成一张独立的小红书使用步骤图，不要拼图，不要合集，不要九宫格。画面是洗衣凝珠的真实使用步骤，整体为三步骤排版。第1步：手从桶里取1颗凝珠；第2步：把凝珠放入洗衣机内筒；第3步：放入衣物后启动洗涤。请使用我上传的产品图片作为真实产品主体参考，保持产品包装、LOGO、瓶型/桶型、标签、颜色、规格、可见文字一致，不要重新设计包装。顶部大字写“懒人洗衣真的很方便”。步骤文字分别是“1 取1颗凝珠”“2 放入洗衣机内筒”“3 放入衣物后启动洗涤”。整体风格真实、干净、清楚，小红书家居洗护教程感。

负面提示词：
不要生成拼图合集，不要把5张图合成一张，不要写喷、涂、擦、冲水，不要写剪开凝珠，不要直接手洗，不要小红书水印，不要账号ID，不要二维码，不要改包装。
""",
        "第5张图：懒人种草收尾图": """## 第5张图：懒人种草收尾图

只生成第5张图，不要生成其他图，不要拼图。

图片目的：
形成收藏和下单记忆点。

画面构图：
竖版 3:4 或 4:5。
产品放在宿舍洗衣区、阳台洗衣区、洗衣机上或干净衣物旁。
画面温暖、干净、有生活感。
顶部大字，底部卖点勾选。

图中文字：
顶部：
无需费力，轻松搞定日常洗衣

中间大字：
懒人洗衣之光

底部勾选：
✓ 一颗搞定
✓ 省时省力
✓ 香味好闻
✓ 日常常备

图片生成提示词：
请生成一张独立的小红书懒人种草收尾图，不要拼图，不要合集。画面是产品摆在真实宿舍洗衣区、阳台洗衣区、洗衣机上或干净衣物旁，氛围温暖、明亮、整洁，有真实生活感。请使用我上传的产品图片作为真实产品主体参考，保持产品包装、LOGO、瓶型/桶型、标签、颜色、规格、可见文字一致，不要重新设计包装，不要改写品牌和包装信息。顶部写“无需费力，轻松搞定日常洗衣”，中间大字写“懒人洗衣之光”，底部勾选“一颗搞定、省时省力、香味好闻、日常常备”。整体像小红书家清爆文收尾图，强收藏感，强种草感。

负面提示词：
不要生成拼图，不要合集，不要九宫格，不要长图，不要小红书水印，不要账号ID，不要二维码，不要改包装，不要改LOGO，不要虚假功效。
""",
    }


def make_markdown_package(data: ProductInput, image_copies: dict[str, str]) -> str:
    images_text = "\n\n---\n\n".join(image_copies.values())
    return f"""【复制给 ChatGPT 的执行包开始】

请根据我上传的产品图片和下面的产品资料，直接完成两个任务：

任务一：
先输出一篇完整的小红书种草文章。

任务二：
再生成 5 张独立的小红书风格图片。

非常重要：
1. 请生成 5 张独立图片，不要生成一张合集图。
2. 不要生成拼图、九宫格、长图、信息合集海报。
3. 每张图都是单独完整的一张小红书图片。
4. 每张图都要竖版 3:4 或 4:5。
5. 每张图都要参考我上传的真实产品图片。
6. 产品包装、LOGO、标签、瓶型/桶型、颜色、规格、可见文字必须尽量保持一致。
7. 不要重新设计包装。
8. 不要改写品牌名和包装信息。
9. 可以生成新的生活场景、背景、贴纸、标题和排版。
10. 不要生成小红书水印、账号ID、二维码、平台水印。

# 一、产品资料

产品名称：
{data.product_name}

品牌：
{data.brand_name}

品类：
{data.category}

使用场景：
{data.usage_scene}

目标人群：
{data.target_user}

核心痛点：
{bullet_lines(data.pain_points)}

核心卖点：
{bullet_lines(data.selling_points)}

可使用功效数据：
{bullet_lines(data.safe_claims, "未提供可使用功效数据，请不要编造")}

香味/使用体验：
{data.scent_or_experience}

使用方法：
{numbered_lines(split_lines(data.usage_method))}

包装可见信息：
{data.package_visible_info}

禁用词：
{"、".join(data.forbidden_words)}

参考风格：
{data.reference_style}

# 二、请先输出小红书文章

文章要求：
1. 标题要有爆文感，可以用“不删”“终于找到”“宿舍党”“懒人”“宝妈”等表达。
2. 开头先讲真实痛点，不要直接介绍产品。
3. 中段自然引出产品。
4. 卖点用 ✅ 展开。
5. 使用方法要简单清楚。
6. 结尾强调省心、干净感、香味、常备。
7. 标签 8-12 个。
8. 口吻要像真人分享，不要像官方详情页。
9. 不要夸大功效，不要编造数据。

# 三、再生成 5 张独立图片

请严格按照下面 5 张图片分别生成。
注意：每一张都是独立图片，不是合集。

---

{images_text}

【复制给 ChatGPT 的执行包结束】
"""


def save_uploaded_files(uploaded_files) -> list[str]:
    saved_paths: list[str] = []
    for uploaded_file in uploaded_files:
        content = uploaded_file.getvalue()
        digest = hashlib.sha256(content).hexdigest()[:12]
        suffix = Path(uploaded_file.name).suffix.lower() or ".png"
        safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(uploaded_file.name).stem).strip("_") or "product"
        target = UPLOAD_DIR / f"{safe_stem}_{digest}{suffix}"
        target.write_bytes(content)
        saved_paths.append(str(target.relative_to(BASE_DIR)))
    return saved_paths


def persist_outputs(package: GeneratedPackage) -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = OUTPUT_DIR / f"xhs_chatgpt_package_{timestamp}.md"
    json_path = OUTPUT_DIR / f"xhs_chatgpt_package_{timestamp}.json"
    md_path.write_text(package.markdown_package, encoding="utf-8")
    json_path.write_text(json.dumps(asdict(package), ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path


def build_package(raw_input: ProductInput, uploaded_image_paths: list[str]) -> tuple[GeneratedPackage, list[str]]:
    normalized, notes = normalize_product_input(raw_input)
    image_copies = make_image_copies(normalized)
    markdown_package = make_markdown_package(normalized, image_copies)
    article_copy = make_article_copy(normalized)
    package = GeneratedPackage(
        created_at=datetime.now().isoformat(timespec="seconds"),
        uploaded_images=uploaded_image_paths,
        normalized_input=normalized,
        markdown_package=markdown_package,
        article_copy=article_copy,
        image_copies=image_copies,
    )
    return package, notes


def page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container { max-width: 1180px; padding-top: 2rem; }
        .stTextInput input, .stTextArea textarea { border-radius: 8px; }
        .hint-box {
            border: 1px solid #e6e8ef;
            background: #f8fafc;
            border-radius: 8px;
            padding: 14px 16px;
            color: #334155;
            font-size: 14px;
            line-height: 1.65;
        }
        .result-box {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
            background: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="小红书爆文图文执行包生成器", page_icon="📝", layout="wide")
    page_style()

    st.title("小红书爆文图文执行包生成器")
    st.caption("本工具只生成可复制给 ChatGPT 的文本执行包；不生成图片，不调用 OpenAI API，不接入 IMAGE_API_ENDPOINT。")

    st.markdown(
        """
        <div class="hint-box">
        上传的产品图只用于本地预览。生成执行包后，请把执行包和原产品图片一起发送给 ChatGPT。
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("产品图")
        uploaded_files = st.file_uploader(
            "上传产品图",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help="支持多张 jpg/png/webp。图片只用于本地预览和保存，不会被发送到任何接口。",
        )
        if uploaded_files:
            st.caption(f"已选择 {len(uploaded_files)} 张图片")
            for uploaded_file in uploaded_files:
                try:
                    image = Image.open(uploaded_file)
                    st.image(image, caption=uploaded_file.name, use_container_width=True)
                except Exception:
                    st.warning(f"{uploaded_file.name} 无法预览，请确认文件格式。")
        else:
            st.info("请先上传产品图。后续复制执行包给 ChatGPT 时，也要把这些图片一起上传。")

    with st.form("product_form"):
        col1, col2 = st.columns(2)
        with col1:
            product_name = st.text_input("产品名称 product_name", placeholder="例：XX 香氛洗衣凝珠")
            brand_name = st.text_input("品牌 brand_name", placeholder="例：XX")
            category = st.text_input("产品品类 category", placeholder="例：洗衣凝珠")
            usage_scene = st.text_input("使用场景 usage_scene", placeholder="例：宿舍洗衣、家庭日常洗衣")
            target_user = st.text_input("目标人群 target_user", placeholder="例：宿舍党、宝妈、懒人洗衣人群")
            scent_or_experience = st.text_input("香味/使用体验 scent_or_experience", placeholder="例：清新花香，洗完衣服柔软好闻")
        with col2:
            package_visible_info = st.text_area("包装可见信息 package_visible_info", height=112, placeholder="例：包装上可见 118颗、大桶装、除菌除螨检测信息等")
            safe_claims = st.text_area("可使用功效数据 safe_claims", height=112, placeholder="每行一条。只填写你能从包装或资料确认的数据，例如：有检测报告的99.9%除菌除螨")
            forbidden_words = st.text_area(
                "禁用词 forbidden_words",
                height=92,
                value="\n".join(DEFAULT_FORBIDDEN_WORDS),
                help="默认包含常见违规词，可继续补充。",
            )

        pain_points = st.text_area(
            "核心痛点 pain_points",
            height=132,
            placeholder="每行一条。例：汗味残留\n衣服闷味\n宿舍洗衣麻烦",
        )
        selling_points = st.text_area(
            "核心卖点 selling_points",
            height=132,
            placeholder="每行一条。例：一颗搞定\n118颗大桶装\n香味好闻",
        )
        usage_method = st.text_area(
            "使用方法 usage_method",
            height=92,
            placeholder="洗衣凝珠类产品会自动固定为：取1颗凝珠 / 放入洗衣机内筒 / 放入衣物后启动洗涤",
        )
        reference_style = st.text_area("参考风格 reference_style", height=82, value=DEFAULT_REFERENCE_STYLE)

        submitted = st.form_submit_button("生成 ChatGPT 执行包", use_container_width=True)

    if submitted:
        raw_input = ProductInput(
            product_name=product_name,
            brand_name=brand_name,
            category=category,
            usage_scene=usage_scene,
            target_user=target_user,
            pain_points=split_lines(pain_points),
            selling_points=split_lines(selling_points),
            safe_claims=split_lines(safe_claims),
            scent_or_experience=scent_or_experience,
            usage_method=usage_method,
            package_visible_info=package_visible_info,
            forbidden_words=split_lines(forbidden_words),
            reference_style=reference_style,
        )
        uploaded_image_paths = save_uploaded_files(uploaded_files or [])
        package, notes = build_package(raw_input, uploaded_image_paths)
        md_path, json_path = persist_outputs(package)
        st.session_state["package"] = package
        st.session_state["notes"] = notes
        st.session_state["md_path"] = md_path
        st.session_state["json_path"] = json_path

    package: GeneratedPackage | None = st.session_state.get("package")
    if package:
        st.divider()
        st.subheader("生成结果")

        notes = st.session_state.get("notes", [])
        if notes:
            with st.expander("自动纠错记录", expanded=True):
                for note in notes:
                    st.write(f"- {note}")

        md_path = st.session_state["md_path"]
        json_path = st.session_state["json_path"]
        json_text = json.dumps(asdict(package), ensure_ascii=False, indent=2)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "下载 Markdown 执行包",
                data=package.markdown_package.encode("utf-8"),
                file_name=md_path.name,
                mime="text/markdown",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "下载 JSON 备份",
                data=json_text.encode("utf-8"),
                file_name=json_path.name,
                mime="application/json",
                use_container_width=True,
            )

        tabs = st.tabs(["ChatGPT 执行包", "文章单独复制版", "5张图逐张复制版", "JSON备份版"])
        with tabs[0]:
            st.text_area("复制给 ChatGPT 的执行包", value=package.markdown_package, height=620)
        with tabs[1]:
            st.text_area("文章单独复制版", value=package.article_copy, height=460)
        with tabs[2]:
            for title, content in package.image_copies.items():
                with st.expander(title, expanded=title.startswith("第1张")):
                    st.text_area(title, value=content, height=420, key=f"copy_{title}")
        with tabs[3]:
            st.text_area("JSON备份版", value=json_text, height=520)

        st.caption(f"文件已保存：{md_path.relative_to(BASE_DIR)}，{json_path.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
