from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
HISTORY_PATH = BASE_DIR / "previous_groups.json"
for folder in (UPLOAD_DIR, OUTPUT_DIR):
    folder.mkdir(parents=True, exist_ok=True)

MAX_GROUPS = 10
FORBIDDEN = ["第一", "顶级", "最强", "100%", "永久", "彻底", "无毒", "零伤害", "医学级", "医院级", "神仙产品", "闭眼入"]
PROMPT_GUARD = (
    "竖版4:5，单张独立出图，不要拼图、九宫格、长图或合集；真实消费者、真实家庭空间、"
    "手机实拍感加轻度精修，自然肤质，不要网红脸、AI假脸、过度磨皮、僵硬广告姿势；"
    "不要平台Logo、水印、价格角标、夸张促销字或传统电商海报排版；"
    "以上传产品图为唯一产品主体参考，严格保持包装、LOGO、品牌名、瓶型或盒型、主色、标签、"
    "规格、比例和可见文字一致，不要重绘、变形或虚构不存在的功效。"
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
    titles: list[str]
    article: str
    tags: list[str]
    images: list[ImagePrompt]
    markdown: str


DIRECTIONS = [
    ("A", "真实用户生活分享型", "从一次自然使用经历切入，强调顺手和日常融入"),
    ("B", "痛点解决型", "从具体生活困扰切入，用克制的体验表达解决过程"),
    ("C", "高级生活方式型", "把产品放进有审美但真实可居住的生活片段"),
    ("D", "产品细节质感型", "从包装、形态、触感和使用细节建立选择理由"),
    ("E", "场景沉浸体验型", "围绕一个完整使用时段展开，突出环境和感受"),
    ("F", "家庭安心使用型", "从家庭高频使用与谨慎选择切入，不虚构安全功效"),
    ("G", "达人测评分享型", "用选择标准、观察细节和适用人群做理性分享"),
    ("H", "真实使用过程记录型", "按使用前、使用中、使用后的生活动作展开"),
    ("I", "空间美学融合型", "表现产品如何自然融入收纳和居住空间"),
    ("J", "成分/技术/检测信任型", "只引用用户提供或检测报告明确支持的信息"),
]

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
    base = f"{product.brand}|{product.name}|{product.spec}".encode()
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
        f"{detail}这些真实细节放在一起，使用时不会有很强的广告感。我比较喜欢的一点是{point}。"
        f"{('规格是' + product.spec + '，') if product.spec else ''}对日常收纳和拿取也比较友好。{claim_sentence}"
        f"如果你也是{profile['users']}，又在意使用过程是否省心、产品能不能融入自己的空间，"
        f"可以把它放进备选清单，再结合自己的需求和包装说明判断。"
    )
    tags = [product.brand, product.name, product.category, "得物好物分享", "真实使用感", "生活好物", "居家日常", "使用体验"]
    return titles, article, [re.sub(r"\s+", "", x) for x in tags if x not in ["品牌待确认", "待识别产品"]][:10]


def make_group(product: Product, prior: list[dict]) -> Group:
    group_no = len(prior) + 1
    profile = PROFILES[profile_key(product)]
    used_directions = {x.get("direction_id", "") for x in prior}
    used_scenes = {v for x in prior for v in x.get("scenes", [])}
    used_persons = {v for x in prior for v in x.get("persons", [])}
    used_actions = {v for x in prior for v in x.get("actions", [])}
    used_shots = {v for x in prior for v in x.get("shots", [])}
    used_points = {v for x in prior for v in x.get("selling_points", [])}
    direction = choose_direction(product, used_directions, group_no)
    points = selling_point_pool(product)
    main_point = next((x for x in points if x not in used_points), points[group_no % len(points)])
    theme = clean(f"{direction[1]}｜{product.name}在{profile['scenes'][(group_no * 2) % len(profile['scenes'])]}的真实体验")
    titles, article, tags = make_article(product, profile, direction, main_point, group_no)
    prompts: list[ImagePrompt] = []
    purposes = ["建立真实分享信任", "呈现具体生活痛点", "记录自然使用动作", "放大产品细节质感", "展示空间融合感", "表达使用后的生活状态", "提供理性选择理由", "形成克制的收尾推荐"]
    scene_options = [f"{scene}，{moment}" for scene in profile["scenes"] for moment in TIME_VARIANTS]
    action_options = [f"{action}，{variant}" for action in profile["actions"] for variant in ACTION_VARIANTS]
    shot_options = [f"{shot}，{variant}" for shot in SHOTS for variant in SHOT_VARIANTS]
    person_options = [f"{person}，{variant}" for person in PERSONS for variant in ACTION_VARIANTS]
    for i in range(image_count(product)):
        scene = pick_unused(scene_options, used_scenes | {x.scene for x in prompts}, group_no * 7 + i)
        action = pick_unused(action_options, used_actions | {x.action for x in prompts}, group_no * 9 + i)
        shot = pick_unused(shot_options, used_shots | {x.shot for x in prompts}, group_no * 11 + i)
        person = pick_unused(person_options, used_persons | {x.person for x in prompts}, group_no * 13 + i)
        point = next((x for x in points if x not in used_points and x not in {p.selling_point for p in prompts}), main_point)
        detail = profile["details"][(group_no + i) % len(profile["details"])]
        prompt = clean(
            f"生成一张{product.brand} {product.name}的得物种草内容图片。本图主题是“{direction[1]}中的{point}”。"
            f"画面主体为{person}，正在{action}；产品以自然手持、正在使用或顺手摆放的方式清晰出现，不能悬浮。"
            f"场景设在{scene}，保留{detail}，像真实有人居住和使用的家庭空间，整洁但不做样板间。"
            f"使用自然窗光、柔和室内环境光或符合场景的家居灯光，保留自然阴影、轻微反光和真实材质。"
            f"采用{shot}，形成生活博主随手记录的抓拍感，产品清楚但不压过生活状态。"
            f"重点表达“{point}”；如需图中文字，只允许一行克制短标题，不添加未经提供的数据。{PROMPT_GUARD}"
        )
        prompts.append(ImagePrompt(i + 1, f"{point}｜{scene}", purposes[i], prompt, scene, person, action, shot, point))
    group = Group(
        group_no, datetime.now().isoformat(timespec="seconds"), theme, direction[0], direction[1], profile["users"],
        f"用{direction[2]}，主讲“{main_point}”", direction[2], titles, article, tags, prompts, ""
    )
    group.markdown = render_markdown(group)
    return group


