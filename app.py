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

DEFAULT_FORBIDDEN_WORDS = ["最强", "第一", "100%", "永久", "彻底", "无毒", "零伤害", "医学级", "医院级", "根治", "神药"]
PLATFORM_SENSITIVE_WORDS = ["小红书", "小红书爆文", "小红书风", "真人实拍感", "效果为视觉示意，实际效果以使用情况为准"]
NEGATIVE_PROMPT = (
    "不要生成平台水印、二维码、账号ID；不要重新设计产品包装；不要改写品牌名、LOGO、标签文字、"
    "瓶型/桶型、颜色和规格；不要夸大功效；不要添加未输入的数据；避免使用绝对化、医疗化、"
    "无法确认的承诺表达；不要出现平台敏感字眼；不要出现说明书式大段硬广文案。"
)


@dataclass
class UploadedImage:
    original_name: str
    original_path: str
    preview_path: str
    converted_image_path: str
    status: str
    message: str


@dataclass
class ProductInput:
    product_name: str
    brand_name: str
    core_selling_points: list[str]
    category: str
    usage_scene: str
    target_user: str
    claim_data: list[str]
    avoid_words: list[str]
    extra_notes: str
    desired_group_count: int
    style_mode: str
    selected_style_ids: list[str]
    platform_name: str
    image_format_note: str


@dataclass
class ImagePlan:
    image_no: int
    module_id: str
    module_name: str
    theme: str
    purpose: str
    scene: str
    composition: str
    product_placement: str
    visual_elements: str
    copy_options: list[str]
    style_note: str


@dataclass
class SellingPoint:
    name: str
    user_pain: str
    expression_direction: str
    needs_evidence: str
    suitable_styles: list[str]
    point_type: str


@dataclass
class GroupOutput:
    group_no: int
    style_id: str
    style_name: str
    style_position: str
    difference_anchor: str
    main_selling_point: str
    cover_direction: str
    main_scene: str
    modules: list[str]
    images: list[ImagePlan]
    alt_titles: list[str]
    article_body: str
    hashtags: list[str]
    execution_prompt: str


@dataclass
class GenerationResult:
    created_at: str
    uploaded_images: list[UploadedImage]
    product: ProductInput
    selling_point_library: list[SellingPoint]
    core_selling_points_selected: list[SellingPoint]
    selected_styles: list[dict[str, str]]
    groups: list[GroupOutput]
    markdown: str


STYLE_LIBRARY: dict[str, dict[str, object]] = {
    "G01": {"name": "真人入镜实测证据风", "position": "人物局部或手部入镜，用我在用、我试过、我推荐的逻辑建立信任。", "tone": "真实体验", "modules": ["M01", "M02", "M03", "M09", "M16"]},
    "G02": {"name": "高信任妈妈囤货种草风", "position": "宝妈和家庭常备视角，强调省心、回购、长期使用。", "tone": "家庭囤货分享", "modules": ["M01", "M12", "M15", "M04", "M16"]},
    "G03": {"name": "多场景洗衣难题一瓶解决风", "position": "用多个场景问题做骨架，突出少折腾和效率感。", "tone": "多场景解决方案", "modules": ["M01", "M06", "M07", "M18", "M16"]},
    "G04": {"name": "情绪香氛氛围感故事风", "position": "香气、心情和生活质感切入，画面柔和，有气味想象。", "tone": "香氛氛围日记", "modules": ["M01", "M05", "M11", "M20", "M16"]},
    "G05": {"name": "敏感肌安心成分信任风", "position": "从谨慎选择和贴身衣物顾虑切入，理性克制，不夸张。", "tone": "理性信任分享", "modules": ["M01", "M14", "M15", "M09", "M16"]},
    "G06": {"name": "家庭安全顾虑解决方案风", "position": "从家庭顾虑切入，适合全家可用、婴童可用、安心使用等表达。", "tone": "家庭顾虑解决", "modules": ["M01", "M03", "M15", "M12", "M16"]},
    "G07": {"name": "强对比去污说服风", "position": "用前后变化和清洁难题解决建立结果说服力，但表达保持克制。", "tone": "对比说服", "modules": ["M01", "M07", "M08", "M04", "M16"]},
    "G08": {"name": "对比选购优势锚定风", "position": "偏理性种草，从为什么选这个切入，对比容量、便利性和使用感。", "tone": "选购经验总结", "modules": ["M01", "M10", "M04", "M13", "M16"]},
    "G09": {"name": "人设封面香氛指南风", "position": "女生感、香气感和生活方式感，可带人物封面和穿搭氛围。", "tone": "女生香氛指南", "modules": ["M02", "M20", "M05", "M11", "M16"]},
    "G10": {"name": "长期主义高利用率清单风", "position": "强调高利用率、常备、不闲置，像长期会留在家里的东西。", "tone": "长期高频清单", "modules": ["M01", "M19", "M12", "M10", "M16"]},
    "G11": {"name": "高能量女生松弛感生活方式风", "position": "从通勤穿搭、衣物香气和松弛感生活切入，有记录感。", "tone": "状态感生活方式", "modules": ["M02", "M11", "M05", "M13", "M16"]},
    "G12": {"name": "随身救场即时清洁风", "position": "偏场景救急和临时状况，节奏快，适合应急清洁类内容。", "tone": "即时救场", "modules": ["M01", "M03", "M07", "M17", "M16"]},
    "G13": {"name": "极简高级体香氛围风", "position": "画面干净简洁，文案克制、有氛围，适合香氛和留香表达。", "tone": "极简高级氛围", "modules": ["M01", "M20", "M13", "M05", "M16"]},
    "G14": {"name": "香软衣物真实体验种草风", "position": "强调洗完舒服、香香软软和穿着体验，幸福感更强。", "tone": "香软体验分享", "modules": ["M01", "M09", "M13", "M11", "M16"]},
}

