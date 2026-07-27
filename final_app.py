from __future__ import annotations

import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps
import requests


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
HISTORY_PATH = BASE_DIR / "previous_groups.json"
for folder in (UPLOAD_DIR, OUTPUT_DIR):
    folder.mkdir(parents=True, exist_ok=True)

MAX_GROUPS = 10
FORBIDDEN = ["第一", "顶级", "最强", "100%", "TOP1", "绝对有效", "永久", "彻底", "无毒", "零伤害", "医学级", "医院级", "神仙产品", "神器", "闭眼入"]
PROMPT_GUARD = (
    "竖版4:5；真实消费者、真实家庭空间、自然肤质，不要网红脸、AI假脸、过度磨皮、僵硬广告姿势；"
    "不要价格角标、夸张促销字或传统电商海报排版；"
    "以上传产品图为唯一产品主体参考，严格保持包装、LOGO、品牌名、瓶型或盒型、主色、标签、"
    "规格、比例和可见文字一致，不要重绘或变形。"
    "明亮、通透、真实的生活场景，小红书/得物图文笔记风格，竖版单张独立图片，不要拼图，"
    "不要九宫格，不要多图合集。画面中必须有明显的大标题设计，标题要清楚、显眼、有设计感；"
    "可搭配1-2句辅助短句和少量关键词贴纸，整体像真实种草笔记，而不是电商详情页。"
    "人物自然真实，产品清晰可见，手机实拍感+轻电商精修，不要画面过暗，不要标题太小，"
    "不要文字过少，不要平台logo，不要水印，不要价格角标，不要改变产品包装，不要改变品牌logo，"
    "不要虚构不存在的功效。"
)


@dataclass
class Product:
    name: str
    brand: str
    category: str
    form: str
    spec: str
    selling_points: list[str]
    claims: list[str]
    extra: str
    image_names: list[str]
    report_name: str


@dataclass
class ImagePrompt:
    number: int
    title: str
    subtitle: str
    stickers: list[str]
    theme: str
    purpose: str
    prompt: str
    scene: str
    person: str
    action: str
    shot: str
    selling_point: str


@dataclass
class Group:
    group_no: int
    created_at: str
    theme: str
    direction_id: str
    direction: str
    audience: str
    core_expression: str
    article_angle: str
    competitor_analysis: dict[str, str]
    style_card: dict[str, str]
    titles: list[str]
    article: str
    tags: list[str]
    images: list[ImagePrompt]
    markdown: str


DIRECTIONS = [
    ("A", "真实用户体验记录型", "从连续的真实使用经历切入，强调生活动作与体感"),
    ("B", "达人分享测评型", "用选择标准、观察细节和适用人群做理性分享"),
    ("C", "家庭生活场景型", "从家庭高频使用与日常协作切入，克制表达安心感"),
    ("D", "高级生活方式型", "把产品放进明亮、有审美但真实可居住的生活片段"),
    ("E", "产品细节质感型", "从包装、形态、触感和使用细节建立选择理由"),
    ("F", "痛点解决故事型", "围绕一个具体困扰展开完整的发现、使用与反馈过程"),
    ("G", "使用前后变化型", "记录使用前后生活状态的变化，不夸大具体功效"),
    ("H", "空间美学融合型", "表现产品如何自然融入收纳和居住空间"),
    ("I", "成分/检测/信任背书型", "只引用用户提供或报告明确支持的信息"),
    ("J", "年轻人生活方式种草型", "从通勤、租房或周末生活节奏切入"),
]

STYLE_PRESETS = {
    "A": {"keywords": "真实、松弛、连续记录、轻分享", "tone": "奶油白与浅木色，白天明亮柔和", "person": "同一位普通年轻女性自然出镜，保留碎发和真实肤质", "copy": "第一人称生活记录，口语自然", "layout": "手账式大标题，左上与留白区轮换，统一圆角小标签", "lens": "手机35mm生活抓拍，中近景为主，轻微颗粒"},
    "B": {"keywords": "理性、清晰、可信、测评感", "tone": "清透白与低饱和蓝，整体高亮干净", "person": "同一位理性分享型年轻达人，半身或手部出镜", "copy": "观察式测评口吻，结论克制", "layout": "粗体无衬线大标题配细线标注，统一信息层级", "lens": "手机50mm平视与细节近景，画面稳定清楚"},
    "C": {"keywords": "温暖、家庭、日常、安心", "tone": "暖白、浅米与柔和浅橙，明亮不泛黄", "person": "同一位家庭用户，以背影、侧脸和手部连续出镜", "copy": "家庭日常叙事，温和但不做功效承诺", "layout": "暖色标题块与手写感短注释，版式统一留白", "lens": "自然平视中景，偶尔肩后视角，家庭纪实感"},
    "D": {"keywords": "通透、克制、高级、生活方式", "tone": "象牙白、浅灰与少量品牌色，明亮通透", "person": "同一位穿着简洁的年轻用户，局部或侧身出镜", "copy": "克制的生活方式表达，短句有呼吸感", "layout": "杂志感大标题与大留白，统一细字辅助线", "lens": "明亮窗边光，35mm环境人像与静物近景"},
    "E": {"keywords": "细节、材质、真实、精致", "tone": "高亮中性色与产品品牌色，细节清晰", "person": "统一以同一双自然手部出镜，人物不露脸", "copy": "从可见细节讲选择理由，避免空泛形容", "layout": "大标题与局部放大标注统一组合，不堆参数", "lens": "50mm与微距细节镜头，浅景深但产品文字清楚"},
    "F": {"keywords": "共鸣、过程、解决、真实故事", "tone": "明亮白、浅黄色点缀与自然生活色", "person": "同一位普通租房青年连续出镜，动作自然不看镜头", "copy": "痛点开场、过程展开、体验收尾的故事口吻", "layout": "醒目问题式大标题，统一黄色强调词与箭头元素", "lens": "第一人称和侧后方抓拍结合，保持同一手机镜头质感"},
    "G": {"keywords": "变化、过程、证据、克制", "tone": "清爽白与浅绿色，前后画面均保持明亮", "person": "同一位真实用户以手部和局部动作出镜", "copy": "记录状态变化，不夸大结果，不虚构数据", "layout": "统一时间标记与大标题，不使用拼图式前后对比", "lens": "固定35mm观察视角，用独立单图串联前后过程"},
    "H": {"keywords": "空间、收纳、秩序、治愈", "tone": "暖白、浅木与鼠尾草绿，明亮自然", "person": "统一无正脸，以同一人的手部或背影偶尔出现", "copy": "空间整理与生活秩序感表达", "layout": "标题沿空间留白放置，统一细框与小圆点装饰", "lens": "24-35mm环境广角，保持空间线条与自然透视"},
    "I": {"keywords": "可信、清晰、理性、依据充分", "tone": "亮白、浅蓝与少量品牌色，干净专业但不冰冷", "person": "同一位理性用户以手部和阅读资料的局部出镜", "copy": "只写已提供依据，区分事实与个人感受", "layout": "高可读大标题配极少量依据短句，统一卡片式信息区", "lens": "50mm平视、包装细节和资料局部，所有画面明亮清楚"},
    "J": {"keywords": "年轻、轻快、通勤、租房生活", "tone": "亮白、清新蓝紫与自然品牌色，轻快通透", "person": "同一位年轻通勤或租房用户自然连续出镜", "copy": "轻快口语和真实场景分享，不使用夸张网络词", "layout": "大字标题配贴纸感短标签，统一字体与色彩系统", "lens": "手机广角抓拍与第一人称视角，轻微运动感"},
}

