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
import streamlit.components.v1 as components
from PIL import Image, ImageOps

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_ENABLED = True
except Exception:
    HEIF_ENABLED = False


BASE_DIR = Path(os.environ.get("XHS_GENERATOR_DATA_DIR", Path(__file__).resolve().parent)).resolve()
UPLOAD_DIR = BASE_DIR / "uploads"
CONVERTED_DIR = UPLOAD_DIR / "converted"
OUTPUT_DIR = BASE_DIR / "output"
for folder in (UPLOAD_DIR, CONVERTED_DIR, OUTPUT_DIR):
    folder.mkdir(parents=True, exist_ok=True)


FORBIDDEN_WORDS = [
    "小红书",
    "小红书爆文",
    "小红书风格",
    "小红书水印",
    "小红书笔记",
    "小红书种草",
    "平台水印",
    "账号 ID",
    "账号ID",
    "二维码",
    "最强",
    "第一",
    "全网第一",
    "彻底根除",
    "永久",
    "100%",
    "神药",
    "治疗",
    "医用级",
    "无毒",
    "绝对安全",
    "孕妇婴儿随便用",
    "零风险",
    "完全无残留",
]

DISCLAIMER_WORDS = [
    "效果为视觉示意",
    "仅供参考",
    "实际效果因人而异",
    "实际效果以使用情况为准",
    "视觉示意",
    "图片仅供参考",
]

CAUTIOUS_WORDS = ["杀菌", "除菌", "抑菌", "除螨", "持久留香", "天然", "婴童可用", "敏感肌可用", "宠物友好"]

DEFAULT_NEGATIVE_PROMPT = (
    "不要改变产品包装，不要修改品牌LOGO，不要生成错误文字，不要生成虚假规格，"
    "不要生成平台标识，不要生成账号标识，不要生成扫码图形，不要让产品变形，"
    "不要让瓶身/袋身/盒身扭曲，不要生成夸张塑料感，不要生成过度广告海报感，"
    "不要生成脏乱低质画面，不要出现手指畸形，不要出现多余产品，不要出现不相关品牌，"
    "不要出现医学治疗暗示，不要出现绝对化功效表达。"
)


@dataclass
class UploadedImageInfo:
    original_name: str
    original_path: str
    preview_path: str
    converted_image_path: str
    status: str
    message: str


@dataclass
class ProductInfo:
    product_name: str
    brand_name: str
    category: str
    selling_points: list[str]
    target_user: str
    usage_scene: str
    proof_info: list[str]
    forbidden_words: list[str]
    visible_info: str


@dataclass
class StyleGroup:
    style_id: str
    style_name: str
    reason: str
    title: str
    article: str
    image_prompts: list[dict[str, str]]


@dataclass
class GeneratedResult:
    created_at: str
    uploaded_images: list[UploadedImageInfo]
    product_info: ProductInfo
    selected_styles: list[dict[str, str]]
    groups: list[StyleGroup]
    summary: str
    markdown_package: str


