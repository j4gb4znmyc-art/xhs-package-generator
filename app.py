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
PLATFORM_FORBIDDEN = ["小红书", "小红书爆文", "小红书风", "真人实拍感", "效果为视觉示意，实际效果以使用情况为准"]
NEGATIVE_PROMPT = (
    "不要生成平台水印、二维码、账号ID；不要重新设计产品包装；不要改写品牌名、LOGO、标签文字、"
    "瓶型/桶型、颜色和规格；不要夸大功效；不要添加未输入的数据；避免使用：最强、第一、100%、"
    "永久、彻底、无毒、零伤害、医学级、医院级、根治、神药；不要出现“小红书”字样；"
    "不要出现说明书式大段硬广文案。"
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
    target_user: str
    use_scene: str
    claim_points: list[str]
    package_notes: list[str]
    forbidden_words: list[str]
    extra_notes: str
    style_selection: list[str]


@dataclass
class ImagePrompt:
    image_no: int
    image_role: str
    page_structure: str
    scene_direction: str
    copy_elements: list[str]
    stickers_or_design: str
    chatgpt_image_prompt: str
    negative_prompt: str


@dataclass
class StyleOutput:
    group_no: int
    style_id: str
    style_name: str
    style_summary: str
    difference_point: str
    images: list[ImagePrompt]
    article_title: str
    article_body: str
    hashtags: list[str]
    alt_titles: list[str]


@dataclass
class GenerationResult:
    created_at: str
    uploaded_images: list[UploadedImage]
    product_summary: ProductInput
    groups: list[StyleOutput]
    markdown: str


STYLE_LIBRARY: dict[str, dict[str, object]] = {
    "STYLE_01": {
        "name": "卖点爆点冲击型",
        "summary": "首图用强卖点建立点击理由，整体节奏快，偏快速种草，不靠长故事铺垫。",
        "fit": "有明显功能卖点的清洁/洗护产品",
        "opening": "有些日用品，真的是用过之后才知道自己之前有多绕路。",
        "ending": "这组更适合想快速判断值不值得入手的人，核心就是把重点一眼讲清楚。",
        "roles": ["爆点封面", "卖点拆解", "真实场景", "使用结果", "种草收尾"],
        "structures": ["大标题+产品居中+三条短卖点", "左侧卖点卡+右侧产品", "生活场景大图+局部标注", "前后状态对照+短结论", "产品特写+收藏理由"],
        "scenes": ["桌面或洗护区的产品近景", "产品旁边摆放同类生活物品", "日常使用场景中产品清晰入镜", "清洁前后状态对照画面", "干净收纳角落或常备区"],
        "designs": ["粗体标题、醒目标签、少量箭头", "短标签、数字感排版、重点圈出", "生活化贴纸、轻标注", "对比线、勾选标记", "收藏感标签、清爽留白"],
    },
    "STYLE_02": {
        "name": "囤货清单推荐型",
        "summary": "把产品放进家庭常备/近期回购清单，重点是高频使用和不容易闲置。",
        "fit": "家清、洗护、带娃、家庭常备类产品",
        "opening": "我现在买家里常用的东西，会先想它到底是不是高频刚需。",
        "ending": "它不是那种买回来摆着看的东西，而是很容易被日常反复用到。",
        "roles": ["清单封面", "常备场景", "囤货理由", "适合人群", "回购收尾"],
        "structures": ["清单式封面+产品在收纳区", "柜子/洗衣区一角+产品同框", "三条囤货理由卡片", "人群标签+场景拼接", "常备角落+总结短句"],
        "scenes": ["家庭收纳柜或洗衣区", "阳台、浴室柜、家务工具旁", "家里高频使用物品旁边", "家庭成员生活动线中", "囤货篮或收纳架"],
        "designs": ["清单编号、勾选框、柔和色块", "生活角落标注", "三格理由卡", "人群小标签", "回购感贴纸"],
    },
    "STYLE_03": {
        "name": "脏污救场对比型",
        "summary": "用脏污、异味、旧污或尴尬场景切入，强调被产品救回来，但不夸大效果。",
        "fit": "去污、去味、清洁类产品",
        "opening": "最烦的不是脏，而是明明想处理干净，却越弄越麻烦。",
        "ending": "这类场景我会更看重实际省不省心，而不是包装上写得多热闹。",
        "roles": ["救场封面", "尴尬痛点", "对比变化", "省心理由", "解决后状态"],
        "structures": ["痛点大字+脏污局部+产品", "场景特写+情绪短句", "上下或左右对比", "卖点解释卡", "干净状态+产品收尾"],
        "scenes": ["衣物、鞋面、台面或污渍局部", "出门前或家务中遇到麻烦", "清洁前后同角度对比", "产品旁边放清洁对象", "处理后的清爽场景"],
        "designs": ["警示感标签、局部放大框", "尴尬语气贴纸", "对比线、箭头", "原因解释卡", "轻松收尾文字"],
    },
    "STYLE_04": {
        "name": "故事带入氛围型",
        "summary": "从一个生活片段或情绪切入，不堆卖点，靠氛围和真实场景自然带出产品。",
        "fit": "香氛洗护、生活方式类产品",
        "opening": "最近我发现，生活舒服一点，往往不是靠大改变，而是一些很小的细节。",
        "ending": "它适合放在那种慢慢变舒服的日常里，不用很用力地证明什么。",
        "roles": ["故事封面", "生活片段", "产品出现", "体验细节", "情绪收尾"],
        "structures": ["氛围大图+短句标题", "生活切片图+一句旁白", "产品自然入镜", "细节特写+感受词", "干净空间+情绪文案"],
        "scenes": ["卧室、阳台、衣柜或柔和自然光下", "收衣服、整理物品、做家务的片段", "产品放在生活动线中", "衣物、香气、触感相关细节", "舒服整洁的居家角落"],
        "designs": ["低饱和色调、短句排版", "手写感贴纸", "轻标注", "细节圆圈", "留白和氛围字"],
    },
    "STYLE_05": {
        "name": "敏感友好信任型",
        "summary": "更克制理性，先讲顾虑，再讲为什么愿意选择它，重点是安心和信任感。",
        "fit": "敏感肌、婴童衣物、家庭友好型产品",
        "opening": "有些东西我不会只看香不香、干不干净，还会看每天用着会不会有负担。",
        "ending": "如果你也属于会认真挑日用品的人，这个方向会比较有参考价值。",
        "roles": ["顾虑封面", "认真选择", "安心卖点", "温和体验", "信任收尾"],
        "structures": ["干净背景+顾虑标题", "选择标准清单", "卖点卡片+产品", "衣物/家庭细节图", "适合人群总结"],
        "scenes": ["白色衣物、床边、洗护区", "整理贴身衣物或家庭物品", "产品和补充信息同框", "柔和家居场景", "家人使用相关生活角落"],
        "designs": ["浅色底、理性标签、少量勾选", "选择标准表", "克制卖点卡", "温柔贴纸", "安心感总结"],
    },
    "STYLE_06": {
        "name": "真人首图带入型",
        "summary": "首图用人物或手部带入，口吻更活人，像用户正在分享自己的真实选择。",
        "fit": "女性向、家居洗护、香氛类",
        "opening": "我买东西其实挺看第一眼感觉，但能不能留下来，还是看它有没有真的融进生活。",
        "ending": "这组更像一个人的日常分享，不是把卖点一条条念出来。",
        "roles": ["人物封面", "个人场景", "产品理由", "体验瞬间", "分享收尾"],
        "structures": ["人物局部+产品+观点标题", "镜前/卧室/阳台场景", "三条选择理由", "动作瞬间图", "手持产品收尾"],
        "scenes": ["人物手持或半身入镜", "通勤前、卧室、阳台或衣柜旁", "产品放在生活物品旁", "使用动作或整理动作", "轻松自然的手持分享"],
        "designs": ["人物观点标题", "plog小字", "理由贴纸", "动作箭头", "口语化收尾"],
    },
    "STYLE_07": {
        "name": "萌娃/家庭安全感型",
        "summary": "用家庭和宝宝/孩子相关场景强化安全感和妈妈视角，语气柔和但不夸大。",
        "fit": "宝宝可用、家庭共用类产品",
        "opening": "家里有小朋友之后，很多日用品我都会下意识挑得更细一点。",
        "ending": "这种东西不是为了制造焦虑，而是让每天的家务少一点纠结。",
        "roles": ["家庭封面", "娃衣/家庭场景", "选择标准", "使用安心点", "家庭收尾"],
        "structures": ["家庭场景+柔和标题", "宝宝衣物或家庭用品同框", "妈妈选择标准", "产品+安心理由", "收纳常备画面"],
        "scenes": ["儿童房、卧室、洗衣区或家庭收纳处", "宝宝衣物、毛巾、家庭衣物", "家务台面上的选择对比", "产品在家庭日用品旁", "干净柔和的家庭角落"],
        "designs": ["柔和色块、家庭标签", "小图标贴纸", "标准清单", "安心理由卡", "温柔收尾短句"],
    },
    "STYLE_08": {
        "name": "长期主义效率型",
        "summary": "强调长期用下来减少折腾、省时间和省精力，文案偏理性自洽。",
        "fit": "懒人洗护、效率型产品",
        "opening": "我现在更喜欢那些能长期减少麻烦的东西，而不是只在第一次用时新鲜。",
        "ending": "日用品真正的价值，是过一段时间之后你还愿意继续用它。",
        "roles": ["效率观点封面", "旧流程麻烦", "省事逻辑", "长期使用场景", "效率收尾"],
        "structures": ["观点标题+产品", "旧方式步骤对照", "省事逻辑图", "长期常用场景", "一句结论收尾"],
        "scenes": ["简洁洗护区或家务台面", "旧工具/旧流程与产品同框", "产品旁边放日常物品", "一周生活动线或收纳处", "干净整齐的常备区"],
        "designs": ["理性标题、流程线", "少量叉号", "逻辑箭头", "日历/长期标签", "结论贴纸"],
    },
    "STYLE_09": {
        "name": "拼贴生活流型",
        "summary": "像生活切片合集，节奏碎片化，有多场景、多物品、多感受，但仍保持单张独立生成。",
        "fit": "得物图文、内容社区风",
        "opening": "这不是那种一眼看完参数就下结论的东西，更像是慢慢出现在日常里的小细节。",
        "ending": "所以我会把它归到生活流好物里，存在感不夸张，但挺实用。",
        "roles": ["生活流封面", "碎片场景", "细节拼贴", "卖点轻解释", "日常结尾"],
        "structures": ["单张图内有生活切片排版", "两到三块生活画面", "局部细节+短标签", "产品与生活道具同框", "plog式收尾"],
        "scenes": ["桌面、衣柜、阳台、包内或浴室角落组合", "不同时间段的使用片段", "产品、衣物、手部、道具细节", "卖点被放进生活场景中", "轻松日常收尾画面"],
        "designs": ["拼贴感边框、便签、小箭头", "plog日期感", "局部标签", "轻解释卡", "生活流短句"],
    },
    "STYLE_10": {
        "name": "高颜值高级感型",
        "summary": "画面更简洁有审美，少字少堆叠，用质感、香味、空间感完成种草。",
        "fit": "香氛、品质感洗护、精致女生向产品",
        "opening": "有些东西不需要把卖点堆满屏，放在那里就能看出它适合什么样的生活状态。",
        "ending": "它更适合喜欢干净、简单、有一点质感的人。",
        "roles": ["高级感封面", "空间氛围", "产品质感", "细节感受", "审美收尾"],
        "structures": ["留白封面+短标题", "空间图+产品", "产品局部质感", "感受词卡片", "极简收尾"],
        "scenes": ["低饱和居家角落、衣柜、床边或洗护区", "干净空间里的产品摆放", "产品包装与材质细节", "衣物、香气、触感联想", "简洁审美生活画面"],
        "designs": ["少字、细字体、留白", "浅色底", "质感标注", "小卡片", "极简结论"],
    },
    "STYLE_11": {
        "name": "测评对比活力排版型",
        "summary": "排版更活跃，适合用为什么最后留它的角度做对比，但不硬拉踩。",
        "fit": "有明确差异卖点的产品",
        "opening": "我试东西不太喜欢一上来就夸，更愿意看它最后有没有被留下来。",
        "ending": "留下来的原因很简单：它在几个关键场景里更顺手。",
        "roles": ["测评封面", "对比标准", "使用感打分", "留下理由", "结论收尾"],
        "structures": ["测评感标题+产品", "标准列表", "打分/勾选卡", "三条留下理由", "结论卡片"],
        "scenes": ["桌面测评区或家务台面", "同类使用场景对照", "产品与测试对象同框", "日常真实使用一角", "总结式测评画面"],
        "designs": ["活力色块、评分条", "标准卡", "勾选贴纸", "理由编号", "结论框"],
    },
    "STYLE_12": {
        "name": "宿舍/租房党省心型",
        "summary": "切入小空间生活，强调好收纳、方便、省事、不占脑子，适合年轻用户。",
        "fit": "学生党、租房党相关产品",
        "opening": "小空间生活最怕东西不好放、用起来麻烦，还容易把桌面和角落弄得很乱。",
        "ending": "对宿舍和租房生活来说，省心比花哨重要太多。",
        "roles": ["小空间封面", "宿舍痛点", "省心卖点", "收纳场景", "年轻人收尾"],
        "structures": ["宿舍/租房标题+产品", "小空间痛点图", "省事理由卡", "收纳位置展示", "轻松生活收尾"],
        "scenes": ["宿舍桌面、出租屋浴室、阳台或小洗衣区", "空间局促但真实的生活角落", "产品与小空间工具同框", "柜子、篮子、角落收纳", "年轻用户生活场景"],
        "designs": ["年轻化贴纸、空间标签", "痛点短句", "省心卡片", "收纳标注", "轻松口语收尾"],
    },
}


def split_lines(value: str) -> list[str]:
    parts = re.split(r"[\n\r；;]+", value or "")
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
    for word in [*PLATFORM_FORBIDDEN, *extra_forbidden]:
        if word:
            text = text.replace(word, "")
    return re.sub(r"\s+", " ", text).strip()


def clean_items(items: Iterable[str], extra_forbidden: Iterable[str] = ()) -> list[str]:
    return unique_keep_order(clean_text(item, extra_forbidden) for item in items)


def safe_filename(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    return f"{re.sub(r'[^a-zA-Z0-9._-]+', '_', stem).strip('._-') or 'product'}{suffix}"


def fallback_target_user(product_name: str, scene: str) -> str:
    text = f"{product_name} {scene}"
    if any(k in text for k in ["宝宝", "婴童", "母婴"]):
        return "宝妈、家庭用户"
    if any(k in text for k in ["宿舍", "租房", "学生"]):
        return "学生党、租房党"
    if any(k in text for k in ["香氛", "香", "通勤"]):
        return "精致女生、打工人"
    return "有日常清洁和生活品质需求的人"


def fallback_scene(product_name: str, selling_points: list[str]) -> str:
    text = f"{product_name} {' '.join(selling_points)}"
    if any(k in text for k in ["鞋", "随身", "湿巾"]):
        return "外出救场、鞋子清洁"
    if any(k in text for k in ["浴室", "马桶", "厨房", "油污"]):
        return "浴室或厨房清洁"
    if any(k in text for k in ["洗衣", "凝珠", "衣物", "留香"]):
        return "日常洗衣、阳台洗护"
    return "日常居家使用"


def normalize_product(raw: ProductInput) -> ProductInput:
    forbidden = unique_keep_order([*DEFAULT_FORBIDDEN_WORDS, *raw.forbidden_words])
    product_name = clean_text(raw.product_name, forbidden) or "图片中的产品"
    brand_name = clean_text(raw.brand_name, forbidden) or "图片可见品牌"
    selling = clean_items(raw.core_selling_points, forbidden)
    target = clean_text(raw.target_user, forbidden) or fallback_target_user(product_name, raw.use_scene)
    scene = clean_text(raw.use_scene, forbidden) or fallback_scene(product_name, selling)
    return ProductInput(
        product_name=product_name,
        brand_name=brand_name,
        core_selling_points=selling,
        target_user=target,
        use_scene=scene,
        claim_points=clean_items(raw.claim_points, forbidden),
        package_notes=clean_items(raw.package_notes, forbidden),
        forbidden_words=forbidden,
        extra_notes=clean_text(raw.extra_notes, forbidden),
        style_selection=raw.style_selection,
    )


def style_ids_from_selection(selection: list[str]) -> list[str]:
    if not selection or "ALL" in selection:
        return [f"STYLE_{i:02d}" for i in range(1, 11)]
    valid = [sid for sid in selection if sid in STYLE_LIBRARY]
    return valid or [f"STYLE_{i:02d}" for i in range(1, 11)]


def product_reference_sentence(product: ProductInput) -> str:
    return (
        "使用用户上传的产品图片作为真实产品主体参考，保持产品包装、LOGO、瓶型/桶型、标签、颜色、"
        "规格、可见文字尽量一致，不重新设计包装，不改写品牌和包装信息。"
    )


def build_copy_elements(style_id: str, product: ProductInput, image_no: int) -> list[str]:
    selling = product.core_selling_points or ["日常更省心", "用起来方便", "适合常备"]
    style_specific = {
        "STYLE_01": ["这点太戳我", selling[0], "省心很多"],
        "STYLE_02": ["近期常备清单", "家里用得上", selling[0]],
        "STYLE_03": ["被它救了", "脏感少很多", selling[0]],
        "STYLE_04": ["舒服生活小细节", "干净感在线", selling[0]],
        "STYLE_05": ["认真挑才安心", "日常用着舒服", selling[0]],
        "STYLE_06": ["我会留下它", "真实用着顺手", selling[0]],
        "STYLE_07": ["家里用更省心", "妈妈视角会懂", selling[0]],
        "STYLE_08": ["长期用才省事", "少折腾很多", selling[0]],
        "STYLE_09": ["生活流好物", "日常切片", selling[0]],
        "STYLE_10": ["干净质感在线", "少一点负担", selling[0]],
        "STYLE_11": ["最后留下它", "对比后更清楚", selling[0]],
        "STYLE_12": ["小空间也省心", "宿舍党会懂", selling[0]],
    }
    pool = style_specific.get(style_id, ["日常更省心", selling[0]])
    return unique_keep_order(pool[image_no - 1 : image_no + 2] or pool[:2])[:3]


def build_image_prompt(style_id: str, style: dict[str, object], product: ProductInput, image_no: int) -> ImagePrompt:
    roles: list[str] = style["roles"]  # type: ignore[assignment]
    structures: list[str] = style["structures"]  # type: ignore[assignment]
    scenes: list[str] = style["scenes"]  # type: ignore[assignment]
    designs: list[str] = style["designs"]  # type: ignore[assignment]
    role = roles[image_no - 1]
    structure = structures[image_no - 1]
    scene = scenes[image_no - 1]
    design = designs[image_no - 1]
    copy_elements = build_copy_elements(style_id, product, image_no)
    selling = "、".join(product.core_selling_points[:4]) if product.core_selling_points else "用户输入的核心卖点"
    claims = f"可使用依据：{'、'.join(product.claim_points)}。" if product.claim_points else "不要添加用户未输入的数据。"
    prompt = (
        f"请生成一张独立竖版得物图文内容图，当前是第{image_no}张，作用是「{role}」。"
        f"页面结构：{structure}。场景方向：{scene}，结合{product.use_scene}，面向{product.target_user}。"
        f"{product_reference_sentence(product)}"
        f"产品为{product.brand_name} {product.product_name}，核心卖点围绕：{selling}。{claims}"
        f"可以生成新的生活场景、背景、人物、贴纸、标题和排版，画面要生活化、有代入感，像真实用户分享，不像官方详情页。"
        f"图中文字使用这些短文案：{' / '.join(copy_elements)}。设计元素：{design}。"
        f"不要出现平台名、平台标识、扫码图形、账号标识，不要出现夸大承诺和不存在的数据。"
    )
    return ImagePrompt(
        image_no=image_no,
        image_role=role,
        page_structure=structure,
        scene_direction=scene,
        copy_elements=copy_elements,
        stickers_or_design=design,
        chatgpt_image_prompt=clean_text(prompt),
        negative_prompt=NEGATIVE_PROMPT,
    )


def alt_titles_for(style_id: str, product: ProductInput) -> list[str]:
    category = product.product_name
    scene = product.use_scene
    base = {
        "STYLE_01": [f"{category}这个点真的很戳我", "这类日用品我怎么才知道", "用过才懂它省在哪"],
        "STYLE_02": ["近期家里常备清单", f"{scene}里我会留下它", "这类消耗品真的会回购"],
        "STYLE_03": ["差点翻车，还好有它", "这个救场能力我服了", "脏感少了很多那一刻"],
        "STYLE_04": ["舒服生活是这些细节堆出来的", "最近很喜欢这个家务小片段", "干净感真的会影响心情"],
        "STYLE_05": ["认真挑过才敢长期用", "贴身和家用我会更谨慎", "温和省心这点很重要"],
        "STYLE_06": ["我会留下它的理由", "不是硬夸是真的顺手", "这个日常小物有点实用"],
        "STYLE_07": ["家里有娃之后我会这样选", "妈妈视角真的会在意这些", "家庭常用更要省心"],
        "STYLE_08": ["长期用下来才知道省事", "减少折腾才是真的好用", "日常效率感被它拉起来"],
        "STYLE_09": ["最近生活里的一个小细节", "这些日常切片里都有它", "生活流好物不用太用力"],
        "STYLE_10": ["干净质感真的会加分", "喜欢这种不吵的高级感", "香气和质感都刚刚好"],
        "STYLE_11": ["为什么我最后留下它", "对比之后选择更清楚", "这个差异点挺关键"],
        "STYLE_12": ["宿舍党真的会懂", "小空间生活需要这种省心", "租房党少折腾清单"],
    }.get(style_id, ["这个日常好物挺省心"])
    fillers = [
        f"{category}真实使用感分享",
        f"{scene}里的省心选择",
        f"{product.brand_name}{category}日常记录",
        f"适合{product.target_user}的生活好物",
        f"{category}种草内容灵感",
    ]
    return clean_items([*base, *fillers])[:8]


def hashtags_for(style_id: str, product: ProductInput, group_no: int) -> list[str]:
    pools = [
        ["得物图文", "种草内容", "生活好物", "日常清洁", "真实分享", "家居日用", "省心好物", "内容种草"],
        ["囤货清单", "家里常备", "高频好物", "家庭日用", "回购清单", "实用主义", "生活清单", "居家好物"],
        ["清洁救场", "前后对比", "去污好物", "清爽感", "省力清洁", "日常救场", "使用体验", "清洁记录"],
        ["生活方式", "氛围感日常", "香氛洗护", "居家片段", "生活细节", "干净感", "自然分享", "质感生活"],
    ]
    tags = pools[(group_no - 1) % len(pools)]
    extra = [product.product_name, product.use_scene, product.target_user]
    return clean_items([*tags, *extra])[:10]


def build_article(style_id: str, style: dict[str, object], product: ProductInput, group_no: int) -> tuple[str, str, list[str], list[str]]:
    titles = alt_titles_for(style_id, product)
    title = titles[0]
    selling = product.core_selling_points or ["日常用起来更省心", "使用步骤不复杂", "适合长期常备"]
    claim_sentence = f"能写的依据只有：{'、'.join(product.claim_points)}，所以我不会额外脑补别的数据。" if product.claim_points else "功效数据没有额外确认的部分，我就不往夸张了写。"
    package_sentence = f"包装上能确认的重点是：{'、'.join(product.package_notes)}。" if product.package_notes else "包装上看不清或没有明确输入的部分，就不当成确定卖点。"
    body = (
        f"{style['opening']}我这次关注的是{product.brand_name}的{product.product_name}，"
        f"主要放在{product.use_scene}里看它到底顺不顺手。"
        f"它最打动我的点不是把话说得很满，而是这几件事比较贴近日常：{'、'.join(selling[:4])}。"
        f"{package_sentence}{claim_sentence}"
        f"如果你是{product.target_user}，其实会更在意它能不能融进日常，而不是只看一次性的惊艳。"
        f"我会把它理解成一个偏实用的选择：画面里可以讲生活场景、使用感、收纳常备和细节变化，"
        f"但不要写成官方说明书，也不要编造看不清的信息。{style['ending']}"
    )
    return clean_text(title), clean_text(body), hashtags_for(style_id, product, group_no), titles


def build_group(group_no: int, style_id: str, product: ProductInput) -> StyleOutput:
    style = STYLE_LIBRARY[style_id]
    images = [build_image_prompt(style_id, style, product, i) for i in range(1, 6)]
    title, body, hashtags, titles = build_article(style_id, style, product, group_no)
    difference = f"本组使用「{style['name']}」逻辑，重点是{style['summary']}，首图、场景和叙事顺序与前后组错开。"
    return StyleOutput(
        group_no=group_no,
        style_id=style_id,
        style_name=str(style["name"]),
        style_summary=str(style["summary"]),
        difference_point=clean_text(difference),
        images=images,
        article_title=title,
        article_body=body,
        hashtags=hashtags,
        alt_titles=titles,
    )


def format_product_summary(product: ProductInput) -> str:
    return f"""- product_name：{product.product_name}
- brand_name：{product.brand_name}
- core_selling_points：{", ".join(product.core_selling_points) if product.core_selling_points else "未填写"}
- target_user：{product.target_user}
- use_scene：{product.use_scene}
- claim_points：{", ".join(product.claim_points) if product.claim_points else "未提供，不编造"}
- package_notes：{", ".join(product.package_notes) if product.package_notes else "未提供，不编造"}
- forbidden_words：{", ".join(product.forbidden_words)}
- extra_notes：{product.extra_notes or "无"}"""


def build_markdown(product: ProductInput, groups: list[StyleOutput]) -> str:
    parts = [
        "# 得物图文提示词生成结果",
        "",
        "## 产品摘要",
        format_product_summary(product),
        "",
        "## 风格输出",
    ]
    for group in groups:
        parts.extend(
            [
                "",
                f"### 第{group.group_no}组｜{group.style_name}（{group.style_id}）",
                f"- 风格说明：{group.style_summary}",
                f"- 本组与其他组的差异点：{group.difference_point}",
            ]
        )
        for image in group.images:
            parts.extend(
                [
                    "",
                    f"#### 图片{image.image_no}",
                    f"- 作用：{image.image_role}",
                    f"- 页面结构：{image.page_structure}",
                    f"- 场景方向：{image.scene_direction}",
                    f"- 画面短文案：{' / '.join(image.copy_elements)}",
                    f"- 设计元素：{image.stickers_or_design}",
                    f"- 给 ChatGPT 的图片提示词：{image.chatgpt_image_prompt}",
                    f"- 负面提示词：{image.negative_prompt}",
                ]
            )
        parts.extend(
            [
                "",
                "#### 本组文章",
                f"- 标题：{group.article_title}",
                f"- 正文：{group.article_body}",
                f"- 标签：{' '.join('#' + tag for tag in group.hashtags)}",
                f"- 备选标题：{' / '.join(group.alt_titles)}",
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
            return UploadedImage(uploaded_file.name, str(original.relative_to(BASE_DIR)), "", "", "convert_failed", "已识别 HEIC/HEIF，但当前环境缺少 pillow-heif，请手动转 JPG 后上传。")
        try:
            image = Image.open(original)
            ImageOps.exif_transpose(image).convert("RGB").save(converted, "JPEG", quality=92)
            return UploadedImage(uploaded_file.name, str(original.relative_to(BASE_DIR)), str(converted.relative_to(BASE_DIR)), str(converted.relative_to(BASE_DIR)), "converted", "HEIC/HEIF 已转换为 JPG，发给 ChatGPT 时优先用转换后的 JPG。")
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


def persist_result(result: GenerationResult) -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = OUTPUT_DIR / f"dewu_workflow_package_{timestamp}.md"
    json_path = OUTPUT_DIR / f"dewu_workflow_package_{timestamp}.json"
    latest_path = OUTPUT_DIR / "latest_dewu_workflow_package.json"
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


def make_result(product: ProductInput, uploaded_images: list[UploadedImage]) -> GenerationResult:
    normalized = normalize_product(product)
    style_ids = style_ids_from_selection(normalized.style_selection)
    groups = [build_group(i, style_id, normalized) for i, style_id in enumerate(style_ids, start=1)]
    markdown = build_markdown(normalized, groups)
    return GenerationResult(datetime.now().isoformat(timespec="seconds"), uploaded_images, normalized, groups, markdown)


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
    st.set_page_config(page_title="得物图文工作流提示词生成器", page_icon="📦", layout="wide")
    page_style()
    st.title("得物图文工作流提示词生成器")
    st.caption("输入产品信息，生成可交给 ChatGPT 继续生成“5张图 + 1篇文章”的结构化提示词包。")
    st.markdown('<div class="notice">本工具不直接生成图片，不调用图片接口；输出内容按组完整展开，默认 ALL 生成 STYLE_01~STYLE_10。</div>', unsafe_allow_html=True)

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
            st.info("产品图只用于本地预览。最终请把产品图和执行包一起发给 ChatGPT。")

        st.divider()
        st.header("风格选择")
        all_option = ["ALL"]
        style_options = [*all_option, *STYLE_LIBRARY.keys()]
        selected_styles = st.multiselect("style_selection", style_options, default=["ALL"])
        if "ALL" in selected_styles:
            st.caption("ALL 默认输出 STYLE_01~STYLE_10。")

    with st.form("workflow_form"):
        col1, col2 = st.columns(2)
        with col1:
            product_name = st.text_input("product_name 产品名称（必填）")
            brand_name = st.text_input("brand_name 品牌名（必填）")
            target_user = st.text_input("target_user 目标人群（选填）")
            use_scene = st.text_input("use_scene 使用场景（选填）")
        with col2:
            core_selling_points = st.text_area("core_selling_points 核心卖点（必填，3~8条，每行一条）", height=130)
            claim_points = st.text_area("claim_points 可写功效依据（选填，每行一条）", height=90)
            package_notes = st.text_area("package_notes 包装可见重点（选填，每行一条）", height=90)
            forbidden_words = st.text_area("forbidden_words 禁用词（选填，每行一条）", value="\n".join(DEFAULT_FORBIDDEN_WORDS), height=90)
        extra_notes = st.text_area("extra_notes 补充要求（选填）", height=80)

        submitted = st.form_submit_button("生成结构化提示词包", use_container_width=True)
        clear = st.form_submit_button("清空结果")

    if clear:
        st.session_state.pop("result", None)
        st.rerun()

    if submitted:
        product = ProductInput(
            product_name=product_name,
            brand_name=brand_name,
            core_selling_points=split_lines(core_selling_points),
            target_user=target_user,
            use_scene=use_scene,
            claim_points=split_lines(claim_points),
            package_notes=split_lines(package_notes),
            forbidden_words=split_lines(forbidden_words),
            extra_notes=extra_notes,
            style_selection=selected_styles,
        )
        if not product.product_name or not product.brand_name or len(product.core_selling_points) < 1:
            st.error("请至少填写产品名称、品牌名和核心卖点。")
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
        c1.metric("组数", len(result.groups))
        c2.metric("图片提示词", len(result.groups) * 5)
        c3.metric("文章", len(result.groups))

        tabs = st.tabs(["Markdown 执行包", "JSON 备份", "逐组预览"])
        with tabs[0]:
            copy_button(result.markdown, "一键复制 Markdown")
            st.text_area("可直接复制给 ChatGPT", value=result.markdown, height=680)
            st.download_button("导出 Markdown", result.markdown.encode("utf-8"), file_name=st.session_state["md_path"].name, mime="text/markdown", use_container_width=True)
        with tabs[1]:
            copy_button(json_text, "一键复制 JSON")
            st.text_area("JSON", value=json_text, height=620)
            st.download_button("导出 JSON", json_text.encode("utf-8"), file_name=st.session_state["json_path"].name, mime="application/json", use_container_width=True)
        with tabs[2]:
            for group in result.groups:
                with st.expander(f"第{group.group_no}组｜{group.style_name}（{group.style_id}）", expanded=False):
                    st.write(group.style_summary)
                    st.write(group.difference_point)
                    st.markdown(f"**文章标题：** {group.article_title}")
                    st.write(group.article_body)
                    st.markdown("**备选标题：** " + " / ".join(group.alt_titles))
                    for image in group.images:
                        st.markdown(f"**图片{image.image_no}：{image.image_role}**")
                        st.write(image.chatgpt_image_prompt)


if __name__ == "__main__":
    main()