PROFILES = {
    "laundry": {
        "category": "衣物洗护", "form": "洗衣/衣物护理产品",
        "scenes": ["洗衣机旁的洗护区", "有生活痕迹的阳台", "卧室衣柜前", "叠衣服的床边", "小户型洗衣角", "晾晒区", "通勤前的穿衣镜旁", "毛巾与床品收纳柜", "周末家务现场", "旅行酒店洗衣区"],
        "actions": ["拿取产品准备洗衣", "把产品放入洗衣流程", "整理刚洗好的衣物", "靠近衣物感受清爽气息", "补充洗护区收纳", "折叠毛巾和床品", "挑选次日通勤衣物", "记录一次周末洗衣", "给家人分类衣物", "装入旅行收纳袋"],
        "details": ["织物纹理、洗衣篮、少量未叠衣物", "洗衣机舱门反光、自然水汽", "衣架、柔软毛巾和窗边光", "衣柜木纹与整齐但不刻意的衣物", "阳台光影、晾晒夹和生活小物"],
        "users": "重视衣物状态、效率与居家体验的年轻用户、租房人群和家庭用户",
        "pain": "洗护步骤繁琐、衣物状态不理想、收纳占空间或日常使用不够顺手",
    },
    "bathroom": {
        "category": "浴室/洗护清洁", "form": "浴室使用产品",
        "scenes": ["真实浴室洗手台", "带水珠的镜前", "淋浴区收纳架", "瓷砖墙边", "浴室清洁后的通风时刻", "租房浴室角落", "毛巾架旁", "晨间洗漱现场", "夜间沐浴后的浴室", "周末浴室整理现场"],
        "actions": ["湿手拿取产品", "对着镜子自然使用", "整理浴室收纳架", "擦拭局部水渍", "观察泡沫或质地", "冲洗使用区域", "换上干净毛巾", "补充日常用品", "分享使用后的感受", "把产品放回顺手位置"],
        "details": ["镜面水汽、水珠、毛巾和牙刷杯", "自然泡沫、瓷砖纹理、玻璃反光", "湿发碎发、浴室顶灯和真实肤质", "收纳架、瓶罐生活痕迹", "通风后的柔和自然光"],
        "users": "注重浴室卫生、洗护体验与居家整洁的年轻用户和家庭用户",
        "pain": "浴室潮湿、清洁费力、洗护体验不够舒服或用品摆放杂乱",
    },
    "kitchen": {
        "category": "厨房清洁", "form": "厨房清洁产品",
        "scenes": ["真实家庭水槽边", "做饭后的灶台", "料理台一角", "餐具沥水区", "橱柜边的清洁收纳", "晚餐后的厨房", "租房小厨房", "早餐准备后的台面", "周末深度清洁现场", "厨房窗边"],
        "actions": ["戴家务手套拿取产品", "处理台面局部污渍", "清洗餐具后整理水槽", "擦拭灶台", "观察清洁后的表面", "把产品收入橱柜", "记录做饭后的清洁过程", "整理海绵和抹布", "处理常见卫生死角", "完成清洁后洗手"],
        "details": ["水槽水珠、海绵、抹布和餐具", "灶台使用痕迹、自然油光", "窗边光、料理台纹理", "橱柜木纹与日常器具", "家务手套和真实清洁动作"],
        "users": "经常做饭、在意清洁效率与厨房状态的租房人群和家庭用户",
        "pain": "饭后清洁麻烦、局部污渍影响观感、工具杂乱或清洁流程费力",
    },
    "fragrance": {
        "category": "家居香氛/生活方式", "form": "香氛或气味体验产品",
        "scenes": ["卧室床头柜", "真实衣帽间", "沙发边角几", "玄关换鞋处", "通勤前的梳妆台", "衣柜内部", "酒店旅行房间", "窗边阅读角", "刚整理好的床品旁", "夜晚暖灯下的卧室"],
        "actions": ["自然拿起产品闻香", "整理衣柜时使用", "放进通勤包", "更换床品后摆放产品", "坐在沙发边放松", "出门前整理穿搭", "打开旅行收纳袋", "把产品放回床头", "记录晚间居家片段", "与织物自然互动"],
        "details": ["织物褶皱、木质家具、柔和窗光", "衣柜衣物层次与自然阴影", "床品纹理、书和水杯", "暖灯、轻微颗粒感和生活痕迹", "通勤包、首饰盘和镜面反射"],
        "users": "重视气味、穿搭状态和居住氛围的年轻女性、通勤与精致生活人群",
        "pain": "空间或织物缺少舒服气息、生活状态不够松弛、随身气味管理不方便",
    },
    "portable": {
        "category": "便携日用/即时清洁", "form": "便携装日用产品",
        "scenes": ["通勤包内部", "办公室桌面", "玄关鞋柜旁", "咖啡店座位", "旅行酒店洗漱台", "车内储物格", "出门前的穿衣镜边", "高铁小桌板", "健身包旁", "周末外出收纳现场"],
        "actions": ["从包里自然取出产品", "处理临时小状况", "放回随身收纳袋", "出门前快速整理", "在桌面使用产品", "旅行途中补充使用", "整理车内常备用品", "展示便携尺寸", "分享一次救场经历", "检查使用后的状态"],
        "details": ["钥匙、耳机、纸巾和真实包内物品", "办公杯、键盘和自然桌面痕迹", "旅行分装袋和酒店灯光", "玄关鞋履与穿搭细节", "手机抓拍视角和轻微运动感"],
        "users": "通勤、旅行、学生与重视随身整洁的年轻用户",
        "pain": "外出遇到临时状况难处理、用品占空间、需要随手可用的解决方式",
    },
    "generic": {
        "category": "生活日用", "form": "日用产品",
        "scenes": ["真实客厅一角", "卧室收纳区", "窗边桌面", "玄关柜", "家庭日用品柜", "租房小空间", "周末整理现场", "通勤包旁", "自然光下的产品使用区", "夜间家居灯光场景"],
        "actions": ["自然拿取产品", "进行日常使用", "整理并收纳产品", "观察产品细节", "分享使用体验", "放入常备区", "记录一次生活片段", "展示使用方式", "对比使用前后的生活状态", "推荐给适合的人"],
        "details": ["木质桌面、织物和生活小物", "自然窗光与真实阴影", "收纳盒、纸巾和水杯", "轻微使用痕迹与真实材质", "手机拍摄颗粒和克制精修"],
        "users": "有日常使用需求并重视便利性与生活品质的消费者",
        "pain": "使用流程不顺手、收纳不便、缺少明确选择理由或体验记忆点",
    },
}