STYLE_LIBRARY: list[dict[str, object]] = [
    {
        "id": "G01",
        "name": "真人入镜实测证据风",
        "position": "用真人入镜和真实使用过程建立信任感，突出我真的用了，而且变化看得见。",
        "fit": ["洗衣凝珠", "去渍", "浴室清洁", "厨房清洁", "马桶清洁", "洗衣液"],
        "visual": "真人或手部入镜，真实家庭场景，产品和使用动作同框，局部对比、箭头、圈重点。",
        "article": "真实问题 → 原来处理很麻烦 → 试了这个产品 → 变化明显 → 补充卖点 → 真实种草收尾",
        "images": ["真人痛点封面图", "真实痛点场景图", "使用前后对比图", "使用步骤图", "卖点解释 + 种草收尾图"],
    },
    {
        "id": "G02",
        "name": "高信任妈妈囤货种草风",
        "position": "用家庭高频消耗、长期回购逻辑建立信任感。",
        "fit": ["洗衣液", "内衣洗衣液", "宝宝衣物清洁", "湿巾", "柔巾", "家庭清洁"],
        "visual": "真实家庭场景，宝宝衣物、洗衣区、收纳区、囤货柜同框。",
        "article": "家里消耗很快 → 囤货不能乱买 → 更看重安心和实用 → 长期用下来不错 → 适合哪些家庭",
        "images": ["囤货型封面图", "家庭真实消耗场景图", "卖点总览图", "安心/实用理由图", "家庭常备收尾图"],
    },
    {
        "id": "G03",
        "name": "多场景洗衣难题一瓶解决风",
        "position": "突出以前步骤很多，现在一个产品解决很多麻烦。",
        "fit": ["洗衣凝珠", "洗衣液", "浴室清洁", "厨房清洁", "家务减负"],
        "visual": "脏衣篮、宝宝衣、校服、洗衣机、阳台、旧方法对比。",
        "article": "以前家务太复杂 → 各种步骤折腾人 → 换了这个 → 一瓶多效省事 → 家里长期常备",
        "images": ["家务减负封面图", "多种难题场景图", "一瓶多效卖点图", "简单使用方式图", "省心收尾图"],
    },
    {
        "id": "G04",
        "name": "情绪香氛氛围感故事风",
        "position": "用生活状态和情绪故事带出产品，讲香味让生活更舒服。",
        "fit": ["香氛洗衣液", "洗衣凝珠", "留香珠", "香氛浴室清洁", "香氛家清"],
        "visual": "自然光、居家、阳台、衣柜、床品、沙发，柔和干净。",
        "article": "最近的生活状态 → 做家务小片段 → 产品自然出现 → 香味体验让我喜欢 → 功能点补充 → 情绪收尾",
        "images": ["氛围感封面图", "居家故事场景图", "香味体验图", "功能补充图", "治愈生活收尾图"],
    },
    {
        "id": "G05",
        "name": "敏感肌安心成分信任风",
        "position": "先讲敏感肌、宝宝、贴身衣物顾虑，再讲做功课后的选择。",
        "fit": ["温和洗衣液", "宝宝洗护", "贴身衣物清洁", "敏感肌", "温和家清"],
        "visual": "柔和、干净、安心，白色衣物、卧室或洗衣区。",
        "article": "敏感/贴身衣物顾虑 → 不敢乱选 → 做功课后选了它 → 温和点打动我 → 使用体验不错",
        "images": ["敏感肌痛点封面图", "为什么要认真选图", "安心卖点图", "温和洗护体验图", "敏肌/宝宝家庭收尾图"],
    },
    {
        "id": "G06",
        "name": "家庭安全顾虑解决方案风",
        "position": "围绕家里有宝宝/宠物/老人，能不能安心用展开。",
        "fit": ["驱蚊", "灭蚊", "母婴家清", "儿童友好", "家庭安全"],
        "visual": "儿童房、卧室、床边、宝宝用品、夜晚睡前场景。",
        "article": "家里有娃所以谨慎 → 传统方案让我担心 → 找到更安心方式 → 使用简单 → 家庭场景反馈",
        "images": ["家庭顾虑封面图", "真实痛点场景图", "安心解决方案图", "使用方式图", "家庭安全感收尾图"],
    },
    {
        "id": "G07",
        "name": "强对比去污说服风",
        "position": "用强烈前后变化完成快速种草，强调一试被说服。",
        "fit": ["洗衣去渍", "免搓粉", "浴室除垢", "厨房油污", "鞋子清洁"],
        "visual": "前后对比明显，污渍局部清楚，产品和污渍同框。",
        "article": "原来很费劲 → 一开始半信半疑 → 一试变化明显 → 解释省心点 → 不想回到老方法",
        "images": ["强痛点封面图", "脏污痛点图", "使用前后对比图", "卖点解释图", "省力种草收尾图"],
    },
    {
        "id": "G08",
        "name": "对比选购优势锚定风",
        "position": "通过旧方式和当前产品对比，帮助快速做购买判断。",
        "fit": ["洗衣机清洁", "浴室清洁", "厨房清洁", "洗衣凝珠", "多效清洁"],
        "visual": "对比框、勾叉、箭头、结论标签，一眼看懂为什么选它。",
        "article": "原来方法不省心 → 为什么需要换方案 → 这个产品更简单 → 优势对比 → 推荐结论",
        "images": ["问题封面图", "旧方式痛点图", "优势对比图", "卖点拆解图", "明确推荐收尾图"],
    },
    {
        "id": "G09",
        "name": "人设封面香氛指南风",
        "position": "用真人封面提升点击率，再用香型/场景/人群选择指南提高停留。",
        "fit": ["多香型洗衣液", "留香珠", "香氛洗护", "贴身衣物洗护", "香氛浴室清洁"],
        "visual": "真人入镜，产品和真人同框，香型卡片和选择指南卡片。",
        "article": "真人人设开场 → 生活场景痛点 → 关注香氛洗护 → 不同香型适合谁 → 卖点补充",
        "images": ["真人高点击封面图", "真实痛点场景图", "香型选择指南图", "核心功效背书图", "试香/囤货建议图"],
    },
    {
        "id": "G10",
        "name": "长期主义高利用率清单风",
        "position": "围绕不盲目囤货，只留高利用率好物展开。",
        "fit": ["母婴清洁", "湿巾", "柔巾", "宝宝洗护", "家庭消耗品", "长期常备"],
        "visual": "家庭生活感，清单式、推荐式排版，外出包、收纳区。",
        "article": "别盲目囤货 → 实际留下的高频使用品 → 为什么利用率高 → 适用场景 → 值得长期回购",
        "images": ["高利用率清单封面图", "使用场景总览图", "安心卖点图", "高利用率价值图", "长期主义收尾图"],
    },
    {
        "id": "G11",
        "name": "高能量女生松弛感生活方式风",
        "position": "围绕都市女生经营状态感，用通勤、穿搭、气味、衣物触感带出产品。",
        "fit": ["香氛洗衣液", "洗衣凝珠", "留香珠", "身体护理", "通勤日用品"],
        "visual": "真人入镜、plog感、通勤前、卧室、衣柜、阳台、镜前。",
        "article": "生活/通勤状态 → 在意衣服味道和触感 → 产品自然出现 → 香味与衣物状态 → 松弛感来自细节",
        "images": ["人设观点封面图", "状态场景图", "香味与质感图", "功能支撑图", "松弛感收尾图"],
    },
    {
        "id": "G12",
        "name": "随身救场即时清洁风",
        "position": "围绕外出即时补救，突出便携、随手用、维持精致感。",
        "fit": ["擦鞋湿巾", "去污湿巾", "应急清洁", "旅行清洁", "通勤清洁"],
        "visual": "强前后对比，产品和脏污物品同框，外出、通勤、旅行。",
        "article": "外出遇到尴尬 → 普通方法不好用 → 产品快速救场 → 便携细节 → 精致感回来",
        "images": ["强对比封面图", "外出尴尬场景图", "即时救场卖点图", "便携与细节图", "精致感收尾图"],
    },
    {
        "id": "G13",
        "name": "极简高级体香氛围风",
        "position": "用真人氛围感、极简画面、高级香味想象种草。",
        "fit": ["香氛洗衣液", "洗衣凝珠", "留香珠", "衣物香氛喷雾", "身体护理香氛"],
        "visual": "半身入镜，白色、米色、浅灰、低饱和色调，字少但钩子强。",
        "article": "气味掉分场景 → 喜欢干净体香 → 产品出现 → 香味画面感 → 高级感收尾",
        "images": ["高级体香封面图", "尴尬气味痛点图", "香味氛围图", "香味卖点图", "高级感收尾图"],
    },
    {
        "id": "G14",
        "name": "香软衣物真实体验种草风",
        "position": "用真实生活场景和穿着体验完成种草，突出香香软软、贴身舒服。",
        "fit": ["洗衣液", "洗衣凝珠", "留香珠", "贴身衣物洗护", "柔顺洗护", "温和洗护"],
        "visual": "真实居家、阳台、洗衣区、卧室，闻衣服、摸衣服、叠衣服。",
        "article": "贴身衣物更在意洗护 → 做功课后选它 → 洗完香软感喜欢 → 温和/养护理由 → 穿着舒服",
        "images": ["真实体验封面图", "贴身衣物顾虑图", "香软体验图", "衣物养护卖点图", "真实种草收尾图"],
    },
]