MODULE_LIBRARY: dict[str, dict[str, str]] = {
    "M01": {"name": "封面强吸引图", "purpose": "建立点击理由", "structure": "大标题+产品主体+一条强钩子", "scene": "产品在生活化场景中清晰出现"},
    "M02": {"name": "人物入镜信任图", "purpose": "增强真实分享和信任", "structure": "人物局部/手部+产品+观点短句", "scene": "手持、拿取、整理或使用动作"},
    "M03": {"name": "痛点共鸣图", "purpose": "让用户代入问题", "structure": "痛点短句+场景局部+产品解决入口", "scene": "衣物、浴室、鞋面、家务角落等问题场景"},
    "M04": {"name": "卖点总览图", "purpose": "快速看懂核心价值", "structure": "3个短卖点卡片+产品", "scene": "产品旁搭配相关生活道具"},
    "M05": {"name": "香气/情绪氛围图", "purpose": "表达气味和心情", "structure": "氛围画面+一句情绪短文案", "scene": "卧室、衣柜、阳台、床品或通勤前"},
    "M06": {"name": "多场景适配图", "purpose": "展示不同使用场景", "structure": "多场景分区但仍是一张独立内容图", "scene": "家庭、宿舍、通勤、收纳等组合"},
    "M07": {"name": "清洁难题解决图", "purpose": "突出问题被处理", "structure": "难题画面+解决逻辑+产品入镜", "scene": "脏污、异味、旧污或局部清洁需求"},
    "M08": {"name": "前后变化图", "purpose": "提供变化说服力", "structure": "前后状态对照+短结论", "scene": "同一对象处理前后的状态差异"},
    "M09": {"name": "使用体验图", "purpose": "讲顺手、舒服、方便", "structure": "使用动作+体验短句+产品", "scene": "拿取、放置、洗护、收纳、穿着体验"},
    "M10": {"name": "选购理由图", "purpose": "讲为什么选它", "structure": "选择标准+理由卡片", "scene": "对比选购或家用判断场景"},
    "M11": {"name": "生活方式图", "purpose": "让产品融入生活状态", "structure": "生活片段+产品自然出现", "scene": "通勤前、衣柜旁、居家整理、生活记录"},
    "M12": {"name": "收纳/囤货/常备图", "purpose": "强化长期常备", "structure": "收纳区+产品+囤货理由", "scene": "柜子、篮子、洗护区、家庭常备角"},
    "M13": {"name": "细节质地图", "purpose": "强化质感和细节", "structure": "产品局部/衣物局部+少量文字", "scene": "包装细节、衣物触感、柔和光线"},
    "M14": {"name": "成分/安心感图", "purpose": "理性建立信任", "structure": "安心关键词+产品+简短理由", "scene": "贴身衣物、白色衣物、干净洗护区"},
    "M15": {"name": "家庭/宝宝/贴身衣物图", "purpose": "传达家庭场景和谨慎选择", "structure": "家庭物品+产品+安心短句", "scene": "宝宝衣物、毛巾、家庭洗护空间"},
    "M16": {"name": "结尾总结种草图", "purpose": "形成收藏和行动记忆点", "structure": "总结短句+产品+场景收尾", "scene": "干净常备区或舒服生活角落"},
    "M17": {"name": "局部特写图", "purpose": "放大细节", "structure": "局部特写+短标签", "scene": "包装、内容物、局部清洁对象"},
    "M18": {"name": "懒人高效图", "purpose": "强调少折腾", "structure": "旧流程少量对照+高效结论", "scene": "忙碌家务或小空间生活"},
    "M19": {"name": "高利用率清单图", "purpose": "讲不闲置和值得留下", "structure": "清单式排版+产品", "scene": "长期常用物品清单"},
    "M20": {"name": "香氛气质图", "purpose": "表达气味气质", "structure": "香味联想+极简画面", "scene": "衣柜、床边、通勤穿搭、柔和空间"},
}

COPY_BANK: dict[str, list[str]] = {
    "G01": ["最近真的离不开它", "洗护流程少折腾了", "用起来才像真省事", "现在基本直接拿它", "真实用过更有感"],
    "G02": ["消耗快更要选省心", "家里高频真的要备", "适合家庭常备款", "放家里用着不慌", "回购逻辑很清楚"],
    "G03": ["衣服一多就懂了", "少几步轻松很多", "忙的时候更有感", "洗护没那么繁琐", "多场景都能用上"],
    "G04": ["衣服香气很加分", "房间都温柔一点", "干净和香气一起出现", "是想靠近闻闻的味道", "生活细节变舒服"],
    "G05": ["贴身衣物认真选", "天天用更要稳", "图的是长期放心", "高频用着更安心", "不花哨但很踏实"],
    "G06": ["家里用会多想一步", "少点顾虑就很好", "家庭日常安心重要", "选对家务轻一点", "适合长期放家里"],
    "G07": ["不想手搓会懂", "变化一眼能看到", "省劲差别挺明显", "清洁没那么狼狈", "结果感更有说服力"],
    "G08": ["选洗护看这些细节", "买前对比更清楚", "用久了才知道重要", "不是随便选的", "细节影响使用感"],
    "G09": ["淡淡香气很加分", "适合日常穿搭", "出门状态都不一样", "清爽又不刻意", "女生会懂这种氛围"],
    "G10": ["留下来的都高频", "不闲置才值得", "长期放家里很合适", "利用率真的重要", "常用才算值"],
    "G11": ["衣服状态影响很大", "通勤党会在意", "松弛感从细节开始", "干净气味默默加分", "出门前就想舒服点"],
    "G12": ["临时需要很顶用", "小状况能救场", "关键时刻派得上用场", "用到就知道重要", "外出带着更安心"],
    "G13": ["喜欢干净的衣服香", "不是浓香是舒服淡香", "靠近才闻到更高级", "不会抢戏的好闻", "干净气味很加分"],
    "G14": ["香软衣物难拒绝", "摸起来心情都好", "穿上身舒服感很真实", "软软香香很加分", "洗后状态让人喜欢"],
}


def split_lines(value: str) -> list[str]:
    parts = re.split(r"[\n\r,，；;]+", value or "")
    return [part.strip(" \t-•、") for part in parts if part.strip(" \t-•、")]


def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = item.strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def clean_text(value: str, extra_forbidden: Iterable[str] = ()) -> str:
    text = value or ""
    for word in [*PLATFORM_SENSITIVE_WORDS, *extra_forbidden]:
        if word:
            text = text.replace(word, "")
    return re.sub(r"\s+", " ", text).strip()