COMPETITOR_KNOWLEDGE = {
    "laundry": {
        "selling": ["使用步骤省事", "清洁与气味体验", "定量或取用方便", "多种衣物场景", "收纳与家庭常备"],
        "angles": ["懒人洗衣记录", "通勤衣物状态", "家庭高频洗护", "香气与穿着体验", "租房小空间收纳"],
        "pains": ["倒取或用量麻烦", "衣物气味影响穿着", "洗护用品占空间", "高频洗衣流程繁琐"],
        "copy": ["从一次真实洗衣过程开场", "用衣物状态代替夸张功效", "突出顺手、常备与使用频率"],
    },
    "bathroom": {
        "selling": ["日常清洁更省力", "泡沫或质地体验", "喷头与使用方式", "气味和浴室清爽感", "收纳不占空间"],
        "angles": ["洗澡后顺手清洁", "浴室湿闷痛点", "镜面与水渍日常", "租房浴室整理", "真实使用过程"],
        "pains": ["潮湿和异味困扰", "水渍污垢反复出现", "清洁过程费力", "用品杂乱难收纳"],
        "copy": ["用浴室现场建立代入感", "突出动作是否顺手", "以明亮清爽状态收尾"],
    },
    "kitchen": {
        "selling": ["油污清洁体验", "喷洒或擦拭顺手", "水槽灶台多场景", "气味接受度", "厨房常备便利"],
        "angles": ["做饭后的快速整理", "水槽边真实使用", "灶台局部处理", "租房厨房清洁", "家务效率记录"],
        "pains": ["饭后清洁拖延", "油污和水渍影响观感", "工具用品杂乱", "清洁气味影响体验"],
        "copy": ["从做饭后的真实现场切入", "记录动作和表面状态", "避免虚构前后效果数据"],
    },
    "fragrance": {
        "selling": ["香型与气味层次", "空间或织物适配", "留香体验", "包装与摆放美感", "随身或旅行使用"],
        "angles": ["卧室气味日记", "衣柜与织物香气", "通勤前状态感", "夜间居家氛围", "旅行收纳分享"],
        "pains": ["气味过浓或单调", "空间缺少舒适氛围", "织物气味影响状态", "香氛用品难融入家居"],
        "copy": ["用具体空间和情绪描述气味", "避免无依据留香时长", "强调靠近闻到的生活细节"],
    },
    "portable": {
        "selling": ["随身便携", "临时救场", "取用快速", "多种外出场景", "小体积好收纳"],
        "angles": ["通勤包里常备", "办公室临时使用", "旅行酒店场景", "出门前快速整理", "真实救场经历"],
        "pains": ["外出小状况难处理", "随身用品太占空间", "需要时找不到", "使用步骤复杂"],
        "copy": ["从突发小状况开场", "突出携带与拿取动作", "用真实场景替代夸张结果"],
    },
    "generic": {
        "selling": ["使用顺手", "真实场景适配", "收纳方便", "细节质感", "日常常备价值"],
        "angles": ["真实用户体验", "细节测评", "生活空间融合", "痛点解决过程", "年轻人日常"],
        "pains": ["使用流程不顺", "选择理由不清楚", "用品难融入空间", "容易买后闲置"],
        "copy": ["用具体生活动作表达", "突出可见细节", "明确适合人群和使用条件"],
    },
}

SEARCH_TERMS = ["便携", "清洁", "留香", "香味", "泡沫", "温和", "收纳", "去污", "水垢", "油污", "除味", "定量", "省事", "家庭", "租房", "通勤", "真实体验", "使用感", "不占空间", "多场景"]