def split_lines(value: str) -> list[str]:
    parts = re.split(r"[\n\r；;]+", value or "")
    return [part.strip(" \t-•、") for part in parts if part.strip(" \t-•、")]


def safe_filename(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", stem).strip("._-") or "product"
    return f"{cleaned}{suffix}"


def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = item.strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def contains_any(text: str, words: Iterable[str]) -> bool:
    return any(word and word in text for word in words)


def sanitize_text(text: str, extra_forbidden: Iterable[str] = ()) -> str:
    value = text or ""
    for word in [*FORBIDDEN_WORDS, *DISCLAIMER_WORDS, *extra_forbidden]:
        if word:
            value = value.replace(word, "")
    value = value.replace("水印", "标识").replace("平台账号", "内容账号")
    return re.sub(r"\s+", " ", value).strip()


def sanitize_items(items: Iterable[str], extra_forbidden: Iterable[str] = ()) -> list[str]:
    return unique_keep_order(sanitize_text(item, extra_forbidden) for item in items)


def first_or_unknown(value: str) -> str:
    value = sanitize_text(value)
    return value if value else "图片不可确认"


def bullet(items: list[str], fallback: str = "图片不可确认") -> str:
    clean = [item for item in items if item]
    if not clean:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in clean)


def detect_category_keywords(category: str, selling_points: list[str], visible_info: str) -> str:
    text = f"{category} {' '.join(selling_points)} {visible_info}"
    if contains_any(text, ["洗衣凝珠", "洗衣液", "留香珠", "香氛洗护", "衣物"]):
        return "laundry"
    if contains_any(text, ["浴室", "除垢", "马桶", "厨房", "油污", "清洁剂"]):
        return "cleaning"
    if contains_any(text, ["母婴", "宝宝", "婴儿", "儿童", "湿巾", "柔巾"]):
        return "family"
    if contains_any(text, ["擦鞋", "随身", "便携", "旅行", "应急", "湿巾"]):
        return "portable"
    return "general"