def clean_items(items: Iterable[str], extra_forbidden: Iterable[str] = ()) -> list[str]:
    return unique_keep_order(clean_text(item, extra_forbidden) for item in items)


def safe_filename(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", stem).strip("._-") or "product"
    return f"{cleaned}{suffix}"


def infer_category(product: ProductInput) -> str:
    if product.category:
        return product.category
    text = f"{product.product_name} {' '.join(product.core_selling_points)}"
    if "洗衣凝珠" in text or "凝珠" in text:
        return "洗衣凝珠 / 衣物洗护"
    if "洗衣机" in text and any(k in text for k in ["泡腾片", "清洁", "清洗"]):
        return "洗衣机清洁"
    if "留香珠" in text or "衣物香氛" in text:
        return "衣物香氛 / 留香产品"
    if "内衣" in text and any(k in text for k in ["洗衣液", "洗液", "清洗"]):
        return "贴身衣物洗护"
    if any(k in text for k in ["柔巾", "湿巾"]):
        return "母婴清洁 / 日用消耗品"
    if any(k in text for k in ["擦鞋", "鞋", "湿巾", "随身"]):
        return "鞋履清洁 / 随身清洁"
    if any(k in text for k in ["洗衣", "衣物", "留香"]):
        return "衣物洗护"
    if any(k in text for k in ["浴室", "厨房", "马桶", "清洁剂", "喷雾"]):
        return "家清清洁"
    return "品类暂不确定，按日化/家清/生活清洁产品做接近推断"


def infer_scene(product: ProductInput) -> str:
    if product.usage_scene:
        return product.usage_scene
    category = infer_category(product)
    if "衣物" in category:
        return "日常洗衣、阳台洗护、衣柜整理"
    if "即时" in category:
        return "外出救场、通勤、鞋子或衣物局部清洁"
    return "居家清洁、浴室/厨房/家庭日用场景"


def infer_user(product: ProductInput) -> str:
    if product.target_user:
        return product.target_user
    text = f"{product.product_name} {infer_scene(product)} {' '.join(product.core_selling_points)}"
    if any(k in text for k in ["宝宝", "婴童", "家庭"]):
        return "宝妈、家庭用户"
    if any(k in text for k in ["宿舍", "租房", "学生"]):
        return "学生党、租房党"
    if any(k in text for k in ["香", "通勤", "女生"]):
        return "精致女生、通勤人群"
    return "有日常清洁和生活品质需求的人"


def point(name: str, user_pain: str, expression: str, evidence: str, styles: list[str], point_type: str = "A类：通用体验卖点") -> SellingPoint:
    return SellingPoint(name, user_pain, expression, evidence, styles, point_type)


def build_selling_point_library(product: ProductInput) -> list[SellingPoint]:
    category_text = f"{product.category} {product.product_name}"
    if "洗衣凝珠" in category_text or "凝珠" in category_text:
        points = [
            point("一颗定量，减少倒洗衣液的麻烦", "不想每次倒洗衣液、估用量、弄脏瓶口", "懒人洗衣、省步骤、拿取顺手", "不需要", ["G01", "G03", "G08", "G10"]),
            point("懒人洗衣更省步骤", "洗衣流程越多越容易拖延", "把洗衣动作讲得更轻、更少折腾", "不需要", ["G03", "G10", "G11"]),
            point("香氛体验更适合日常穿着", "衣服洗完没有状态感，通勤前缺少干净气味", "衣柜淡香、穿上身清爽、靠近闻到的气味", "如写具体留香时长需要依据", ["G04", "G09", "G11", "G13", "G14"]),
            point("高频洗护更适合常备", "家庭/宿舍衣物多，消耗快，临时没有会很麻烦", "常备、囤货、用得上、不闲置", "不需要；如写具体容量需要包装可见依据", ["G02", "G10", "G08"]),
            point("小颗粒形态更好收纳", "洗护区空间小，大瓶容易占地方", "收纳更轻、拿取更顺、宿舍/租房友好", "不需要；不要编造规格", ["G08", "G10", "G12"]),
            point("适合洗衣机日常洗护场景", "日常机洗频繁，不想每次复杂搭配", "洗衣机旁、阳台洗护、日常衣物统一处理", "不需要", ["G03", "G07", "G10"]),
            point("衣服洗后清爽感更明显", "衣物闷味、汗味、洗后不够清爽会影响穿着", "洗后清爽、干净气味、穿上身舒服", "如果涉及除菌/除螨/具体去味数据需要依据", ["G04", "G11", "G13", "G14"]),
            point("对租房党/学生党更友好", "小空间用品要少占地、好拿、别太复杂", "宿舍、出租屋、阳台小角落里的省心选择", "不需要", ["G03", "G08", "G10"]),
            point("对不想手搓的人更友好", "污渍和汗味场景容易让人想手搓但又麻烦", "少手搓、少纠结、日常洗衣更轻松", "涉及具体清洁力结果需要依据或用体验表达", ["G01", "G07", "G03"]),
            point("贴身衣物安心感内容方向", "贴身衣物更想选得稳一点，不想只看香味", "谨慎选择、日常安心、家人衣物也会多想一步", "如写婴童可用、敏感肌友好、无添加需要依据", ["G05", "G06", "G14"], "B类：需要依据支持的功效卖点"),
            point("多场景衣物内容方向", "白T、毛巾、床品、通勤衣物需求不一样", "校服、白T、毛巾、床品分场景讲", "不需要；具体功效不要编造", ["G03", "G07", "G08"]),
            point("通勤衣物气味管理", "出门前衣服气味会影响状态和自信", "通勤、衣柜、穿搭前的干净气味", "如写留香小时数需要依据", ["G09", "G11", "G13"]),
        ]
    elif any(k in category_text for k in ["鞋履", "随身", "擦鞋"]):
        points = [
            point("外出临时救场", "鞋面或局部脏污突然出现，很影响出门状态", "包里/车里/办公室随手处理", "不需要", ["G12", "G01", "G08"]),
            point("局部清洁更省心", "不想为一点脏污整套清洗", "小范围处理、少折腾", "具体去污效果需要依据", ["G07", "G12"]),
            point("携带和收纳方便", "随身用品太占地方就容易闲置", "小包、抽屉、玄关常备", "如写规格数量需要依据", ["G10", "G12"]),
            point("通勤场景更自然", "上班上学路上容易遇到小状况", "通勤、约会、出门前状态管理", "不需要", ["G11", "G12"]),
            point("新鞋维护意识", "鞋子刚买更在意干净状态", "鞋履护理、穿搭细节、得物购物后维护", "不需要", ["G08", "G13"]),
            point("清爽体面感", "鞋面脏会拉低整体穿搭精致度", "局部干净、出门体面", "不需要", ["G09", "G11"]),
            point("家门口常备", "出门前发现脏污最容易手忙脚乱", "玄关、鞋柜、包内常备", "不需要", ["G02", "G10"]),
            point("材质适配提醒", "不同鞋面材质处理方式不同", "提醒先看材质、局部小范围试用", "需要包装或用户说明支持", ["G05", "G08"], "B类：需要依据支持的功效卖点"),
        ]
    else:
        points = [
            point("使用更省心", "日用品太复杂会降低使用频率", "少步骤、顺手、日常可坚持", "不需要", ["G01", "G03", "G10"]),
            point("场景更贴近日常", "只讲功能容易像广告，用户难代入", "把产品放到真实家务/通勤/收纳场景", "不需要", ["G03", "G11", "G14"]),
            point("适合高频使用", "常用产品最怕不顺手、占地方、难坚持", "高利用率、长期常备、不闲置", "不需要", ["G02", "G10"]),
            point("使用步骤更简单", "复杂流程容易被放弃", "懒人友好、少折腾、行动成本低", "不需要", ["G03", "G08", "G10"]),
            point("香气/清爽体验", "用完没有感受记忆点，种草不够鲜明", "干净气味、清爽感、生活氛围", "具体留香/去味数据需要依据", ["G04", "G09", "G13", "G14"]),
            point("收纳/携带更方便", "空间有限时，大件或复杂包装容易闲置", "洗护区、玄关、包内、宿舍收纳", "如写具体规格需要依据", ["G08", "G10", "G12"]),
            point("家庭常备更合适", "家里临时缺日用品很影响节奏", "家庭囤货、常备、多人使用场景", "不需要；如写婴童可用需要依据", ["G02", "G06", "G10"]),
            point("用完体感更清爽", "清洁后仍有黏腻、闷味或不舒服会劝退", "清爽、干净、舒服的使用后状态", "具体除菌/抑菌/除螨需要依据", ["G05", "G07", "G14"]),
            point("安心选择内容方向", "贴身、母婴或家庭场景会让用户更谨慎", "谨慎选择、少点顾虑、日常放心", "婴童可用、敏感肌友好、无添加等必须有依据", ["G05", "G06"], "B类：需要依据支持的功效卖点"),
        ]
    return points


def select_core_selling_points(product: ProductInput, library: list[SellingPoint]) -> list[SellingPoint]:
    if product.core_selling_points:
        user_points = [
            point(item, "用户主动补充的产品重点", f"围绕“{item}”做场景化种草表达", "按用户补充使用；涉及具体数据仍需依据", ["G01", "G03", "G08", "G10"])
            for item in product.core_selling_points
        ]
        return unique_selling_points([*user_points, *library])[:8]
    preferred_styles = {"G01", "G03", "G04", "G08", "G10", "G11", "G13", "G14"}
    sorted_points = sorted(library, key=lambda item: len(preferred_styles.intersection(item.suitable_styles)), reverse=True)
    return sorted_points[:8]


def unique_selling_points(points: Iterable[SellingPoint]) -> list[SellingPoint]:
    seen: set[str] = set()
    result: list[SellingPoint] = []
    for item in points:
        if item.name not in seen:
            seen.add(item.name)
            result.append(item)
    return result


def normalize_product(raw: ProductInput) -> ProductInput:
    avoid = unique_keep_order([*DEFAULT_FORBIDDEN_WORDS, *raw.avoid_words])
    product = ProductInput(
        product_name=clean_text(raw.product_name, avoid) or "图片中的产品",
        brand_name=clean_text(raw.brand_name, avoid) or "图片可见品牌",
        core_selling_points=clean_items(raw.core_selling_points, avoid)[:5],
        category=clean_text(raw.category, avoid),
        usage_scene=clean_text(raw.usage_scene, avoid),
        target_user=clean_text(raw.target_user, avoid),
        claim_data=clean_items(raw.claim_data, avoid),
        avoid_words=avoid,
        extra_notes=clean_text(raw.extra_notes, avoid),
        desired_group_count=max(1, min(raw.desired_group_count or 10, 10)),
        style_mode=raw.style_mode or "all",
        selected_style_ids=raw.selected_style_ids,
        platform_name=clean_text(raw.platform_name, avoid) or "得物",
        image_format_note=clean_text(raw.image_format_note, avoid),
    )
    product.category = infer_category(product)
    product.usage_scene = infer_scene(product)
    product.target_user = infer_user(product)
    return product


def select_style_ids(product: ProductInput) -> list[str]:
    valid_selected = [style_id for style_id in product.selected_style_ids if style_id in STYLE_LIBRARY]
    if product.style_mode == "single" and valid_selected:
        return valid_selected[:1]
    if product.style_mode == "multiple" and valid_selected:
        return valid_selected[:10]

    preferred = ["G01", "G03", "G04", "G08", "G10", "G05", "G09", "G02", "G07", "G11", "G13", "G06", "G12", "G14"]
    text = f"{product.category} {product.usage_scene} {' '.join(product.core_selling_points)}"
    if "洗衣凝珠" in text or "凝珠" in text:
        preferred = ["G01", "G02", "G03", "G04", "G05", "G07", "G08", "G09", "G11", "G13", "G14"]
    elif any(k in text for k in ["宝宝", "婴童", "家庭"]):
        preferred = ["G02", "G06", "G05", "G10", "G14", "G01", "G03", "G08", "G04", "G07"]
    elif any(k in text for k in ["鞋", "随身", "救场", "湿巾"]):
        preferred = ["G12", "G07", "G08", "G01", "G10", "G11", "G03", "G13", "G02", "G04"]
    elif any(k in text for k in ["香", "留香", "气味"]):
        preferred = ["G04", "G09", "G13", "G11", "G14", "G01", "G08", "G10", "G05", "G03"]
    return preferred[: product.desired_group_count]


def main_point_for_group(core_points: list[SellingPoint], style_id: str, group_no: int) -> SellingPoint:
    matching = [item for item in core_points if style_id in item.suitable_styles]
    if matching:
        return matching[(group_no - 1) % len(matching)]
    return core_points[(group_no - 1) % len(core_points)]


def format_image_note(uploaded: list[UploadedImage], manual_note: str) -> str:
    has_heic = any(info.original_name.lower().endswith((".heic", ".heif")) for info in uploaded)
    notes = []
    if has_heic:
        notes.append("若产品图为 HEIC/实况图，优先转成 JPG/PNG 后再执行，可提升识别稳定性。若为实况图，请选取清晰封面帧作为产品参考图上传。")
    if manual_note:
        notes.append(manual_note)
    return " ".join(notes) or "未发现特殊格式问题。"


def build_image_plan(product: ProductInput, style_id: str, module_id: str, image_no: int) -> ImagePlan:
    style = STYLE_LIBRARY[style_id]
    module = MODULE_LIBRARY[module_id]
    copy_pool = COPY_BANK[style_id]
    copy_options = unique_keep_order(copy_pool[image_no - 1 : image_no + 4] + copy_pool[:2])[:5]
    theme = f"{style['name']}｜{module['name']}"
    scene = f"{module['scene']}，结合{product.usage_scene}，面向{product.target_user}"
    composition = f"{module['structure']}；竖版内容图思维，单张独立生成，不拼成长图"
    product_placement = "产品清晰可见，可在画面中下方、手部旁、收纳区或场景核心位置出现；包装、LOGO、颜色和可见文字尽量保持与上传产品图一致"
    elements = f"生活化背景、自然抓拍、日常入镜、短文案贴纸；核心卖点可围绕：{'、'.join(product.core_selling_points)}"
    style_note = f"平台定位按得物图文/社区种草图文理解；本页服务于{style['tone']}，避免官方详情页感。"
    return ImagePlan(image_no, module_id, module["name"], theme, module["purpose"], scene, composition, product_placement, elements, copy_options, style_note)


def article_titles(product: ProductInput, style_id: str) -> list[str]:
    style = STYLE_LIBRARY[style_id]
    base = {
        "G01": ["这次是真的用下来才想说", "这类洗护我终于少踩坑了", "顺手这件事太重要了"],
        "G02": ["家里高频用的东西我会这样挑", "常备款真的不能乱囤", "回购逻辑很简单"],
        "G03": ["洗护步骤少一点真的轻松很多", "衣服一多就知道它的好", "多场景都能用上才省心"],
        "G04": ["衣服有干净香气心情会变好", "最近喜欢这种温柔的家务片段", "香气这件事真的很影响状态"],
        "G05": ["贴身衣物我会更认真选", "日常高频用的东西要稳一点", "不夸张但用着踏实"],
        "G06": ["家里用的东西我会多想一步", "家庭日常更需要少点顾虑", "适合家里长期放着的一类"],
        "G07": ["清洁前后差别真的会说话", "不想手搓的人会懂", "这种结果感挺有说服力"],
        "G08": ["选这类产品我更看重这些细节", "买前对比一下会更清楚", "用久了才知道差距在哪"],
        "G09": ["喜欢衣服淡淡香气的会懂", "出门前的香气状态很加分", "这种味道适合日常穿搭"],
        "G10": ["真正留下来的都是高利用率", "不闲置才是好物的关键", "长期放家里也不会浪费"],
        "G11": ["松弛感有时候从衣服开始", "通勤前我会在意这些细节", "衣服状态会影响整个人"],
        "G12": ["临时救场真的需要这种东西", "外出小状况被它稳住了", "关键时刻派得上用场很重要"],
        "G13": ["我更喜欢这种干净的衣服香", "高级感不是浓香堆出来的", "靠近才闻到的香气更舒服"],
        "G14": ["香香软软的衣服真的很难拒绝", "洗后状态舒服才是真的加分", "穿上身的舒服感很真实"],
    }[style_id]
    fillers = [f"{product.product_name}真实使用记录", f"{product.usage_scene}里的省心选择", f"{style['name']}内容标题备选"]
    return clean_items([*base, *fillers], product.avoid_words)[:5]


def build_article(product: ProductInput, style_id: str) -> str:
    style = STYLE_LIBRARY[style_id]
    claims = f"能写的依据只有：{'、'.join(product.claim_data)}，不会额外扩写成其他数据。" if product.claim_data else "没有明确提供的数据部分，不会写成确定功效。"
    return clean_text(
        f"最近我在{product.usage_scene}里更在意一件事：日用品到底能不能真的减少麻烦。"
        f"这次看的是{product.brand_name}的{product.product_name}，核心卖点是{'、'.join(product.core_selling_points)}。"
        f"它适合{product.target_user}，切入角度可以按「{style['tone']}」来讲，不用写成官方说明。"
        f"{claims}我会更建议把内容落在真实生活场景里：什么时候会用、为什么顺手、和原来方式相比少了哪些纠结。"
        f"如果你也在找一款适合{product.usage_scene}的东西，这类表达会更自然，也更像社区种草图文里的真实分享。",
        product.avoid_words,
    )


def hashtags(product: ProductInput, style_id: str) -> list[str]:
    tags = ["得物图文", "社区种草", "生活好物", "家清洗护", "真实分享", product.category, product.usage_scene, product.target_user, STYLE_LIBRARY[style_id]["tone"]]
    return clean_items([str(tag) for tag in tags], product.avoid_words)[:10]


def group_execution_prompt(product: ProductInput, group_no: int, style_id: str, images: list[ImagePlan], titles: list[str], body: str) -> str:
    style = STYLE_LIBRARY[style_id]
    image_lines = []
    for img in images:
        image_lines.append(
            f"""第{img.image_no}张：
- 主题：{img.theme}
- 目的：{img.purpose}
- 场景：{img.scene}
- 构图：{img.composition}
- 图上短文案方向：{' / '.join(img.copy_options)}"""
        )
    return clean_text(
        f"""【当前只执行这一组，不要生成其他组】

请使用我上传的产品图片作为产品主体参考，保持产品包装、LOGO、瓶型/桶型、标签、颜色、规格、可见文字一致，不要重新设计包装，不要改写品牌和包装信息。

现在请只生成第{group_no}组内容：

本组风格：
- 风格ID：{style_id}
- 风格名称：{style['name']}
- 风格定位：{style['position']}

请输出：
1. 先输出本组文章，文章是纯文本，不要放进图片里。
2. 再生成本组5张独立图片。
3. 每张图片独立生成，不要拼图，不要合集，不要九宫格，不要长图。
4. 图片中只放短标题、短标签、卖点贴纸，不要放整篇文章。
5. 本组完成后停止，不要继续下一组。

产品信息：
- 产品名：{product.product_name}
- 品牌：{product.brand_name}
- 自动识别品类：{product.category}
- 核心卖点：{'、'.join(product.core_selling_points)}
- 可用功效数据：{'、'.join(product.claim_data) if product.claim_data else '未提供，不要编造'}

5张图片分别为：

{chr(10).join(image_lines)}

文章要求：
- 像真实社区种草内容
- 有生活感
- 不要广告腔
- 和当前组风格匹配
- 标题提供5个备选：{' / '.join(titles)}
- 正文提供1篇完整内容，可参考：{body}
- 不要出现平台敏感字眼
- 不要出现平台水印、账号ID、二维码""",
        product.avoid_words,
    )


def build_group(product: ProductInput, style_id: str, group_no: int, previous_style: str | None, core_points: list[SellingPoint]) -> GroupOutput:
    style = STYLE_LIBRARY[style_id]
    modules = style["modules"]  # type: ignore[assignment]
    images = [build_image_plan(product, style_id, module_id, idx) for idx, module_id in enumerate(modules, start=1)]
    titles = article_titles(product, style_id)
    body = build_article(product, style_id)
    tags = hashtags(product, style_id)
    main_point = main_point_for_group(core_points, style_id, group_no)
    cover_direction = f"{images[0].module_name}：{main_point.expression_direction}"
    main_scene = images[0].scene
    previous = f"上一组为{previous_style}，本组切换到{style['tone']}，" if previous_style else "作为开场组，"
    difference = clean_text(f"{previous}通过模块{'、'.join(modules)}拉开首图方式、场景和文章口吻。", product.avoid_words)
    prompt = group_execution_prompt(product, group_no, style_id, images, titles, body)
    return GroupOutput(group_no, style_id, str(style["name"]), str(style["position"]), difference, main_point.name, cover_direction, main_scene, modules, images, titles, body, tags, prompt)


def style_table(groups: list[GroupOutput]) -> str:
    rows = ["| 组别 | 风格ID | 风格名称 | 主卖点 | 首图方向 | 主要场景 | 与上一组差异点 |", "|---|---|---|---|---|---|---|"]
    for group in groups:
        rows.append(f"| 第{group.group_no}组 | {group.style_id} | {group.style_name} | {group.main_selling_point} | {group.cover_direction} | {group.main_scene} | {group.difference_anchor} |")
    return "\n".join(rows)


def product_summary(product: ProductInput, image_note: str, has_image: bool) -> str:
    image_status = "已上传产品图，可把可见包装信息作为参考" if has_image else "未上传产品图；后续给 ChatGPT 出图时必须上传产品图作为包装参考"
    return f"""- 产品名：{product.product_name}
- 品牌：{product.brand_name}
- 自动识别品类：{product.category}
- 推测使用场景：{product.usage_scene}
- 推测目标人群：{product.target_user}
- 是否上传产品图：{image_status}
- 注意事项：{image_note}；没有明确依据的数据不写成确定功效，不重新设计包装，不改写品牌和包装信息。"""


def selling_point_table(points: list[SellingPoint]) -> str:
    rows = ["| 卖点名称 | 用户痛点 | 内容表达方向 | 是否需要依据 | 适合风格 | 类型 |", "|---|---|---|---|---|---|"]
    for item in points:
        rows.append(f"| {item.name} | {item.user_pain} | {item.expression_direction} | {item.needs_evidence} | {'、'.join(item.suitable_styles)} | {item.point_type} |")
    return "\n".join(rows)


def core_point_list(points: list[SellingPoint], product: ProductInput) -> str:
    lines = []
    for index, item in enumerate(points, start=1):
        reason = "用户主动补充，优先作为本产品表达重点" if item.name in product.core_selling_points else f"适合{product.category}，能自然落到{item.expression_direction}"
        lines.append(f"{index}. {item.name}：{reason}。")
    return "\n".join(lines)


def image_prompt_text(product: ProductInput, group: GroupOutput, img: ImagePlan) -> str:
    return clean_text(
        f"使用用户上传产品图作为唯一产品主体参考，保持{product.brand_name} {product.product_name}的包装、LOGO、瓶型/桶型、颜色、标签、规格和可见文字一致，不重新设计包装，不改写品牌，不生成虚假规格。"
        f"生成单张独立得物社区种草图，不拼图、不长图、不合集。主题为{img.theme}，场景为{img.scene}，构图为{img.composition}。"
        f"产品摆放：{img.product_placement}。画面元素：{img.visual_elements}。图上只放短标题/短标签，文案方向：{' / '.join(img.copy_options)}。不要出现平台水印、账号ID、二维码。",
        product.avoid_words,
    )


def build_markdown(product: ProductInput, groups: list[GroupOutput], image_note: str, selling_points: list[SellingPoint], core_points: list[SellingPoint], has_image: bool) -> str:
    parts = [
        "# 得物图文提示词生成结果",
        "",
        "## A. 产品基础信息",
        product_summary(product, image_note, has_image),
        "",
        "## B. 同品类差异化卖点库",
        selling_point_table(selling_points),
        "",
        "## C. 本次筛选出的核心卖点",
        core_point_list(core_points, product),
        "",
        "## D. 本次风格队列",
        style_table(groups),
        "",
        "## E. 分组执行包",
    ]
    for group in groups:
        parts.extend(
            [
                "",
                f"### 第{group.group_no}组｜{group.style_id} {group.style_name}",
                "",
                "#### 1. 本组风格定位",
                f"{group.style_position} 本组主卖点是「{group.main_selling_point}」，与上一组差异点：{group.difference_anchor}",
                "",
                "#### 2. 本组5张图策划",
            ]
        )
        for img in group.images:
            parts.extend(
                [
                    "",
                    f"#### 图片{img.image_no}",
                    f"- image_no：{img.image_no}",
                    f"- 图片主题：{img.theme}",
                    f"- 图片目的：{img.purpose}",
                    f"- 场景建议：{img.scene}",
                    f"- 构图建议：{img.composition}",
                    f"- 产品摆放建议：{img.product_placement}",
                    f"- 画面元素建议：{img.visual_elements}",
                    f"- 图上短文案建议：{' / '.join(img.copy_options)}",
                    f"- 给 ChatGPT 的图片提示词：{image_prompt_text(product, group, img)}",
                ]
            )
        parts.extend(
            [
                "",
                "#### 3. 本组文章",
                f"- 标题备选：{' / '.join(group.alt_titles)}",
                f"- 正文：{group.article_body}",
                f"- 标签建议：{' '.join('#' + tag for tag in group.hashtags)}",
                "",
                "#### 4. 可直接复制给 ChatGPT 的本组执行提示词",
                "```text",
                group.execution_prompt,
                "```",
            ]
        )
    return "\n".join(parts)


def save_uploaded_file(uploaded_file) -> UploadedImage:
    data = uploaded_file.getvalue()
    digest = hashlib.sha256(data).hexdigest()[:10]
    safe_name = safe_filename(uploaded_file.name)
    suffix = Path(safe_name).suffix.lower()
    original = UPLOAD_DIR / f"{Path(safe_name).stem}_{digest}{suffix}"
    original.write_bytes(data)
    if suffix in [".heic", ".heif"]:
        converted = CONVERTED_DIR / f"{Path(safe_name).stem}_{digest}.jpg"
        if not HEIF_ENABLED:
            return UploadedImage(uploaded_file.name, str(original.relative_to(BASE_DIR)), "", "", "convert_failed", "识别到 HEIC/HEIF，请手动转 JPG/PNG 后上传，或安装 pillow-heif。")
        try:
            image = Image.open(original)
            ImageOps.exif_transpose(image).convert("RGB").save(converted, "JPEG", quality=92)
            return UploadedImage(uploaded_file.name, str(original.relative_to(BASE_DIR)), str(converted.relative_to(BASE_DIR)), str(converted.relative_to(BASE_DIR)), "converted", "HEIC/HEIF 已转换为 JPG。")
        except Exception as exc:
            return UploadedImage(uploaded_file.name, str(original.relative_to(BASE_DIR)), "", "", "convert_failed", f"HEIC/HEIF 转换失败：{exc}")
    try:
        image = ImageOps.exif_transpose(Image.open(original))
        preview = CONVERTED_DIR / f"{Path(safe_name).stem}_{digest}.jpg"
        if image.mode in ("RGBA", "P"):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[-1])
            image = background
        else:
            image = image.convert("RGB")
        image.save(preview, "JPEG", quality=92)
        return UploadedImage(uploaded_file.name, str(original.relative_to(BASE_DIR)), str(preview.relative_to(BASE_DIR)), str(preview.relative_to(BASE_DIR)), "uploaded", "上传成功，已生成 JPG 预览。")
    except Exception as exc:
        return UploadedImage(uploaded_file.name, str(original.relative_to(BASE_DIR)), "", "", "preview_failed", f"上传成功，但预览失败：{exc}")