def competitor_research(product: Product) -> dict[str, str]:
    key = profile_key(product)
    knowledge = COMPETITOR_KNOWLEDGE[key]
    query = f"{product.category} 产品 推荐 卖点 使用体验 种草"
    mode = "离线推断"
    source_count = 0
    frequent_terms: list[str] = []
    try:
        response = requests.get(
            "https://www.bing.com/search",
            params={"q": query, "format": "rss", "count": "10", "setlang": "zh-CN"},
            headers={"User-Agent": "Mozilla/5.0 (compatible; DewuContentResearch/5.0)"},
            timeout=8,
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        items = root.findall(".//item")[:10]
        texts = []
        for item in items:
            title = html.unescape(item.findtext("title") or "")
            description = html.unescape(item.findtext("description") or "")
            texts.append(re.sub(r"<[^>]+>", " ", f"{title} {description}"))
        source_count = len(texts)
        if source_count >= 5:
            mode = "联网公开搜索"
            corpus = " ".join(texts)
            ranked = sorted(((term, corpus.count(term)) for term in SEARCH_TERMS), key=lambda x: (-x[1], SEARCH_TERMS.index(x[0])))
            frequent_terms = [term for term, count in ranked if count > 0][:6]
    except Exception:
        source_count = 0
    status = (
        f"已联网搜索同品类公开内容，共采集{source_count}条结果并做共性归纳，不复制竞品原文。"
        if mode == "联网公开搜索"
        else "以下竞品卖点为基于行业经验的离线推断，不代表实时平台结果。"
    )
    online_hint = f"；公开结果较高频出现：{'、'.join(frequent_terms)}" if frequent_terms else ""
    product_opportunity = product.selling_points[0] if product.selling_points else "用真实连续场景与顺手体验建立区别"
    return {
        "mode": mode,
        "status": status,
        "query": query,
        "source_count": str(source_count),
        "mainstream": "、".join(knowledge["selling"]) + online_hint,
        "angles": "、".join(knowledge["angles"]),
        "pains": "、".join(knowledge["pains"]),
        "copy_direction": "；".join(knowledge["copy"]),
        "opportunity": f"围绕“{product_opportunity}”做产品专属表达，并避开同质化参数堆砌和夸张功效承诺。",
    }

SHOTS = ["手持近景", "侧后方抓拍中景", "桌面俯拍", "镜面反射构图", "环境广角", "产品微距特写", "肩后视角", "低机位生活抓拍", "半身自然近景", "第一人称视角"]
PERSONS = ["普通年轻女性局部出镜", "普通年轻男性局部出镜", "仅自然手部出镜", "无人物生活氛围", "家庭用户背影", "租房青年侧脸", "通勤用户半身", "只见肩部与手部", "真实用户镜前抓拍", "无人物产品融入空间"]
TIME_VARIANTS = ["清晨自然光下", "午后窗边光下", "傍晚家居灯刚亮时", "夜间暖灯下", "周末家务进行中", "工作日出门前", "使用后的安静片刻", "补充收纳的过程中"]
ACTION_VARIANTS = ["以随手抓拍状态", "以第一人称记录状态", "以侧后方观察状态", "以近距离生活记录状态", "以不看镜头的自然状态", "以轻微运动模糊的瞬间", "以动作刚开始的瞬间", "以动作完成后的放松状态"]
SHOT_VARIANTS = ["保留前景遮挡", "利用门框形成景深", "保留镜面自然反射", "带轻微手机颗粒", "用生活物件形成前后层次", "保留自然倾斜感", "留出环境呼吸空间", "强调真实材质与阴影"]


def split_text(value: str) -> list[str]:
    return [x.strip(" -•、") for x in re.split(r"[\n,，;；]+", value or "") if x.strip(" -•、")]


def clean(value: str) -> str:
    text = value
    for word in FORBIDDEN:
        text = text.replace(word, "")
    return re.sub(r"\s+", " ", text).strip()


def profile_key(product: Product) -> str:
    text = f"{product.name} {product.category} {' '.join(product.selling_points)}"
    if any(x in text for x in ["洗衣", "凝珠", "衣物", "留香珠", "柔顺"]):
        return "laundry"
    if any(x in text for x in ["浴室", "沐浴", "马桶", "除霉", "水垢", "洁厕", "洗手"]):
        return "bathroom"
    if any(x in text for x in ["厨房", "油污", "餐具", "水槽", "灶台"]):
        return "kitchen"
    if any(x in text for x in ["香氛", "香薰", "留香", "除味", "香衣片"]):
        return "fragrance"
    if any(x in text for x in ["便携", "湿巾", "擦鞋", "随身", "旅行"]):
        return "portable"
    return "generic"


def product_id(product: Product, image_bytes: list[bytes]) -> str:
    base = f"v5|{product.brand}|{product.name}|{product.spec}".encode()
    return hashlib.sha256(base + b"".join(image_bytes)).hexdigest()[:16]


def load_history() -> dict[str, list[dict]]:
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_history(history: dict[str, list[dict]]) -> None:
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def save_upload(file) -> bytes:
    data = file.getvalue()
    suffix = Path(file.name).suffix.lower()
    (UPLOAD_DIR / f"{hashlib.sha256(data).hexdigest()[:12]}{suffix}").write_bytes(data)
    return data


def infer_product(product: Product) -> Product:
    profile = PROFILES[profile_key(product)]
    product.category = product.category or profile["category"]
    product.form = product.form or profile["form"]
    product.name = product.name or (Path(product.image_names[0]).stem if product.image_names else "待识别产品")
    product.brand = product.brand or "品牌待确认"
    return product


def selling_point_pool(product: Product) -> list[str]:
    base = [
        *product.selling_points, "使用过程更顺手", "能自然融入真实生活场景", "包装与收纳更适合日常",
        "体验表达克制但有记忆点", "适合高频使用或常备", "细节质感带来明确选择理由", *product.claims,
    ]
    return list(dict.fromkeys(clean(x) for x in base if clean(x)))


def choose_direction(product: Product, used: set[str], group_no: int) -> tuple[str, str, str]:
    candidates = DIRECTIONS.copy()
    if product.claims:
        candidates = [x for x in candidates if x[0] == "J"] + [x for x in candidates if x[0] != "J"]
    seed = int(hashlib.sha256(f"{product.name}{product.brand}".encode()).hexdigest()[:8], 16)
    offset = (seed + group_no * 3) % len(candidates)
    ordered = candidates[offset:] + candidates[:offset]
    return next((x for x in ordered if x[0] not in used), ordered[0])


def image_count(product: Product) -> int:
    richness = len(product.selling_points) + len(product.claims) + (2 if product.report_name else 0)
    return 8 if richness >= 7 else 7 if richness >= 4 else 6 if richness >= 2 else 5


def pick_unused(options: list[str], used: set[str], index: int) -> str:
    rotated = options[index % len(options):] + options[:index % len(options)]
    return next((x for x in rotated if x not in used), rotated[0])


def make_article(product: Product, profile: dict, direction: tuple[str, str, str], point: str, group_no: int) -> tuple[list[str], str, list[str]]:
    scene = profile["scenes"][(group_no * 2) % len(profile["scenes"])]
    detail = profile["details"][group_no % len(profile["details"])]
    titles = [
        clean(f"最近在{scene}经常用到的{product.name}"),
        clean(f"把{product.name}放进日常后，最有感的是这些细节"),
        clean(f"不夸张安利，聊聊{product.name}的真实使用感"),
    ]
    claim_sentence = f"资料明确支持“{product.claims[0]}”，这里不额外延伸功效。" if product.claims else ""
    article = clean(
        f"最近因为{profile['pain']}，开始认真留意{product.category}。我把{product.name}放在{scene}使用，"
        f"这次更想从“{direction[1]}”的角度聊聊。它给我的直观感受不是需要专门学习的工具，而是能顺着原来的生活动作自然用起来。"
        f"实际用的时候，我通常会先把需要处理的东西整理好，再顺手拿它完成对应步骤。整个过程没有刻意摆拍的感觉，"
        f"{detail}这些真实细节反而更能说明它在日常里的位置。我比较喜欢的一点是{point}。"
        f"{('规格是' + product.spec + '，') if product.spec else ''}放在常用区域不会显得突兀，拿取和收纳也比较顺手。{claim_sentence}"
        f"当然，它不是靠一句夸张口号就能说明白的产品。对我来说，更重要的是实际场景匹不匹配、操作是否顺手、"
        f"包装信息是否清楚，以及用完之后愿不愿意继续把它留在常备区。这些细节比生硬的参数堆砌更有参考价值。"
        f"如果你也是{profile['users']}，又在意使用过程是否省心、产品能不能融入自己的空间，"
        f"可以把它放进备选清单，再结合自己的使用频率、实际需求和包装说明判断，不必只看宣传语。"
    )
    tags = [product.brand, product.name, product.category, "得物好物分享", "真实使用感", "生活好物", "居家日常", "使用体验"]
    return titles, article, [re.sub(r"\s+", "", x) for x in tags if x not in ["品牌待确认", "待识别产品"]][:10]


def headline_for(direction_id: str, index: int, point: str) -> str:
    banks = {
        "A": ["最近真的常用它", "顺手这件事很重要", "我的日常使用记录", "细节比口号更真实", "慢慢成了常备款", "放进生活刚刚好", "用过才懂的顺手感", "这次认真聊聊它"],
        "B": ["我会重点看这几点", "真实测评不说空话", "细节决定使用感", "适合谁一次说清", "我的选择理由", "用法和体验都看了", "买前可以先看这里", "理性分享这次体验"],
        "C": ["家里常用更要顺手", "日常的小事也重要", "一家人的生活细节", "放在常用区很合适", "家务也可以轻松点", "每天用才更有感", "家庭常备看这些", "温柔融入日常"],
        "D": ["生活质感藏在细节", "明亮日常里的好物", "克制但很有存在感", "放进空间刚刚好", "舒服生活不必用力", "喜欢这种清透感", "日常也可以有审美", "简单一点反而耐看"],
        "E": ["近看更懂它的细节", "包装和使用都看清", "真实材质很加分", "手里拿着更直观", "这些细节值得看", "质感不是靠滤镜", "把使用细节放大", "选择理由藏在这里"],
        "F": ["这个困扰我太懂了", "终于少折腾一点", "从麻烦到顺手", "我的真实解决过程", "日常痛点这样处理", "这次确实轻松些", "不用再手忙脚乱", "一个细节改变流程"],
        "G": ["先记录使用前状态", "过程比结果更真实", "使用中的自然变化", "完成后的生活状态", "不夸张只做记录", "连续使用更有参考", "前后感受慢慢看", "这次变化说清楚"],
        "H": ["收纳顺了生活也顺", "产品自然融进空间", "这个角落舒服多了", "明亮空间里的常备", "秩序感来自小细节", "放对位置真的重要", "空间留白刚刚好", "日常收纳也很治愈"],
        "I": ["依据清楚才更安心", "只说资料支持的点", "包装信息认真看", "理性选择不夸张", "事实和感受分开说", "看懂再决定更稳妥", "信任来自清楚表达", "这次把依据讲明白"],
        "J": ["年轻人的顺手日常", "租房生活也要舒服", "通勤前顺手用一下", "小空间里的实用派", "周末生活轻松一点", "日常好物不必夸张", "放进包里也不占地", "轻快生活从细节开始"],
    }
    title = banks[direction_id][index % len(banks[direction_id])]
    return clean(title if title else point[:14])


def subtitle_for(point: str, scene: str, index: int) -> str:
    templates = [
        f"在{scene.split('，')[0]}真实用一次，重点看看{point}",
        "从拿取到使用都按日常节奏记录，感受更直观",
        "不堆参数，只分享这个场景里真正有感的细节",
        "产品放进真实生活里，顺不顺手一眼就能看懂",
        "保留生活痕迹，也把包装和使用动作拍清楚",
        "同一次使用连续记录，画面和感受都不跳戏",
        "适合在意日常体验的人，先看场景是否匹配",
        "用克制的真实分享，讲清楚为什么愿意常备",
    ]
    return clean(templates[index % len(templates)])


def sticker_words(point: str, index: int) -> list[str]:
    fixed = ["真实使用中", "近期使用记录", "生活感分享", "顺手体验", "细节加分", "明亮日常", "我的使用笔记", "场景实测"]
    keyword = clean(point).replace("，", "")[:8]
    return list(dict.fromkeys([fixed[index % len(fixed)], keyword]))[:2]


def make_group(product: Product, prior: list[dict], research: dict[str, str] | None = None) -> Group:
    group_no = len(prior) + 1
    profile = PROFILES[profile_key(product)]
    used_directions = {x.get("direction_id", "") for x in prior}
    used_scenes = {v for x in prior for v in x.get("scenes", [])}
    used_persons = {v for x in prior for v in x.get("persons", [])}
    used_actions = {v for x in prior for v in x.get("actions", [])}
    used_shots = {v for x in prior for v in x.get("shots", [])}
    used_points = {v for x in prior for v in x.get("selling_points", [])}
    direction = choose_direction(product, used_directions, group_no)
    preset = STYLE_PRESETS[direction[0]]
    competitor = research or competitor_research(product)
    points = selling_point_pool(product)
    main_point = next((x for x in points if x not in used_points), points[group_no % len(points)])
    scene_start = (group_no * 3) % len(profile["scenes"])
    scene_range = [profile["scenes"][(scene_start + offset) % len(profile["scenes"])] for offset in range(3)]
    theme = clean(f"{direction[1]}｜{product.name}在{scene_range[0]}的连续真实体验")
    style_card = {
        "theme": theme,
        "direction": direction[1],
        "core_expression": f"{direction[2]}，主讲“{main_point}”",
        "keywords": preset["keywords"],
        "tone": preset["tone"],
        "scene_range": "、".join(scene_range),
        "person_rule": preset["person"],
        "copy_tone": preset["copy"],
        "layout": preset["layout"],
        "lens": preset["lens"],
    }
    titles, article, tags = make_article(product, profile, direction, main_point, group_no)
    prompts: list[ImagePrompt] = []
    purposes = ["建立真实分享信任", "呈现具体生活痛点", "记录自然使用动作", "放大产品细节质感", "展示空间融合感", "表达使用后的生活状态", "提供理性选择理由", "形成克制的收尾推荐"]
    scene_options = [f"{scene}，{moment}" for scene in scene_range for moment in TIME_VARIANTS[:3]]
    action_options = [f"{action}，{variant}" for action in profile["actions"] for variant in ACTION_VARIANTS]
    shot_options = [f"{preset['lens']}；{variant}" for variant in SHOT_VARIANTS]
    person_rule = preset["person"]
    for i in range(image_count(product)):
        scene = pick_unused(scene_options, used_scenes | {x.scene for x in prompts}, group_no * 7 + i)
        action = pick_unused(action_options, used_actions | {x.action for x in prompts}, group_no * 9 + i)
        shot = pick_unused(shot_options, used_shots | {x.shot for x in prompts}, group_no * 11 + i)
        person = person_rule
        point = next((x for x in points if x not in used_points and x not in {p.selling_point for p in prompts}), main_point)
        detail = profile["details"][(group_no + i) % len(profile["details"])]
        image_title = headline_for(direction[0], i, point)
        subtitle = subtitle_for(point, scene, i)
        stickers = sticker_words(point, i)
        title_position = ["左上留白区", "右上留白区", "画面中部自然留白", "下方三分之一留白区"][i % 4]
        prompt = clean(
            f"生成{product.brand} {product.name}同一组系列笔记中的第{i + 1}张图片。本组统一视觉设定："
            f"{preset['keywords']}；主色调与明暗为{preset['tone']}；人物规则为{person_rule}；"
            f"统一文案调性为{preset['copy']}；统一排版语言为{preset['layout']}；统一镜头语言为{preset['lens']}。"
            f"本图主题是“{direction[1]}中的{point}”。"
            f"画面主体为{person}，正在{action}；产品以自然手持、正在使用或顺手摆放的方式清晰出现，不能悬浮。"
            f"场景设在{scene}，保留{detail}，像真实有人居住和使用的家庭空间，整洁但不做样板间。"
            f"必须使用白天自然光、窗边柔光或明亮干净的室内光，画面高亮通透，人物、产品、背景和标题都清楚，"
            f"禁止偏黑、偏灰、脏黄或低照度。采用{shot}，延续同一位达人、同一次策划、同一本笔记的系列感。"
            f"画面必须加入醒目主标题“{image_title}”，放在{title_position}，使用本组统一字体、字号体系和色彩，"
            f"标题足够大、清晰可读并参与构图；加入清楚可读的辅助短句“{subtitle}”，字号小于主标题但不能像备注；"
            f"再加入1-2个轻量贴纸短文案“{' / '.join(stickers)}”，用于突出重点词。"
            f"主标题、辅助短句、关键词贴纸形成清楚的三级信息层次，文字比纯摄影图更丰富，但禁止密密麻麻。"
            f"重点表达“{point}”，不添加未经提供的数据。"
            f"{('用户补充要求：' + product.extra + '。') if product.extra else ''}"
            f"{PROMPT_GUARD}"
        )
        prompts.append(ImagePrompt(i + 1, image_title, subtitle, stickers, f"{point}｜{scene}", purposes[i], prompt, scene, person, action, shot, point))
    group = Group(
        group_no, datetime.now().isoformat(timespec="seconds"), theme, direction[0], direction[1], profile["users"],
        style_card["core_expression"], direction[2], competitor, style_card, titles, article, tags, prompts, ""
    )
    group.markdown = render_markdown(group, product, profile, points)
    return group


def render_markdown(group: Group, product: Product, profile: dict, points: list[str]) -> str:
    card = group.style_card
    competitor = group.competitor_analysis
    diff_point = product.selling_points[0] if product.selling_points else points[0]
    product_keywords = "明亮、真实、生活感、清晰、易融入场景"
    lines = [
        "====================", f"【第{group.group_no}组内容方案】", "====================", "",
        "【产品识别】",
        f"- 产品名称：{product.name}",
        f"- 品牌：{product.brand}",
        f"- 品类：{product.category}",
        f"- 产品形态：{product.form}",
        f"- 主要使用场景：{'、'.join(profile['scenes'][:4])}",
        f"- 目标用户：{profile['users']}",
        f"- 产品气质关键词：{product_keywords}",
        f"- 建议出现的真实生活空间：{'、'.join(profile['scenes'][:5])}",
        f"- 核心卖点：{'、'.join(points[:4])}",
        f"- 差异化卖点：{diff_point}",
        f"- 用户痛点：{profile['pain']}",
        f"- 用户购买理由：场景匹配、使用顺手、可见细节清楚，并能自然融入高频生活。",
        "",
        "【竞品卖点分析】",
        f"- 研究状态：{competitor['status']}",
        f"- 竞品主流卖点总结：{competitor['mainstream']}",
        f"- 高频内容角度：{competitor['angles']}",
        f"- 用户常见痛点：{competitor['pains']}",
        f"- 可借鉴的文案表达方向：{competitor['copy_direction']}",
        f"- 本产品可切入的差异化机会：{competitor['opportunity']}", "",
        "【本组风格设定卡】",
        f"- 本组主题：{card['theme']}",
        f"- 本组内容方向：{card['direction']}",
        f"- 本组核心表达：{card['core_expression']}",
        f"- 本组风格关键词：{card['keywords']}",
        f"- 本组主色调 / 明暗倾向：{card['tone']}",
        f"- 本组场景范围：{card['scene_range']}",
        f"- 本组人物出镜规则：{card['person_rule']}",
        f"- 本组文案调性：{card['copy_tone']}",
        f"- 本组排版特点：{card['layout']}",
        f"- 本组镜头感觉：{card['lens']}", "",
        "====================", "【种草文章】", "====================", "",
        f"标题1：{group.titles[0]}", f"标题2：{group.titles[1]}", f"标题3：{group.titles[2]}", "",
        f"正文：\n\n{group.article}", "", f"标签：{' '.join('#' + x for x in group.tags)}", "",
        "====================", "【图片方案】", "====================", "",
    ]
    for image in group.images:
        lines.extend([
            f"图{image.number}：", f"图片主题：{image.theme}", f"图片作用：{image.purpose}",
            f"主标题文案：{image.title}", f"辅助短句文案：{image.subtitle}",
            f"关键词/贴纸短文案：{' / '.join(image.stickers)}",
            f"图片提示词：\n\n{image.prompt}", "",
        ])
    return "\n".join(lines)


def hydrate_group(data: dict) -> Group:
    values = dict(data)
    images = []
    for item in values.get("images", []):
        if not isinstance(item, dict):
            images.append(item)
            continue
        row = dict(item)
        row.setdefault("title", row.get("theme", "真实使用记录")[:14])
        row.setdefault("subtitle", "真实场景里的自然使用记录")
        row.setdefault("stickers", ["真实使用中"])
        images.append(ImagePrompt(**row))
    values["images"] = images
    values.setdefault("style_card", {
        "theme": values.get("theme", ""), "direction": values.get("direction", ""),
        "core_expression": values.get("core_expression", ""), "keywords": "真实、明亮、生活感",
        "tone": "明亮通透", "scene_range": "", "person_rule": "真实用户自然出镜",
        "copy_tone": "自然分享", "layout": "大标题图文设计", "lens": "手机生活抓拍",
    })
    values.setdefault("competitor_analysis", {
        "mode": "离线推断",
        "status": "以下竞品卖点为基于行业经验的离线推断，不代表实时平台结果。",
        "query": "", "source_count": "0", "mainstream": "日常使用、场景适配、收纳便利",
        "angles": "真实体验、场景记录、细节分享", "pains": "流程不顺、选择困难",
        "copy_direction": "从真实动作与使用细节切入", "opportunity": "突出产品专属场景与用户提供卖点",
    })
    return Group(**values)


def copy_button(text: str, label: str) -> None:
    components.html(
        f"""<button id="copy" style="border:0;border-radius:10px;background:#111827;color:#fff;padding:10px 16px;font-weight:700;cursor:pointer">{label}</button>
        <span id="msg" style="margin-left:10px;color:#64748b"></span>
        <script>const t={json.dumps(text)};document.getElementById("copy").onclick=async()=>{{try{{await navigator.clipboard.writeText(t);document.getElementById("msg").innerText="已复制"}}catch(e){{document.getElementById("msg").innerText="请手动复制"}}}}</script>""",
        height=48,
    )


def persist_group(key: str, group: Group, history: dict[str, list[dict]]) -> None:
    record = {
        "group_no": group.group_no, "created_at": group.created_at, "theme": group.theme,
        "direction_id": group.direction_id, "direction": group.direction, "article_angle": group.article_angle,
        "scenes": [x.scene for x in group.images], "persons": [x.person for x in group.images],
        "actions": [x.action for x in group.images], "shots": [x.shot for x in group.images],
        "selling_points": [x.selling_point for x in group.images],
        "color_tone": group.style_card["tone"], "layout": group.style_card["layout"],
        "copy_tone": group.style_card["copy_tone"], "image_structure": group.style_card["lens"],
        "group": asdict(group),
    }
    history.setdefault(key, []).append(record)
    save_history(history)
    (OUTPUT_DIR / f"{key}_group_{group.group_no}.md").write_text(group.markdown, encoding="utf-8")


def main() -> None:
    st.set_page_config(page_title="得物 / 小红书种草图文生成器 V5", page_icon="🟣", layout="wide")
    st.markdown(
        """<style>.block-container{max-width:1180px;padding-top:2rem}.stTextInput input,.stTextArea textarea{border-radius:10px}
        .hero{padding:22px;border:1px solid #e5e7eb;border-radius:16px;background:linear-gradient(135deg,#faf5ff,#fff)}</style>""",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="hero"><h1>得物 / 小红书种草图文生成器 V5</h1><p>先搜竞品卖点｜单组输出｜文章 + 5–8张独立单图提示词｜强化小红书文案设计</p></div>', unsafe_allow_html=True)
    st.write("")
    with st.sidebar:
        st.header("产品资料")
        image_files = st.file_uploader("产品图片", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
        report = st.file_uploader("检测报告（可选）", type=["pdf", "jpg", "jpeg", "png"])
        style_refs = st.file_uploader("风格参考图（可选）", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
        if image_files:
            for file in image_files:
                try:
                    st.image(ImageOps.exif_transpose(Image.open(file)), caption=file.name, use_container_width=True)
                except Exception:
                    st.caption(file.name)
        st.info("检测报告不会自动变成功效结论，请填写确认可用的支持点。风格参考图会随产品保存；如需精确提取某项风格，请在补充要求中说明。")
    with st.form("product_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("产品名称（可选，建议填写)")
            brand = st.text_input("品牌名称（可选，建议填写)")
            category = st.text_input("产品品类（可选）")
            form = st.text_input("产品形态（可选）")
            spec = st.text_input("产品规格（可选）")
        with c2:
            selling = st.text_area("产品卖点（可选，每行一条）", height=120)
            claims = st.text_area("检测报告/包装明确支持点（可选，每行一条）", height=120)
            extra = st.text_area("补充要求 / 参考图风格说明（可选）", height=80)
        submit = st.form_submit_button("生成本产品第1组 / 查看当前进度", use_container_width=True)
    if submit:
        product = infer_product(Product(
            name, brand, category, form, spec, split_text(selling), split_text(claims), extra,
            [f.name for f in image_files] if image_files else [], report.name if report else "",
        ))
        image_bytes = [save_upload(f) for f in image_files or []]
        if report:
            save_upload(report)
        for reference in style_refs or []:
            image_bytes.append(save_upload(reference))
        key = product_id(product, image_bytes)
        st.session_state["product"] = product
        st.session_state["product_key"] = key
        history = load_history()
        prior = history.get(key, [])
        if not prior:
            with st.spinner("正在联网搜索同品类公开卖点并生成第1组内容…"):
                research = competitor_research(product)
                group = make_group(product, prior, research)
            persist_group(key, group, history)
        else:
            group = hydrate_group(prior[-1]["group"])
            research = group.competitor_analysis
        st.session_state["research"] = research
        st.session_state["current_group"] = group
    product = st.session_state.get("product")
    key = st.session_state.get("product_key")
    current = st.session_state.get("current_group")
    if product and key and current:
        history = load_history()
        prior = history.get(key, [])
        st.divider()
        a, b, c = st.columns([1, 1, 2])
        a.metric("已生成", f"{len(prior)} / {MAX_GROUPS} 组")
        b.metric("本组图片", f"{len(current.images)} 张")
        c.progress(len(prior) / MAX_GROUPS, text="同一产品差异化内容进度")
        st.subheader("产品分析")
        profile = PROFILES[profile_key(product)]
        points = selling_point_pool(product)
        st.markdown(
            f"- 产品名称：{product.name}\n- 品牌：{product.brand}\n- 品类：{product.category}\n- 产品形态：{product.form}\n"
            f"- 主要使用场景：{'、'.join(profile['scenes'][:4])}\n- 目标消费者：{profile['users']}\n"
            f"- 产品气质：明亮、真实、生活感、清晰、易融入场景\n"
            f"- 核心卖点：{'、'.join(points[:4])}\n- 差异化卖点：{product.selling_points[0] if product.selling_points else points[0]}\n"
            f"- 用户痛点：{profile['pain']}\n- 内容机会：用连续生活叙事、明显大标题和统一视觉体系表达，避免重复海报模板。"
        )
        with st.expander("查看竞品卖点研究", expanded=True):
            research = current.competitor_analysis
            st.caption(research["status"])
            st.markdown(
                f"- 竞品主流卖点：{research['mainstream']}\n- 高频内容角度：{research['angles']}\n"
                f"- 用户常见痛点：{research['pains']}\n- 文案表达方向：{research['copy_direction']}\n"
                f"- 本产品差异化机会：{research['opportunity']}"
            )
        with st.expander("查看本组风格设定卡", expanded=True):
            card = current.style_card
            st.markdown(
                f"- 主题：{card['theme']}\n- 内容方向：{card['direction']}\n- 核心表达：{card['core_expression']}\n"
                f"- 风格关键词：{card['keywords']}\n- 主色调 / 明暗：{card['tone']}\n- 场景范围：{card['scene_range']}\n"
                f"- 人物规则：{card['person_rule']}\n- 文案调性：{card['copy_tone']}\n- 排版：{card['layout']}\n- 镜头：{card['lens']}"
            )
        b1, b2, b3 = st.columns(3)
        if b1.button("生成下一组", type="primary", use_container_width=True, disabled=len(prior) >= MAX_GROUPS):
            group = make_group(product, prior, st.session_state.get("research") or current.competitor_analysis)
            persist_group(key, group, history)
            st.session_state["current_group"] = group
            st.rerun()
        if b2.button("查看上一组", use_container_width=True, disabled=current.group_no <= 1):
            st.session_state["current_group"] = hydrate_group(prior[current.group_no - 2]["group"])
            st.rerun()
        if b3.button("清空此产品历史", use_container_width=True):
            history.pop(key, None)
            save_history(history)
            st.session_state.pop("current_group", None)
            st.rerun()
        st.subheader(f"第{current.group_no}组｜{current.direction}")
        copy_button(current.markdown, "一键复制本组全部内容")
        st.text_area("完整输出", current.markdown, height=760)
        st.download_button(
            "下载本组 Markdown", current.markdown.encode("utf-8"),
            file_name=f"dewu_{key}_group_{current.group_no}.md", mime="text/markdown", use_container_width=True,
        )
        if len(prior) >= MAX_GROUPS:
            st.success("本产品10组差异化内容已全部生成。")