def select_styles(product: ProductInfo, count: int, manual_ids: list[str]) -> list[dict[str, object]]:
    if manual_ids:
        chosen = [style for style in STYLE_LIBRARY if style["id"] in manual_ids]
    else:
        category_type = detect_category_keywords(product.category, product.selling_points, product.visible_info)
        priority_map = {
            "laundry": ["G01", "G03", "G04", "G05", "G07", "G09", "G11", "G13", "G14", "G02", "G08", "G10"],
            "cleaning": ["G01", "G03", "G04", "G07", "G08", "G12", "G02", "G06", "G10", "G14"],
            "family": ["G02", "G05", "G06", "G10", "G14", "G01", "G03", "G08", "G04", "G07"],
            "portable": ["G12", "G07", "G08", "G11", "G13", "G01", "G10", "G03", "G04", "G14"],
            "general": ["G01", "G03", "G08", "G10", "G02", "G04", "G07", "G11", "G13", "G14"],
        }
        ids = priority_map[category_type]
        chosen = [style for style_id in ids for style in STYLE_LIBRARY if style["id"] == style_id]
        for style in STYLE_LIBRARY:
            if style not in chosen:
                chosen.append(style)

    return chosen[: max(1, min(count, 14))]


def style_reason(style: dict[str, object], product: ProductInfo) -> str:
    fit_words = "、".join(style["fit"])  # type: ignore[index]
    if product.category != "图片不可确认":
        return f"该风格适合「{product.category}」这类产品，可从{style['position']}切入。匹配关键词：{fit_words}。"
    return f"产品品类未完全确认，选择该风格用于覆盖真实使用、对比、场景和种草转化角度。匹配关键词：{fit_words}。"


def overlay_text_for(style: dict[str, object], image_title: str, product: ProductInfo, index: int) -> str:
    category = product.category if product.category != "图片不可确认" else "这件好物"
    selling = product.selling_points[0] if product.selling_points else "日常更省心"
    templates = [
        f"{category}真的省心",
        "日常清洁感在线",
        selling[:18],
        "用起来更顺手",
        "家里常备很方便",
    ]
    if "香" in style["name"] or contains_any(" ".join(product.selling_points), ["香", "留香", "气味"]):
        templates = ["干净香气刚刚好", "衣服状态更舒服", selling[:18], "靠近也好闻", "细节感拉满"]
    if "对比" in style["name"] or "去污" in style["name"]:
        templates = ["清洁感上来了", "脏感少了很多", selling[:18], "省力很多", "看得见的变化"]
    if "妈妈" in style["name"] or "家庭" in style["name"]:
        templates = ["家里常备更安心", "高频使用很方便", selling[:18], "日常用得上", "囤货不踩雷"]
    if "随身" in style["name"]:
        templates = ["外出救场很方便", "尴尬瞬间稳住", selling[:18], "小包也放得下", "精致感回来了"]
    return sanitize_text(templates[(index - 1) % len(templates)])


def build_article(style: dict[str, object], product: ProductInfo, index: int) -> tuple[str, str]:
    name = product.product_name if product.product_name != "图片不可确认" else "这款产品"
    brand = "" if product.brand_name == "图片不可确认" else product.brand_name
    category = product.category if product.category != "图片不可确认" else "日用好物"
    user = product.target_user if product.target_user != "图片不可确认" else "有同类需求的人"
    scene = product.usage_scene if product.usage_scene != "图片不可确认" else "日常生活场景"
    selling = product.selling_points or ["日常使用更省心", "清洁感更明显", "适合常备"]
    proof = product.proof_info or []

    titles = [
        f"{category}别乱选，我更看重真实使用感",
        f"{scene}里用得上的省心好物",
        f"{user}可以看看这款{category}",
        f"日常清洁想省事，真的可以换个思路",
        f"不是硬夸，{name}的使用感挺稳",
    ]
    title = sanitize_text(titles[(index - 1) % len(titles)])
    proof_sentence = ""
    if proof:
        proof_sentence = f" 另外，能确认的信息里有「{proof[0]}」，这类内容我会更愿意当作辅助判断，而不是只看包装话术。"
    body = (
        f"以前我选{category}时，最怕看起来很厉害，真正放到{scene}里却不好用。"
        f"这次关注到{brand + ' ' if brand else ''}{name}，主要是因为它的卖点更贴近日常："
        f"{'、'.join(selling[:3])}。"
        f"它适合{user}，尤其是想把步骤变简单、又不想把家务做得太复杂的人。"
        f"我更喜欢它的点不是夸张效果，而是用起来更顺手，清洁感、气味和收纳常备这些细节都比较容易被感知。"
        f"{proof_sentence}"
        f"如果你也经常在{scene}里遇到类似麻烦，可以把它放进备选清单。整体是偏真实、实用、适合长期用的种草方向，不走夸张硬广路线。"
    )
    return title, sanitize_text(body)