def make_result(product: ProductInput, uploaded_images: list[UploadedImage]) -> GenerationResult:
    normalized = normalize_product(product)
    image_note = format_image_note(uploaded_images, normalized.image_format_note)
    selling_points = build_selling_point_library(normalized)
    core_points = select_core_selling_points(normalized, selling_points)
    normalized.core_selling_points = [item.name for item in core_points[:8]]
    selected_ids = select_style_ids(normalized)
    groups: list[GroupOutput] = []
    previous: str | None = None
    for index, style_id in enumerate(selected_ids, start=1):
        group = build_group(normalized, style_id, index, previous, core_points)
        groups.append(group)
        previous = group.style_name
    markdown = build_markdown(normalized, groups, image_note, selling_points, core_points, bool(uploaded_images))
    return GenerationResult(
        created_at=datetime.now().isoformat(timespec="seconds"),
        uploaded_images=uploaded_images,
        product=normalized,
        selling_point_library=selling_points,
        core_selling_points_selected=core_points,
        selected_styles=[{"group": str(g.group_no), "style_id": g.style_id, "style_name": g.style_name, "difference": g.difference_anchor} for g in groups],
        groups=groups,
        markdown=markdown,
    )


def format_image_note(uploaded: list[UploadedImage], manual_note: str) -> str:
    has_heic = any(item.original_name.lower().endswith((".heic", ".heif")) for item in uploaded)
    notes = []
    if has_heic:
        notes.append("若产品图为 HEIC/实况图，优先转成 JPG/PNG 后再执行，可提升识别稳定性。若为实况图，请选取清晰封面帧作为产品参考图上传。")
    if manual_note:
        notes.append(manual_note)
    return " ".join(notes) or "无特殊格式说明。"