def render_markdown(group: Group) -> str:
    lines = [
        "====================", "", f"【第{group.group_no}组内容方案】", "", f"主题：{group.theme}", "",
        f"内容方向：{group.direction}", "", f"适合用户：{group.audience}", "", f"核心表达：{group.core_expression}", "",
        "====================", "", "【得物文章】", "", f"标题1：{group.titles[0]}", "", f"标题2：{group.titles[1]}", "",
        f"标题3：{group.titles[2]}", "", f"正文：\n\n{group.article}", "", f"标签：{' '.join('#' + x for x in group.tags)}", "",
        "====================", "", "【图片提示词】", "",
    ]
    for image in group.images:
        lines.extend([f"图{image.number}：", "", f"主题：{image.theme}", "", f"图片目的：{image.purpose}", "", f"生图提示词：\n\n{image.prompt}", ""])
    lines.append("====================")
    return "\n".join(lines)


def hydrate_group(data: dict) -> Group:
    values = dict(data)
    values["images"] = [ImagePrompt(**x) if isinstance(x, dict) else x for x in values.get("images", [])]
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
        "selling_points": [x.selling_point for x in group.images], "group": asdict(group),
    }
    history.setdefault(key, []).append(record)
    save_history(history)
    (OUTPUT_DIR / f"{key}_group_{group.group_no}.md").write_text(group.markdown, encoding="utf-8")


def main() -> None:
    st.set_page_config(page_title="得物种草内容生成器", page_icon="🟣", layout="wide")
    st.markdown(
        """<style>.block-container{max-width:1180px;padding-top:2rem}.stTextInput input,.stTextArea textarea{border-radius:10px}
        .hero{padding:22px;border:1px solid #e5e7eb;border-radius:16px;background:linear-gradient(135deg,#faf5ff,#fff)}</style>""",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="hero"><h1>得物种草内容生成器</h1><p>一次生成1组，连续生成最多10组差异化图文内容。每组包含1篇文章与5–8张独立生图提示词。</p></div>', unsafe_allow_html=True)
    st.write("")
    with st.sidebar:
        st.header("产品资料")
        image_files = st.file_uploader("产品图片", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
        report = st.file_uploader("检测报告（可选）", type=["pdf", "jpg", "jpeg", "png"])
        if image_files:
            for file in image_files:
                try:
                    st.image(ImageOps.exif_transpose(Image.open(file)), caption=file.name, use_container_width=True)
                except Exception:
                    st.caption(file.name)
        st.info("检测报告不会自动变成功效结论。请在右侧“报告支持点”填写确认可用的内容。")
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
            extra = st.text_area("补充要求（可选）", height=80)
        submit = st.form_submit_button("生成本产品第1组 / 查看当前进度", use_container_width=True)
    if submit:
        product = infer_product(Product(
            name, brand, category, form, spec, split_text(selling), split_text(claims), extra,
            [f.name for f in image_files] if image_files else [], report.name if report else "",
        ))
        image_bytes = [save_upload(f) for f in image_files or []]
        if report:
            save_upload(report)
        key = product_id(product, image_bytes)
        st.session_state["product"] = product
        st.session_state["product_key"] = key
        history = load_history()
        prior = history.get(key, [])
        if not prior:
            group = make_group(product, prior)
            persist_group(key, group, history)
        else:
            group = hydrate_group(prior[-1]["group"])
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
            f"- 核心卖点：{'、'.join(points[:4])}\n- 用户痛点：{profile['pain']}\n"
            f"- 内容机会：用真实生活动作、不同空间和不同镜头表达，避免重复海报模板。"
        )
        b1, b2, b3 = st.columns(3)
        if b1.button("生成下一组", type="primary", use_container_width=True, disabled=len(prior) >= MAX_GROUPS):
            group = make_group(product, prior)
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