def build_image_prompt(style: dict[str, object], image_title: str, product: ProductInfo, image_no: int) -> dict[str, str]:
    scene = product.usage_scene if product.usage_scene != "图片不可确认" else "真实居家或日常生活场景"
    user = product.target_user if product.target_user != "图片不可确认" else "目标用户"
    category = product.category if product.category != "图片不可确认" else "产品"
    selling = "、".join(product.selling_points[:3]) if product.selling_points else "日常清洁更省心、用起来更方便"
    overlay = overlay_text_for(style, image_title, product, image_no)
    prompt = (
        f"请生成第{image_no}张独立得物图文图片，主题为「{image_title}」。"
        f"画面在{scene}中展开，面向{user}，整体真实自然，有内容种草风格。"
        f"产品必须使用用户上传的产品图作为唯一真实主体参考，保持包装、LOGO、颜色、瓶型/桶型/袋型/盒型、可见文字和规格一致，"
        f"不要重新设计包装，不要把产品画成另一个品牌。"
        f"画面重点围绕{category}的使用场景和「{selling}」展开，可以加入手部、生活道具、前后对比、短文字贴纸。"
        f"构图为竖版 3:4 或 4:5，产品清晰可见，图上文字写「{overlay}」，文字不超过三组，清晰但不要堆太多信息。"
        f"风格关键词：{style['visual']}，真实生活感，清爽、可信、不过度广告化。"
    )
    return {
        "image_no": str(image_no),
        "purpose": sanitize_text(image_title),
        "scene": sanitize_text(f"{scene}，{style['visual']}"),
        "product_requirement": "产品使用上传图作为唯一包装参考，包装、LOGO、颜色、形状、文字、规格尽量一致，产品清晰不变形。",
        "overlay_text": overlay,
        "composition": "竖版 3:4 或 4:5，单张独立图片，不要合集、九宫格、长图。",
        "prompt": sanitize_text(prompt),
        "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
    }


def build_groups(product: ProductInfo, styles: list[dict[str, object]]) -> list[StyleGroup]:
    groups: list[StyleGroup] = []
    for index, style in enumerate(styles, start=1):
        title, article = build_article(style, product, index)
        image_prompts = [
            build_image_prompt(style, image_title, product, image_no)
            for image_no, image_title in enumerate(style["images"], start=1)  # type: ignore[index]
        ]
        groups.append(
            StyleGroup(
                style_id=str(style["id"]),
                style_name=str(style["name"]),
                reason=style_reason(style, product),
                title=title,
                article=article,
                image_prompts=image_prompts,
            )
        )
    return groups


def build_summary(product: ProductInfo, groups: list[StyleGroup]) -> str:
    style_lines = "\n".join(f"- {group.style_id} {group.style_name}：{group.reason}" for group in groups)
    notes = [
        "产品图需要和执行包一起发给 ChatGPT。",
        "产品包装、LOGO、颜色、形状和可见文字以用户上传图为准。",
        "图片不可确认的信息不会写成确定事实。",
        "检测、专利、认证类表达只使用用户补充或包装可见信息。",
        "输出内容已规避平台敏感字、绝对化功效表达和免责声明。",
    ]
    return f"""# 给用户看的摘要

## 产品识别结果
- 产品名称：{product.product_name}
- 品牌：{product.brand_name}
- 品类：{product.category}
- 可见卖点：{ "、".join(product.selling_points) if product.selling_points else "图片不可确认" }
- 目标人群：{product.target_user}
- 使用场景：{product.usage_scene}
- 检测/专利/认证信息：{ "、".join(product.proof_info) if product.proof_info else "图片不可确认" }

## 已选择的 {len(groups)} 组风格
{style_lines}

## 注意事项
{bullet(notes)}
"""