def persist_result(result: GenerationResult) -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = OUTPUT_DIR / f"dewu_multi_style_package_{timestamp}.md"
    json_path = OUTPUT_DIR / f"dewu_multi_style_package_{timestamp}.json"
    latest_path = OUTPUT_DIR / "latest_dewu_multi_style_package.json"
    json_text = json.dumps(asdict(result), ensure_ascii=False, indent=2)
    md_path.write_text(result.markdown, encoding="utf-8")
    json_path.write_text(json_text, encoding="utf-8")
    latest_path.write_text(json_text, encoding="utf-8")
    return md_path, json_path


def copy_button(text: str, label: str) -> None:
    components.html(
        f"""
        <button id="copy" style="border:0;border-radius:8px;background:#111827;color:white;padding:10px 14px;font-size:14px;font-weight:650;cursor:pointer">{label}</button>
        <span id="msg" style="margin-left:10px;color:#64748b;font-size:13px"></span>
        <script>
        const text = {json.dumps(text)};
        document.getElementById("copy").onclick = async () => {{
          try {{ await navigator.clipboard.writeText(text); document.getElementById("msg").innerText = "已复制"; }}
          catch(e) {{ document.getElementById("msg").innerText = "复制失败，请手动复制文本框"; }}
        }};
        </script>
        """,
        height=46,
    )