def build_markdown_package(product: ProductInfo, groups: list[StyleGroup]) -> str:
    group_blocks: list[str] = []
    for idx, group in enumerate(groups, start=1):
        image_blocks: list[str] = []
        for image in group.image_prompts:
            image_blocks.append(
                f"""#### 图{image['image_no']}：{image['purpose']}
- 画面描述：{image['scene']}
- 图上文字：{image['overlay_text']}
- 产品呈现：{image['product_requirement']}
- 构图要求：{image['composition']}
- 图片提示词：{image['prompt']}
- 负面提示词：{image['negative_prompt']}"""
            )
        group_blocks.append(
            f"""## 第{idx}组：{group.style_id} {group.style_name}
### 风格目标
{group.reason}

### 文章标题
{group.title}

### 文章正文
{group.article}

### 5张图生成指令
{chr(10).join(image_blocks)}
"""
        )

    markdown = f"""【请严格按以下要求执行】

我会同时上传一张产品图。请你以这张产品图作为唯一产品包装参考，生成 {len(groups)} 组不同风格的得物图文内容。每组包含：
1 篇种草文章 + 5 张独立图片。

重要要求：
1. 每张图必须是独立图片，不要合集图，不要九宫格，不要长图。
2. 产品包装、LOGO、颜色、瓶型、桶型、袋型、文字、规格尽量保持和我上传的产品图一致。
3. 不要重新设计产品包装。
4. 不要生成平台标识、账号标识、扫码图形。
5. 不要出现平台敏感字眼。
6. 不要出现免责声明式表达。
7. 如产品图中看不清的卖点，不要编造。
8. 可以根据产品品类合理推导真实使用场景。
9. 先输出第 1 组文章，再生成第 1 组 5 张图；再继续第 2 组，以此类推。
10. 每组风格必须明显不同，不要只是换标题。

# ChatGPT执行包：{len(groups)}组得物图文内容

## 使用说明
请用户把本执行包和产品图一起发送给 ChatGPT。若上传图中有转换后的 JPG，请优先上传转换后的 JPG 产品图。

## 产品信息
- 产品名称：{product.product_name}
- 品牌：{product.brand_name}
- 品类：{product.category}
- 可见卖点：{ "、".join(product.selling_points) if product.selling_points else "图片不可确认" }
- 用户补充卖点：{ "、".join(product.selling_points) if product.selling_points else "图片不可确认" }
- 目标人群：{product.target_user}
- 使用场景：{product.usage_scene}
- 检测/专利/认证信息：{ "、".join(product.proof_info) if product.proof_info else "图片不可确认" }
- 风险提醒：图片中看不清的品牌、规格、功效数据不要编造；谨慎词只有在包装可见或用户明确补充时使用。

## 禁止事项
- 禁止绝对化表达：{ "、".join(FORBIDDEN_WORDS[-12:]) }
- 谨慎使用：{ "、".join(CAUTIOUS_WORDS) }
- 禁止生成平台标识、账号标识、扫码图形
- 禁止改变产品包装、LOGO、颜色、形状、可见文字和规格
- 禁止输出免责声明式表达

## 全局图片规则
- 使用上传产品图作为唯一包装参考
- 产品包装不重新设计
- 不修改 LOGO
- 不修改产品颜色
- 不修改瓶型/桶型/袋型
- 不生成平台标识、扫码图形、账号标识
- 每张图独立生成
- 不要合集图、九宫格、长图
- 图上文字简洁清晰
- 场景真实自然

{chr(10).join(group_blocks)}
"""
    return sanitize_text(markdown)


def build_result(product: ProductInfo, image_infos: list[UploadedImageInfo], styles: list[dict[str, object]]) -> GeneratedResult:
    groups = build_groups(product, styles)
    summary = build_summary(product, groups)
    markdown_package = build_markdown_package(product, groups)
    return GeneratedResult(
        created_at=datetime.now().isoformat(timespec="seconds"),
        uploaded_images=image_infos,
        product_info=product,
        selected_styles=[{"style_id": g.style_id, "style_name": g.style_name, "reason": g.reason} for g in groups],
        groups=groups,
        summary=summary,
        markdown_package=markdown_package,
    )