def page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container { max-width: 1240px; padding-top: 2rem; }
        .stTextInput input, .stTextArea textarea { border-radius: 8px; }
        .notice { border:1px solid #dbe3ef; background:#f8fafc; border-radius:8px; padding:14px 16px; color:#334155; line-height:1.7; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="得物图文种草内容工作流生成器", page_icon="📦", layout="wide")
    page_style()
    st.title("得物图文种草内容工作流生成器")
    st.caption("只填产品名和品牌名，也能自动识别品类、生成同品类卖点，并输出可复制给 ChatGPT 的执行包。")
    st.markdown('<div class="notice">必填只有产品名和品牌名。每组 = 5张独立图片 + 1篇文章；真正执行时建议一组一组复制给 ChatGPT。</div>', unsafe_allow_html=True)

    with st.sidebar:
        st.header("产品图")
        files = st.file_uploader("上传产品图", type=["jpg", "jpeg", "png", "webp", "heic", "heif"], accept_multiple_files=True)
        uploaded_images: list[UploadedImage] = []
        if files:
            for file in files:
                info = save_uploaded_file(file)
                uploaded_images.append(info)
                if info.preview_path:
                    st.success(f"{file.name}：{info.message}")
                    st.image(str(BASE_DIR / info.preview_path), caption=info.converted_image_path, use_container_width=True)
                else:
                    st.warning(f"{file.name}：{info.message}")
        else:
            st.info("没有产品图也可以先生成执行包；后续给 ChatGPT 出图时，需要上传产品图作为包装参考。")

        st.divider()
        st.header("风格控制")
        desired_group_count = st.slider("desired_group_count", 1, 10, 10)
        style_mode = st.radio("style_mode", ["all", "single", "multiple"], horizontal=True)
        selected_style_ids = st.multiselect("selected_style_ids", list(STYLE_LIBRARY.keys()), default=[])

    with st.form("main_form"):
        col1, col2 = st.columns(2)
        with col1:
            product_name = st.text_input("product_name 产品名称（必填）")
            brand_name = st.text_input("brand_name 品牌名（必填）")
            category = st.text_input("category 品类（选填）")
            usage_scene = st.text_input("usage_scene 使用场景（选填）")
            target_user = st.text_input("target_user 目标人群（选填）")
            platform_name = st.text_input("platform_name", value="得物")
        with col2:
            core_selling_points = st.text_area("core_selling_points 核心卖点（选填，每行一条；不填会自动生成）", height=120)
            claim_data = st.text_area("claim_data 可使用功效数据（选填，每行一条）", height=90)
            avoid_words = st.text_area("avoid_words 需规避词（选填，每行一条）", value="\n".join(DEFAULT_FORBIDDEN_WORDS), height=90)
            image_format_note = st.text_area("image_format_note 图片格式说明（选填）", height=70)
        extra_notes = st.text_area("extra_notes 补充要求（选填）", height=80)
        submitted = st.form_submit_button("生成得物图文执行包", use_container_width=True)
        clear = st.form_submit_button("清空结果")

    if clear:
        st.session_state.pop("result", None)
        st.rerun()

    if submitted:
        product = ProductInput(
            product_name=product_name,
            brand_name=brand_name,
            core_selling_points=split_lines(core_selling_points)[:5],
            category=category,
            usage_scene=usage_scene,
            target_user=target_user,
            claim_data=split_lines(claim_data),
            avoid_words=split_lines(avoid_words),
            extra_notes=extra_notes,
            desired_group_count=desired_group_count,
            style_mode=style_mode,
            selected_style_ids=selected_style_ids,
            platform_name=platform_name,
            image_format_note=image_format_note,
        )
        if not product.product_name or not product.brand_name:
            st.error("请填写产品名称和品牌名。核心卖点可以不填，系统会自动生成。")
        elif style_mode in ["single", "multiple"] and not selected_style_ids:
            st.error("当前风格模式需要选择至少一个风格ID。")
        else:
            result = make_result(product, uploaded_images)
            md_path, json_path = persist_result(result)
            st.session_state["result"] = result
            st.session_state["md_path"] = md_path
            st.session_state["json_path"] = json_path

    result: GenerationResult | None = st.session_state.get("result")
    if result:
        st.divider()
        st.subheader("生成结果")
        json_text = json.dumps(asdict(result), ensure_ascii=False, indent=2)
        c1, c2, c3 = st.columns(3)
        c1.metric("风格组", len(result.groups))
        c2.metric("自动卖点", len(result.selling_point_library))
        c3.metric("图片策划", len(result.groups) * 5)
        tabs = st.tabs(["Markdown 指令包", "JSON 备份", "逐组执行提示词"])
        with tabs[0]:
            copy_button(result.markdown, "一键复制 Markdown")
            st.text_area("可直接复制给 ChatGPT", value=result.markdown, height=720)
            st.download_button("导出 Markdown", result.markdown.encode("utf-8"), file_name=st.session_state["md_path"].name, mime="text/markdown", use_container_width=True)
        with tabs[1]:
            copy_button(json_text, "一键复制 JSON")
            st.text_area("JSON", value=json_text, height=640)
            st.download_button("导出 JSON", json_text.encode("utf-8"), file_name=st.session_state["json_path"].name, mime="application/json", use_container_width=True)
        with tabs[2]:
            for group in result.groups:
                with st.expander(f"第{group.group_no}组｜{group.style_name}（{group.style_id}）", expanded=False):
                    copy_button(group.execution_prompt, f"复制第{group.group_no}组执行提示词")
                    st.text_area("本组执行提示词", value=group.execution_prompt, height=420, key=f"group_{group.group_no}")


if __name__ == "__main__":
    main()