def save_uploaded_file(uploaded_file) -> UploadedImageInfo:
    data = uploaded_file.getvalue()
    digest = hashlib.sha256(data).hexdigest()[:10]
    safe_name = safe_filename(uploaded_file.name)
    suffix = Path(safe_name).suffix.lower()
    target = UPLOAD_DIR / f"{Path(safe_name).stem}_{digest}{suffix}"
    target.write_bytes(data)

    if suffix in [".heic", ".heif"]:
        converted = CONVERTED_DIR / f"{Path(safe_name).stem}_{digest}.jpg"
        if not HEIF_ENABLED:
            return UploadedImageInfo(
                original_name=uploaded_file.name,
                original_path=str(target.relative_to(BASE_DIR)),
                preview_path="",
                converted_image_path="",
                status="convert_failed",
                message="已识别 HEIC/HEIF 文件，但当前环境缺少转换能力。请手动转 JPG 后上传，或安装 pillow-heif。",
            )
        try:
            image = Image.open(target)
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.save(converted, "JPEG", quality=92)
            return UploadedImageInfo(
                original_name=uploaded_file.name,
                original_path=str(target.relative_to(BASE_DIR)),
                preview_path=str(converted.relative_to(BASE_DIR)),
                converted_image_path=str(converted.relative_to(BASE_DIR)),
                status="converted",
                message="HEIC/HEIF 已转换为 JPG，发给 ChatGPT 时优先使用转换后的 JPG。",
            )
        except Exception as exc:
            return UploadedImageInfo(
                original_name=uploaded_file.name,
                original_path=str(target.relative_to(BASE_DIR)),
                preview_path="",
                converted_image_path="",
                status="convert_failed",
                message=f"HEIC/HEIF 转换失败：{exc}。请手动转 JPG 后上传。",
            )

    try:
        image = Image.open(target)
        image = ImageOps.exif_transpose(image)
        preview = CONVERTED_DIR / f"{Path(safe_name).stem}_{digest}.jpg"
        if image.mode in ("RGBA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
            image = background
        else:
            image = image.convert("RGB")
        image.save(preview, "JPEG", quality=92)
        return UploadedImageInfo(
            original_name=uploaded_file.name,
            original_path=str(target.relative_to(BASE_DIR)),
            preview_path=str(preview.relative_to(BASE_DIR)),
            converted_image_path=str(preview.relative_to(BASE_DIR)),
            status="uploaded",
            message="上传成功，已校正方向并生成 JPG 预览。",
        )
    except Exception as exc:
        return UploadedImageInfo(
            original_name=uploaded_file.name,
            original_path=str(target.relative_to(BASE_DIR)),
            preview_path="",
            converted_image_path="",
            status="preview_failed",
            message=f"上传成功，但预览生成失败：{exc}",
        )


def persist_result(result: GeneratedResult) -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = OUTPUT_DIR / f"dewu_package_{timestamp}.md"
    json_path = OUTPUT_DIR / f"dewu_package_{timestamp}.json"
    latest_path = OUTPUT_DIR / "latest_dewu_package.json"
    json_text = json.dumps(asdict(result), ensure_ascii=False, indent=2)
    md_path.write_text(result.markdown_package, encoding="utf-8")
    json_path.write_text(json_text, encoding="utf-8")
    latest_path.write_text(json_text, encoding="utf-8")
    return md_path, json_path


def copy_component(text: str, button_label: str) -> None:
    payload = json.dumps(text)
    label = json.dumps(button_label)
    components.html(
        f"""
        <button id="copyBtn" style="
            border:0;border-radius:8px;background:#111827;color:white;
            padding:10px 14px;font-size:14px;font-weight:650;cursor:pointer;">
            {button_label}
        </button>
        <span id="copyMsg" style="margin-left:10px;color:#64748b;font-size:13px;"></span>
        <script>
        const text = {payload};
        const label = {label};
        const btn = document.getElementById("copyBtn");
        const msg = document.getElementById("copyMsg");
        btn.onclick = async () => {{
            try {{
                await navigator.clipboard.writeText(text);
                msg.innerText = "已复制";
            }} catch (e) {{
                msg.innerText = "复制失败，请手动选择文本复制";
            }}
        }};
        </script>
        """,
        height=48,
    )


def page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container { max-width: 1240px; padding-top: 2rem; }
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] { border-radius: 8px; }
        div[data-testid="stMetricValue"] { font-size: 22px; }
        .notice {
            border: 1px solid #dbe3ef;
            background: #f8fafc;
            border-radius: 8px;
            padding: 14px 16px;
            color: #334155;
            line-height: 1.7;
        }
        .small-note { color: #64748b; font-size: 13px; line-height: 1.6; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="得物图文风格执行包生成器", page_icon="📦", layout="wide")
    page_style()

    st.title("得物图文风格执行包生成器")
    st.caption("上传产品图并填写少量信息，生成可复制给 ChatGPT 的 10 组得物图文执行包。本工具不生成图片，不调用 OpenAI API。")

    st.markdown(
        """
        <div class="notice">
        本工具只做本地规则整理和提示词生成。图片中看不清的信息不会被写成确定事实；发给 ChatGPT 出图时，请把执行包和产品图一起上传。
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("产品图")
        uploaded_files = st.file_uploader(
            "上传 jpg / jpeg / png / webp / heic / heif",
            type=["jpg", "jpeg", "png", "webp", "heic", "heif"],
            accept_multiple_files=True,
        )
        image_infos: list[UploadedImageInfo] = []
        if uploaded_files:
            for file in uploaded_files:
                info = save_uploaded_file(file)
                image_infos.append(info)
                if info.status in ["uploaded", "converted"]:
                    st.success(f"{file.name}：{info.message}")
                    if info.preview_path:
                        st.image(str(BASE_DIR / info.preview_path), caption=info.preview_path, use_container_width=True)
                else:
                    st.warning(f"{file.name}：{info.message}")
        else:
            st.info("请上传至少一张产品图。")

        st.divider()
        st.header("风格设置")
        style_count = st.slider("输出风格组数量", min_value=1, max_value=14, value=10)
        style_options = [f"{style['id']} {style['name']}" for style in STYLE_LIBRARY]
        manual_styles = st.multiselect("手动固定风格，可不选", style_options)
        manual_ids = [item.split(" ", 1)[0] for item in manual_styles]

    with st.form("dewu_form"):
        col1, col2 = st.columns(2)
        with col1:
            product_name = st.text_input("产品名称，可选")
            brand_name = st.text_input("品牌名称，可选")
            category = st.text_input("产品品类，可选", placeholder="例：洗衣凝珠、浴室清洁剂、擦鞋湿巾")
            target_user = st.text_input("目标人群，可选", placeholder="例：通勤女生、宝妈、宿舍党、家庭用户")
            usage_scene = st.text_input("使用场景，可选", placeholder="例：阳台洗衣、浴室清洁、外出救场")
        with col2:
            selling_points = st.text_area("核心卖点，可选，多行", height=112, placeholder="每行一条。只写确认过的卖点。")
            proof_info = st.text_area("已有检测/专利/认证信息，可选", height=112, placeholder="每行一条。没有就留空，不会编造。")
            visible_info = st.text_area("包装可见信息/图片可读信息，可选", height=112, placeholder="例：包装可见规格、香型、卖点短语等。")
            extra_forbidden = st.text_area("禁止使用的词，可选", height=80, placeholder="每行一条。")

        submitted = st.form_submit_button("生成得物图文执行包", use_container_width=True)
        clear = st.form_submit_button("清空重填")

    if clear:
        st.session_state.pop("result", None)
        st.rerun()

    if submitted:
        extra_words = split_lines(extra_forbidden)
        product = ProductInfo(
            product_name=first_or_unknown(product_name),
            brand_name=first_or_unknown(brand_name),
            category=first_or_unknown(category),
            selling_points=sanitize_items([*split_lines(selling_points), *split_lines(visible_info)], extra_words),
            target_user=first_or_unknown(target_user),
            usage_scene=first_or_unknown(usage_scene),
            proof_info=sanitize_items(split_lines(proof_info), extra_words),
            forbidden_words=unique_keep_order(["已内置平台敏感词过滤", "已内置绝对化用语过滤", *sanitize_items(extra_words)]),
            visible_info=sanitize_text(visible_info, extra_words) or "图片不可确认",
        )
        styles = select_styles(product, style_count, manual_ids)
        result = build_result(product, image_infos, styles)
        md_path, json_path = persist_result(result)
        st.session_state["result"] = result
        st.session_state["md_path"] = md_path
        st.session_state["json_path"] = json_path

    result: GeneratedResult | None = st.session_state.get("result")
    if result:
        json_text = json.dumps(asdict(result), ensure_ascii=False, indent=2)
        st.divider()
        st.subheader("生成结果")

        c1, c2, c3 = st.columns(3)
        c1.metric("风格组", len(result.groups))
        c2.metric("图片提示词", len(result.groups) * 5)
        c3.metric("文章", len(result.groups))

        tabs = st.tabs(["区域 A：摘要", "区域 B：ChatGPT 执行包", "区域 C：JSON 备份", "逐组预览"])

        with tabs[0]:
            st.markdown(result.summary)
            st.download_button(
                "下载 Markdown 执行包",
                data=result.markdown_package.encode("utf-8"),
                file_name=st.session_state["md_path"].name,
                mime="text/markdown",
                use_container_width=True,
            )

        with tabs[1]:
            copy_component(result.markdown_package, "一键复制 ChatGPT 执行包")
            st.text_area("ChatGPT 执行包", value=result.markdown_package, height=620)
            st.download_button(
                "导出 Markdown 文件",
                data=result.markdown_package.encode("utf-8"),
                file_name=st.session_state["md_path"].name,
                mime="text/markdown",
                use_container_width=True,
            )

        with tabs[2]:
            copy_component(json_text, "一键复制 JSON")
            st.text_area("JSON 备份", value=json_text, height=560)
            st.download_button(
                "导出 JSON 文件",
                data=json_text.encode("utf-8"),
                file_name=st.session_state["json_path"].name,
                mime="application/json",
                use_container_width=True,
            )

        with tabs[3]:
            for group in result.groups:
                with st.expander(f"{group.style_id} {group.style_name}", expanded=False):
                    st.markdown(f"**适合原因：** {group.reason}")
                    st.markdown(f"**文章标题：** {group.title}")
                    st.write(group.article)
                    for image in group.image_prompts:
                        st.markdown(f"**图{image['image_no']}：{image['purpose']}**")
                        st.write(image["prompt"])

        st.caption(f"最近一次结果已保存到：{Path('output/latest_dewu_package.json')}")


if __name__ == "__main__":
    main()
