# -*- coding: utf-8 -*-
import os
import sys
import json
import shutil
import tkinter as tk
import base64
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import subprocess
import time
import requests
import uuid
import glob
import re
import traceback
from collections import deque, Counter
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os, sys, json, requests, time, threading, traceback
try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None

# --- Global Constants Shadowing ---
OLLAMA_BASE_URL = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
MODEL_LIBRARY_URL = 'https://ollama.com/library'

# --- Cross-Module Symbol Injection ---
try: from mbk_tool.ollama_utils import * 
except: pass
try: from mbk_tool.main import * 
except: pass

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    import openai
except ImportError:
    messagebox.showerror('Error', "The 'openai' library is not installed. Please run: pip install openai")
    sys.exit(1)

MODEL_LIBRARY_URL = 'https://ollama.com/library'

OLLAMA_BASE_URL = 'http://localhost:11434'

SOP_PROMPT_PREFIX = '\n您是一位顶级的提示词（Prompt）优化大师。当您接收到用户的请求时，必须严格遵循以下SOP（标准作业程序）三步流程来思考和创作，确保输出结果的专业性和稳定性：\n\n**第一步：确立【风格和主体】**\n*   您必须首先从用户提供的风格和创意描述中，精准地提炼出核心的“艺术风格”和“核心主体”。这是整个创作的基石。\n\n**第二步：进行【创意润色】**\n*   以第一步确立的风格和主体为基础，对用户的原始创意进行专业的文学性润色和想象力扩展。\n*   目标是生成一段内容更丰富、细节更饱满、画面感更强的详细中文描述，为下一步的结构化做好准备。\n\n**第三步：应用【分类指令】进行调整和补充**\n*   使用第二步生成的“润色版描述”作为核心素材。\n*   严格对照当前任务的“专业分类指令”，逐项检查、调整和补充，确保最终的提示词在结构上完整、在内容上不缺失、在逻辑上不冲突。\n\n**最终输出：**\n*   您必须将严格遵循以上三步流程后得到的、高质量的、结构化的中文提示词，以稳定、纯净的JSON格式返回。\n\n---\n现在，请根据以下具体的【专业的分类指令】来执行任务：\n'

SYSTEM_PROMPTS = {'文生图': SOP_PROMPT_PREFIX + '\n**Task Type: Text-to-Image (Stable Diffusion)**\n**Core Requirement:** For the text-to-image task, strictly generate according to the following format:\n\n**Text-to-Image Specific Structure:**\n1. Quality Control: masterpiece, best quality, ultra-detailed, 8k resolution, photorealistic\n2. Subject Description: emotion, action, gesture, subject details, character features, expressions, poses\n3. Composition Elements: composition, camera angle, perspective, framing\n4. Environment & Scene: background, setting, atmosphere, props\n5. Lighting Effects: lighting setup, shadows, highlights, mood lighting\n6. Material & Texture: surface textures, materials, fabric details\n7. Detail Enhancement: intricate details, sharp focus, depth of field\n\n**Weighting System:**\n- Core Elements: (keyword:1.15-1.25)\n- Important Elements: (keyword:1.05-1.15)\n- Normal Elements: keyword\n- De-emphasized Elements: (keyword:0.8-0.9)\n\n', '文生图-FLUX': SOP_PROMPT_PREFIX + "\n**Task Type: Text-to-Image (FLUX Model)**\n**Core Requirement:** The FLUX model prefers more natural, descriptive language rather than traditional keyword stacking. Convert the user's creative idea into a high-quality text-to-image prompt suitable for the FLUX model.\n\n**FLUX Prompt Core Principles:**\n1.  **Natural Language First**: Use complete, descriptive sentences to build the scene.\n2.  **Brevity and Core Focus**: Capture the core creative idea, avoiding excessive trivial details and weight modifiers.\n3.  **Quality Tags**: Add common high-quality tags at the beginning or end of the sentence.\n4.  **Clear Style Definition**: Clearly describe the desired art style, medium, or artist.\n\n**text-to-Video (flux) Weights:**\n\n1.  Subject Emphasis: To ensure the main subject is the focus.\n    -   Example: A cinematic film still of a (knight in shining armor:1.1-1.2) standing on a cliff.\n2.  Style & Artist Strength: To increase the intensity of a specific style.\n    -   Example: A portrait of a woman, (in the style of Van Gogh:1.15-1.25).\n3.  Composition & Camera Control: To give priority to a specific shot type.\n    -   Example: A futuristic city, (dramatic low-angle shot:1.05-1.15), towering skyscrapers.\n4.  Atmosphere & Lighting: To emphasize a particular mood or light effect.\n    -   Example: A mysterious forest at night, (eerie volumetric lighting:1.1-1.2) filtering through the\n  trees.\n\n", '中文润色': '您是一位专业的中文创意大师。您的任务是根据用户的请求，进行润色、扩展和优化，生成一段充满想象力、细节丰富、文采飞扬的创意描述。您的最终输出必须严格遵循以下格式：以 `[START_TEXT]` 作为开头，紧接着是完整的纯中文创意描述文本，最后以 `[END_TEXT]` 作为结尾。在这两个标记之间，绝对禁止包含任何额外的标题、解释或标记。', 'Chinese Segmentation': '您是一位精通AI提示词，可以精确区分提示词内容的专家。您将收到一个JSON对象，其中包含一个\'creative_text\'（源文本）块和一个\'target_segments\'（目标分段）数组。\n\n数组中的每一项代表一个最终的提示词分段，它是一个JSON对象，包含一个唯一的\'display_name\'（显示名称）和一组\'keywords\'（关键词）。这组关键词**通常包含两个元素**：一个“性质词”（定义提示词的生成方式）和一个“功能词”（定义提示词的描述主题）,这些词语决定了该段提示词的内容构成。\n\n**您的核心任务是**：\n1.  **分配正面内容**：根据每个分段的“功能词”定义，将\'creative_text\'的**全部文本内容**，按逻辑关联性，**完整且无遗漏地**拆分并分配到所有`"keywords": ["positive", ...]`的段落中。\n2.  **生成负面内容**：对于每一个`"keywords": ["negative", ...]`的段落，您必须基于其**同名“功能词”**的描述内容，生成对应的负面描述。\n\n---\n\n### 定义与规则\n\n#### 性质词 (Property Words)\n\n*   **性质词: `positive`**\n    *   所有内容都必须是关于“希望看到什么”的正面描述。这是您根据功能词从\'creative_text\'中直接提取和整理的内容。\n*   **性质词: `negative`**\n    *   所有内容都必须是关于“需要避免什么”的负面描述。这部分内容是根据对应的`positive`内容**生成**的，而不是提取的。\n    *   **生成步骤**:\n        1.  **基础内容**: 针对其对应正面内容中的形容词，生成反义词（例如：`美丽` -> `丑陋`）。\n        2.  **补充内容**: 对照其对应正面内容中的具体事物或情景，生成反面或无关的描述（例如：`精致的奖杯` -> `变形的手`，`宏伟的宫殿` -> `现代建筑`）。\n\n#### 功能词 (Function Words) 详细定义\n\n##### 1. 场景与构图 (Scene & Composition)\n\n*   **关键词**: `base` (主要), `main` (别名)\n*   **核心目标**: 描述画面的基础结构，包括整体环境、主体和辅助元素的相关信息。\n*   **具体定义**:\n    *   **场景环境 (Scene Setting)**: 描述故事发生的基础背景，例如“在森林深处”、“一个赛博朋克城市的街角”、“空旷的白色房间”。\n    *   **主体与元素 (Subjects & Elements)**: 定义画面中包含哪些核心主体或物体，例如“一个女孩和一只白狼”、“一艘巨大的宇宙飞船”。\n    *   **构图与布局 (Composition & Layout)**: 描述主体与背景、主体与主体之间的空间关系和位置。使用专业的构图词汇，例如“女孩位于画面中央”、“白狼在她身后”、“采用对称构图”、“远景是连绵的雪山”。\n*   **示例**: “一个男人站在山顶，背对观众，采用中心构图，远景是日落和云海。”\n\n##### 2. 艺术风格与氛围 (Art Style & Atmosphere)\n\n*   **关键词**: `refine`\n*   **核心目标**: 描述画面的整体艺术风格、光影、色调和情感氛围。\n*   **具体定义**:\n    *   **光影与色彩 (Lighting & Color)**: 描述光源方向、光线质感和整体色调。例如“柔和的午后阳光”、“霓虹灯光照亮”、“电影感色调”、“伦勃朗式用光”、“高对比度黑白照片”。\n    *   **艺术风格 (Art Style)**: 指定一个明确的艺术流派、艺术家风格或媒介。例如“梵高风格”、“印象派”、“日本浮世绘”、“虚幻引擎渲染”、“水彩画”、“3D辛烷值渲染”。\n    *   **氛围与意境 (Mood & Atmosphere)**: 描述画面希望传达的情感或感觉。例如“神秘的”、“宁静的”、“充满未来科技感”、“忧郁的氛围”。\n*   **示例**: “电影感光效，柔和的边缘光，整体为冷色调，营造出一种宁静而孤寂的氛围，水彩画风格。”\n\n##### 3. 细节与叙事 (Details & Narrative)\n\n*   **关键词**: `details` (主要), `inpaint` / `fix` (特定流程别名)\n*   **核心目标**: 专注于刻画画面中的高优先级区域，添加具体细节、定义互动和情节。\n*   **具体定义**:\n    *   **重点区域刻画 (Key Area Focus)**: 对指定的角色或物体进行精细描述。例如“主角的眼睛是蓝色的，眼神坚定”、“机器人手臂上有复杂的机械刻线”。\n    *   **互动与情节 (Interaction & Plot)**: 描述角色之间、角色与物体之间的互动或正在发生的事件。例如“女孩轻轻抚摸着白狼的头”、“男人正在修理一个复杂的装置”。\n    *   **关联物细节 (Associated Details)**: 补充与主体相关的环境或背景细节，以增强故事感。例如“桌子上放着一杯冒着热气的咖啡和一本翻开的书”。\n*   **示例**: “男人穿着一件磨损的皮夹克，夹克上有徽章；他正在操作一个全息屏幕，屏幕上显示着复杂的代码。”\n\n##### 4. 人物形态 (Human Form)\n\n*   **关键词**: `person`\n*   **核心目标**: 精确描述画面中主要人物的姿态、动作和穿着。\n*   **具体定义**:\n    *   **姿态与动作 (Pose & Action)**: 使用明确的词汇描述身体的姿势和动态。例如“全身像，正面站立”、“坐姿，双腿交叉”、“正在奔跑，身体前倾”、“从后面看，弯腰拾取东西”。\n    *   **服装描述 (Apparel Description)**: 详细描述人物的穿着。例如“穿着一件白色的连衣裙”、“戴着一顶黑色的礼帽”、“身穿未来派风格的盔甲”。\n    *   **身体朝向 (Body Orientation)**: 明确人物相对于镜头的方向。例如“侧脸”、“面朝镜头”、“背对观众”。\n*   **示例**: “一个女人，全身像，穿着哥特式长裙，坐在王座上，双手交叠放在膝上，正面视角。”\n\n##### 5. 精准解剖结构 (Precise Anatomy)\n\n*   **关键词**: `face` / `hand` / `foot`\n*   **核心目标**: 描述人类最容易出错的特定身体部位，施加严格的解剖学和形态学约束。\n*   **具体定义**:\n    *   **解剖学准确性 (Anatomical Accuracy)**: 强制要求生成的结构符合真实的人体解剖学。例如“一只完整的手，包含五根手指”、“对称、结构正确的脸部特征”。\n    *   **形态与线条 (Form & Lines)**: 要求轮廓清晰，形态精准，无扭曲或模糊。例如“清晰的手指线条”、“精致的脸部轮廓”、“脚的结构正确”。\n    *   **光影一致性 (Lighting Consistency)**: 确保该部位的光影表现与 `refine` 中定义的整体光源保持一致。\n*   **示例**:\n    *   `face`: “一张完美对称的脸，五官精致，皮肤质感细腻，符合解剖学结构。”\n    *   `hand`: “一只形态优美的手，五指分明，线条清晰，没有畸变。”\n\n\n**输出格式:**\n您的最终输出必须是一个严格的JSON对象，其键名必须严格匹配`target_segments` 数组中提供的`display_name`。内容完全使用中文，被包裹在`[START_JSON]`和`[END_JSON]`标记之间，并且不包含任何额外的解释或标记。\n\n  例如，如果输入是:\n```json\n{\n  "creative_text": "一个美丽的公主走在城堡的花园里，阳光明媚，但远处的龙看起来有点模糊和变形。",\n  "target_segments": [\n    {\n      "display_name": "Positive Prompt (Base)",\n      "keywords": ["positive", "base"]\n    },\n    {\n      "display_name": "Negative Prompt",\n      "keywords": ["negative"]\n    }\n  ]\n}\n```\n\n  您的输出必须是:\n```json\n{\n  "Positive Prompt (Base)": "一个美丽的公主走在城堡的花园里，阳光明媚。",\n  "Negative Prompt": "远处的龙看起来有点模糊和变形。"\n}\n```\n', 'English Translation': 'You are an expert translator specializing in AI art prompts.\n\nYou will receive a JSON object containing:\n1) `prompt_groups`: grouped segments by full node name.  \n   - each group includes `full_name` and `segments`\n   - each segment includes `display_name`, `keywords`, `type` (`positive` or `negative`), and `text`\n2) `flat_prompts`: a flat map where keys are unique `display_name` and values are Chinese prompt text\n\nCore rules:\n1. Translate each segment accurately and fluently into English.\n2. Keep semantic correspondence strictly inside each group and each segment.\n3. Do not mix content across `display_name`s, even when multiple positive/negative segments exist.\n4. Preserve all entities, attributes, actions, style details, and constraints. No omissions.\n\nOutput rules:\n1. Output a strict JSON object enclosed by `[START_JSON]` and `[END_JSON]`.\n2. Keys in output must exactly match every key in input `flat_prompts`.\n3. Values must be purely English translations for the corresponding segment.\n4. No extra explanation.\n\nExample input:\n```json\n{\n  "prompt_groups": [\n    {\n      "full_name": "Base Prompt",\n      "segments": [\n        {\n          "display_name": "Positive Prompt (Base)",\n          "keywords": ["positive", "base"],\n          "type": "positive",\n          "text": "一个美丽的女孩，动漫风格"\n        },\n        {\n          "display_name": "Negative Prompt (Base)",\n          "keywords": ["negative", "base"],\n          "type": "negative",\n          "text": "丑陋，模糊"\n        }\n      ]\n    }\n  ],\n  "flat_prompts": {\n    "Positive Prompt (Base)": "一个美丽的女孩，动漫风格",\n    "Negative Prompt (Base)": "丑陋，模糊"\n  }\n}\n```\n\nExample output:\n```json\n{\n  "Positive Prompt (Base)": "a beautiful girl, anime style",\n  "Negative Prompt (Base)": "ugly, blurry"\n}\n```', 'Supplement Instructions': 'You are a standardization expert specializing in professional AI art prompts. You will receive a JSON object of `english_prompts` and a string of `professional_instructions`.Each “professional_instructions” document contains metric entries and weight parameters.\n \nYour task is: to add semantically relevant metric entries and weight parameters to every \nreceived prompt segment. Follow these rules precisely for each segment:\n\n\n1.  **Add Quality‑Control Entry**: First, analyze the `professional_instructions` text. If you locate any metric entry whose name contains the word “quality,” prepend the full content of that entry to the beginning of every `positive` prompt segment. Do not duplicate descriptions.\n\n2. **Finding Indicator Keywords**: Analyze the keywords in a segment’s `display_name` (e.g., “base”, “face”) and the character states and object relationships described in the `english_prompts` text. From the `professional_instructions`, select entries that have a strong semantic correlation with the (keywords, states, relationships). For each selected entry, pick one word from its content,these words are the indicator keywords, making sure no duplicate words are added.\n\n\n3. **Applying Weight Parameters**: Analyze the meaning of each weight name, tag the selected indicator keywords with the appropriate weights, and then insert those weighted keywords between the `positive` prompt text and the quality‑control content of the corresponding paragraph. Duplicate usage of the same keyword within a paragraph of the same name is prohibited.\n\n4.  **Output Format**: Your final output must be a strict JSON object. Its keys must exactly match the input `display_name`s. The values must be entirely in English. The entire object must be enclosed between `[START_JSON]` and `[END_JSON]` markers, with no extra explanations.\n\nFor example, if the input is `{"Positive Prompt (Base)": "a girl", "Negative Prompt (Base)": "ugly"}`,\nyour output must be:\n```json\n{"Positive Prompt (Base)": "(masterpiece, best quality, ultra-detailed, 8k resolution) (cinematic lighting (base:1.2)) a girl ",\n"Negative Prompt (Base)": "(worst quality, low quality, blurry) ugly"}\n```'}

MODEL_PARAMS_CONFIG = {'qw3.5': {'num_ctx': 16384, 'temperature': 0.7}, 'qwen3.5': {'num_ctx': 16384, 'temperature': 0.7}, 'qw3.5:cloud': {'num_ctx': 32768}, 'qwen3.5:397b-cloud': {'num_ctx': 32768}, 'mistral-large-3:675b-cloud': {'num_ctx': 32768}, 'qwen3-vl:235b-cloud': {'num_ctx': 32768}, 'qwen3-next:80b-a3b-instruct-q8_0': {'num_ctx': 16384}, 'qwen3.5:122b-a10b': {'num_ctx': 16384}, 'nemotron-3-super:120b': {'num_ctx': 16384}, 'gpt-oss:120b': {'num_ctx': 24576}, 'qwen3.5:27b-bf16': {'num_ctx': 16384}, 'ernie-4.5-37b-a3b-thinking-brainstorm20x.q8-0': {'num_ctx': 16384}, 'gemma4:31b-it-bf16': {'num_ctx': 16384}, 'ernie-4.5-37b-a3b-thinking-brainstorm20x.q8-0:latest': {'num_ctx': 16384}, 'glm-5.1:cloud': {'num_ctx': 32768}, 'kimi-k2.5:cloud': {'num_ctx': 32768}, 'gemini-3-flash-preview': {'num_ctx': 32768}}

WORKFLOWS = {'文生图片': {'type': '文生图', 'positive_node_title': 'Positive Prompt', 'negative_node_title': 'Negative Prompt'}, '文生图-FLUX': {'type': '文生图-FLUX', 'positive_node_title': 'Positive Prompt (FLUX Base)', 'negative_node_title': 'Negative Prompt (FLUX Base)'}}

PROFESSIONAL_STYLES = ['默认风格 (Default Style)', '电影感 (Cinematic)', '照片写实 (Photorealistic)', '概念艺术 (Concept Art)', '数字绘画 (Digital Painting)', '幻想艺术 (Fantasy Art)', '科幻风格 (Science Fiction)', '赛博朋克 (Cyberpunk)', '蒸汽朋克 (Steampunk)', '复古风格 (Retro Style)', '极简主义 (Minimalism)', '哥特风格 (Gothic)', '抽象艺术 (Abstract)', '超现实主义 (Surrealism)', '印象派 (Impressionism)', '波普艺术 (Pop Art)', '装饰风艺术 (Art Deco)', '新艺术运动 (Art Nouveau)', '巴洛克风格 (Baroque)', '未来主义 (Futurism)', '立体主义 (Cubism)', '古典主义 (Classicism)', '文艺复兴 (Renaissance)', '动漫风格 (Anime Style)', '漫画风格 (Comic Book Style)', '卡通风格 (Cartoon Style)', '水墨画 (Ink Wash Painting)', '水彩画 (Watercolor)', '素描 (Sketch)', '插画 (Illustration)', '人像摄影 (Portrait Photography)', '风光摄影 (Landscape Photography)', '微距摄影 (Macro Photography)', '长曝光 (Long Exposure)', '双重曝光 (Double Exposure)', '黄金时刻 (Golden Hour)', '蓝调时刻 (Blue Hour)', '航拍摄影 (Aerial Photography)', '单色摄影 (Monochrome)', '虚幻引擎 (Unreal Engine)', '辛烷值渲染 (Octane Render)', '光线追踪 (Ray Tracing)', '卡通渲染 (Cel Shading)', '低多边形 (Low Poly)', '体素艺术 (Voxel Art)', '等距视角 (Isometric)', '3D模型 (3D Model)']

def get_model_params(model_name):
    """根据模型名称获取推荐的上下文参数，适配 Ollama 20.4+ 交互算法
    
    注意: 移除 num_predict 避免限制或强制模型生成长度，让模型自然停止。
    """
    if not model_name:
        return {'num_ctx': 16384}
    model_lower = model_name.lower()
    for key in ['qw3.5', 'qwen3.5']:
        if key in model_lower:
            return MODEL_PARAMS_CONFIG[key]
    if model_name in MODEL_PARAMS_CONFIG:
        return MODEL_PARAMS_CONFIG[model_name]
    for (config_name, params) in MODEL_PARAMS_CONFIG.items():
        if model_name.startswith(config_name.replace(':latest', '')) or config_name.startswith(model_name.split(':')[0]):
            return params
    if any((x in model_lower for x in [':cloud', '-cloud', 'api-', 'claude-'])):
        return {'num_ctx': 32768}
    if 'gpt-' in model_lower and 'oss' not in model_lower:
        return {'num_ctx': 16384}
    if any((x in model_lower for x in ['120b', '122b'])):
        return {'num_ctx': 16384}
    if any((x in model_lower for x in ['235b', '397b', '675b', '80b', '400b'])):
        return {'num_ctx': 16384}
    if any((x in model_lower for x in ['27b', '31b', '37b', '70b', '72b'])):
        return {'num_ctx': 16384}
    if any((x in model_lower for x in ['7b', '8b', '13b', '14b', '32b'])):
        return {'num_ctx': 16384}
    return {'num_ctx': 16384}

class OllamaManager:

    def __init__(self):
        self.process = None
        self.is_running = False
        self.base_url = OLLAMA_BASE_URL
        self.session = self._build_session()

    def _build_session(self):
        """构建带重试能力的HTTP会话，提高本地服务短暂抖动时的稳定性。"""
        session = requests.Session()
        retry = Retry(total=2, connect=2, read=2, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(['GET', 'POST']))
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _request(self, method, path, timeout=5, **kwargs):
        """统一HTTP请求入口，避免散落的URL与异常处理。"""
        url = f'{self.base_url}{path}'
        return self.session.request(method, url, timeout=timeout, **kwargs)

    def start_ollama(self):
        """启动OLLAMA服务，增加对 Mac 环境的路径探测"""
        try:
            response = self._request('GET', '/api/tags', timeout=2)
            if response.status_code == 200:
                self.is_running = True
                return True
        except:
            pass
        try:
            cmd = ['ollama', 'serve']
            if sys.platform == 'darwin':
                paths_to_check = ['/usr/local/bin/ollama', '/opt/homebrew/bin/ollama', 'ollama']
                for p in paths_to_check:
                    try:
                        subprocess.run([p, '--version'], capture_output=True, timeout=3)
                        cmd[0] = p
                        break
                    except:
                        continue
            if os.name == 'nt':
                self.process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(10):
                time.sleep(1.2)
                try:
                    response = self._request('GET', '/api/tags', timeout=3)
                    if response.status_code == 200:
                        self.is_running = True
                        return True
                except Exception:
                    continue
        except Exception as e:
            print(f'启动OLLAMA失败: {e}')
            return False
        return False

    def stop_ollama(self):
        """停止OLLAMA服务"""
        if self.process:
            self.process.terminate()
            self.process = None
        self.is_running = False

    def get_available_models(self):
        """获取可用模型列表"""
        try:
            response = self._request('GET', '/api/tags', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
        except:
            pass
        return []

    def get_running_models(self):
        """获取当前正在运行的模型"""
        try:
            response = self._request('GET', '/api/ps', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
        except:
            pass
        return []

    def pull_model(self, model_name, callback=None):
        """拉取模型"""
        try:
            response = self._request('POST', '/api/pull', json={'name': model_name}, stream=True, timeout=(10, 1800))
            for line in response.iter_lines():
                if line and callback:
                    try:
                        data = json.loads(line)
                        callback(data)
                    except:
                        pass
            return True
        except Exception as e:
            print(f'拉取模型失败: {e}')
            return False

    def search_online_models(self, keyword=''):
        """从ollama.ai/library搜索模型"""
        try:
            import re
            response = self.session.get(MODEL_LIBRARY_URL, timeout=10)
            if response.status_code == 200:
                model_names = re.findall('href="/library/([^"\\\\]+)"\\s*class="[^\\"]*font-medium"', response.text)
                model_names = [name for name in model_names if '/' not in name]
                if keyword:
                    return [name for name in model_names if keyword.lower() in name.lower()]
                return model_names
        except Exception as e:
            print(f'搜索在线模型失败: {e}')
        return []

class PromptApp:

    def __init__(self, root):
        self.root = root
        self.root.title('MBK-ComfyUI 智能提示词全自动化多媒体创作系统_开源版本')
        self.root.geometry('1200x900')
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)
        self.ollama_manager = OllamaManager()
        self.client = None
        self.workflow_files = {}
        self.proj_path = tk.StringVar(value=os.path.join(os.getcwd(), 'WORKFLOWS'))
        self.selected_model_var = tk.StringVar(value='未选择')
        self.selected_model_for_conversion = tk.StringVar(value='')
        self.running_models_cache = []
        self.current_workflow_type = ''
        self.prompt_text_widgets = {}
        self.negative_prompt_text_widgets = {}
        self.workflow_analysis_cache = {}
        self.image_path_var = tk.StringVar()
        self.positive_tab_full_name_var = tk.StringVar()
        self.negative_tab_full_name_var = tk.StringVar()
        self.creative_chinese_text = ''
        self.creative_chinese_generated = False
        self.chinese_segmented = False
        self.english_translated = False
        self.english_supplemented = False
        self.setup_ui()
        try:
            self._init_watermark()
            self._ensure_watermark_integrity()
        except Exception:
            pass
        self.initial_ollama_check()

    def initial_ollama_check(self):
        """程序启动时检查OLLAMA状态"""
        threading.Thread(target=self.refresh_ollama_status, daemon=True).start()

    def _create_openai_client(self):
        """统一创建OpenAI兼容客户端，集中管理超时与重试行为。"""
        return openai.OpenAI(api_key='dummy', base_url=f'{OLLAMA_BASE_URL}/v1', timeout=240, max_retries=2)

    def _is_cloud_model(self, model_name):
        if not model_name:
            return False
        model_lower = model_name.lower()
        return any((tag in model_lower for tag in [':cloud', '-cloud', 'api-', 'claude-', 'gemini-']))

    def _get_request_profile(self, model_name):
        """
        针对本地大模型与云端模型给出差异化超时与重试配置。
        重点提高 qwen3.5 / gemma4 与 cloud 的容错性。
        """
        model_lower = (model_name or '').lower()
        if self._is_cloud_model(model_name):
            return {'timeout': 420, 'retries': 4}
        if any((tag in model_lower for tag in ['qwen3.5', 'qw3.5', 'gemma4', '31b', '70b', '72b', '120b', '122b'])):
            return {'timeout': 300, 'retries': 3}
        return {'timeout': 180, 'retries': 2}

    def _build_extra_body(self, model_name):
        """构建 Ollama 额外参数，移除 num_predict 并保持模型热加载。"""
        params = get_model_params(model_name)
        num_ctx = params.get('num_ctx', 16384)
        extra_body = {'options': {'num_ctx': num_ctx}}
        if not self._is_cloud_model(model_name):
            extra_body['keep_alive'] = '30m'
        return extra_body

    def _chat_completion_with_retry(self, model_name, messages, temperature=0.7, json_mode=False, max_tokens=None):
        """统一的对话调用层：重试、超时、JSON模式降级策略。
        
        适配 Ollama 20.4+ 的 reasoning_content (CoT) 支持。
        """
        if not self.client:
            raise RuntimeError('OLLAMA客户端未初始化')
        profile = self._get_request_profile(model_name)
        is_reasoning_model = any((x in model_name.lower() for x in ['gemma', 'qw', 'gpt-oss', 'reasoning', 'thought', 'r1']))
        extra_body = self._build_extra_body(model_name)
        if is_reasoning_model:
            extra_body['think'] = True
        request_kwargs = {'messages': messages, 'model': model_name, 'temperature': temperature, 'extra_body': extra_body, 'timeout': profile['timeout']}
        if max_tokens is not None:
            request_kwargs['max_tokens'] = max_tokens
        if json_mode:
            if not is_reasoning_model:
                request_kwargs['stop'] = ['[END_JSON]']
        elif not is_reasoning_model:
            request_kwargs['stop'] = ['[END_TEXT]']
        last_error = None
        for attempt in range(profile['retries']):
            try:
                completion = self.client.chat.completions.create(**request_kwargs)
                msg = completion.choices[0].message
                if not msg.content:
                    reasoning = getattr(msg, 'reasoning_content', None) or getattr(msg, 'thought', None)
                    if reasoning:
                        msg.content = reasoning
                return completion
            except Exception as e:
                last_error = e
                err_text = str(e).lower()
                if attempt < profile['retries'] - 1:
                    time.sleep(min(1.5 * (attempt + 1), 4.0))
                else:
                    break
        raise last_error

    def setup_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        style = ttk.Style(self.root)
        style.configure('Execute.TButton', foreground='white', background='#c00000', font=('微软雅黑', 12, 'bold'))
        style.map('Execute.TButton', background=[('active', '#e00000'), ('disabled', '#a0a0a0')], foreground=[('disabled', 'darkgrey')])
        style.configure('Run.TButton', foreground='white', background='#0055ff', font=('微软雅黑', 10, 'bold'))
        style.map('Run.TButton', background=[('active', '#0077ff'), ('disabled', '#a0a0a0')], foreground=[('disabled', 'darkgrey')])
        style = ttk.Style(self.root)
        style.configure('Yellow.Horizontal.TProgressbar', background='gold')
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text='主控制台')
        setup_frame = ttk.Frame(notebook)
        notebook.add(setup_frame, text='OLLAMA设置')
        self.setup_main_tab(main_frame)
        self.setup_ollama_tab(setup_frame)

    def setup_main_tab(self, parent):
        proj_frame = ttk.LabelFrame(parent, text='1. 工作流路径设置', padding='10')
        proj_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(proj_frame, text='工作流路径:').pack(side='left')
        proj_entry = ttk.Entry(proj_frame, textvariable=self.proj_path, width=40)
        proj_entry.pack(side='left', padx=5)
        ttk.Button(proj_frame, text='浏 览', command=self.browse_proj_path, width=4).pack(side='left', padx=4)
        workflow_frame = ttk.LabelFrame(parent, text='2. 工作流选择', padding='10')
        workflow_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(workflow_frame, text='工作流分类:').grid(row=0, column=0, sticky='w')
        self.workflow_type_var = tk.StringVar()
        self.workflow_type_combo = ttk.Combobox(workflow_frame, textvariable=self.workflow_type_var, state='readonly', width=20)
        self.workflow_type_combo.grid(row=0, column=1, sticky='w', padx=5)
        self.workflow_type_combo.bind('<<ComboboxSelected>>', self.on_workflow_type_change)
        ttk.Label(workflow_frame, text='具体工作流:').grid(row=0, column=2, sticky='w', padx=(20, 5))
        self.specific_workflow_var = tk.StringVar()
        self.specific_workflow_combo = ttk.Combobox(workflow_frame, textvariable=self.specific_workflow_var, state='readonly', width=30)
        self.specific_workflow_combo.grid(row=0, column=3, sticky='w', padx=5)
        self.specific_workflow_combo.bind('<<ComboboxSelected>>', self.on_specific_workflow_change)
        workflow_frame.columnconfigure(4, weight=1)
        button_frame = ttk.Frame(workflow_frame)
        button_frame.grid(row=0, column=4, sticky='ew', padx=10)
        ttk.Button(button_frame, text='识别工作流', command=self.recognize_workflows_in_folder).pack(side='left')
        self.exit_button = ttk.Button(button_frame, text='退 出', command=self.on_closing)
        self.exit_button.pack(side='right', padx=(5, 0), ipady=12)
        self.run_comfyui_button = ttk.Button(button_frame, text='运 行', command=self.run_comfyui_workflow, state='disabled')
        self.run_comfyui_button.pack(side='right', padx=(10, 0), ipady=12)
        status_frame = ttk.LabelFrame(parent, text='3. OLLAMA状态', padding='10')
        status_frame.place(relx=1.0, rely=0, anchor='ne', x=-10, y=10)
        self.ollama_status_var = tk.StringVar(value='未连接')
        ttk.Label(status_frame, text='服务状态:').pack(side='left')
        self.ollama_status_label = ttk.Label(status_frame, textvariable=self.ollama_status_var, foreground='red')
        self.ollama_status_label.pack(side='left', padx=5)
        ttk.Label(status_frame, text='当前模型:').pack(side='left', padx=(20, 5))
        ttk.Label(status_frame, textvariable=self.selected_model_var, foreground='blue').pack(side='left', padx=5)
        main_paned_window = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill='both', expand=True, padx=10, pady=5)
        result_frame = ttk.LabelFrame(main_paned_window, text='5. 提示词结果', padding='10')
        main_paned_window.add(result_frame, weight=55)
        input_frame = ttk.LabelFrame(main_paned_window, text='4. 中文创意输入', padding='10')
        main_paned_window.add(input_frame, weight=45)
        pos_section_frame = ttk.Frame(result_frame)
        pos_section_frame.pack(fill='both', expand=True, pady=(0, 10), padx=2)
        pos_title_frame = ttk.Frame(pos_section_frame)
        pos_title_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(pos_title_frame, text='正面提示词', font=('微软雅黑', 12, 'bold')).pack(side='left')
        ttk.Label(pos_title_frame, textvariable=self.positive_tab_full_name_var, foreground='blue').pack(side='left', padx=8)
        self.positive_notebook = ttk.Notebook(pos_section_frame)
        self.positive_notebook.pack(fill='both', expand=True)
        self.positive_notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        neg_section_frame = ttk.Frame(result_frame)
        neg_section_frame.pack(fill='both', expand=True, pady=5, padx=2)
        neg_title_frame = ttk.Frame(neg_section_frame)
        neg_title_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(neg_title_frame, text='负面提示词', font=('微软雅黑', 12, 'bold')).pack(side='left')
        ttk.Label(neg_title_frame, textvariable=self.negative_tab_full_name_var, foreground='blue').pack(side='left', padx=8)
        self.negative_notebook = ttk.Notebook(neg_section_frame)
        self.negative_notebook.pack(fill='both', expand=True)
        self.negative_notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        input_text_frame = ttk.Frame(input_frame)
        input_text_frame.pack(fill='both', expand=True, pady=(10, 0))
        style_frame = ttk.Frame(input_text_frame)
        style_frame.pack(fill='x', pady=(0, 10))
        style_frame.columnconfigure(3, weight=1)
        ttk.Label(style_frame, text='风格选择:').grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.style_var = tk.StringVar(value=PROFESSIONAL_STYLES[0])
        style_combo = ttk.Combobox(style_frame, textvariable=self.style_var, values=PROFESSIONAL_STYLES, state='readonly', width=20)
        style_combo.grid(row=0, column=1, sticky='w')
        style_combo.bind('<<ComboboxSelected>>', self.on_style_change)
        self.image_label = ttk.Label(style_frame, text='图片输入:')
        self.image_label.grid(row=0, column=2, sticky='w', padx=(15, 5))
        self.image_path_entry = ttk.Entry(style_frame, textvariable=self.image_path_var)
        self.image_path_entry.grid(row=0, column=3, sticky='ew')
        self.image_browse_button = ttk.Button(style_frame, text='浏 览', command=self.browse_image_path, width=3)
        self.image_browse_button.grid(row=0, column=4, sticky='e', padx=(5, 0))
        self.chinese_input = scrolledtext.ScrolledText(input_text_frame, height=4, font=('微软雅黑', 11), wrap='word', undo=True)
        self.chinese_input.pack(fill='both', expand=True)
        self.create_context_menu(self.chinese_input)
        self.chinese_input.bind('<KeyRelease>', lambda event: self.update_button_states())
        self.preview_frame = ttk.Frame(input_text_frame)
        self.preview_label = ttk.Label(self.preview_frame, text='暂无预览图', anchor='center')
        self.preview_label.pack(fill='both', expand=True)
        self.preview_label.bind('<Double-1>', self.open_preview_file)
        self.current_preview_file = None
        convert_frame = ttk.Frame(input_frame)
        convert_frame.pack(fill='x', pady=(10, 0))
        self.convert_cn_button = ttk.Button(convert_frame, text='1.中文创意', command=self.generate_creative_chinese, state='disabled')
        self.convert_cn_button.pack(side='left')
        self.segment_button = ttk.Button(convert_frame, text='2.提示词分段', command=self.segment_chinese_text, state='disabled')
        self.segment_button.pack(side='left', padx=5)
        self.convert_en_button = ttk.Button(convert_frame, text='3.转换英文', command=self.translate_to_english, state='disabled')
        self.convert_en_button.pack(side='left', padx=5)
        self.supplement_button = ttk.Button(convert_frame, text='4.专业化调整', command=self.supplement_with_instructions, state='disabled')
        self.supplement_button.pack(side='left', padx=5)
        ttk.Button(convert_frame, text='清除重写', command=self.clear_and_rewrite).pack(side='right')
        execute_frame = ttk.Frame(parent)
        execute_frame.pack(fill='x', padx=10, pady=9)
        self.execute_button = ttk.Button(execute_frame, text='执 行 注 入', command=self.execute_workflow, state='disabled', style='Execute.TButton')
        self.execute_button.pack(side='left', ipady=16)
        self.conversion_progressbar = ttk.Progressbar(execute_frame, mode='indeterminate', style='Yellow.Horizontal.TProgressbar')
        self.conversion_progressbar.pack(side='left', padx=10, fill='x', expand=True)
        self.status_var = tk.StringVar(value='就绪')
        ttk.Label(execute_frame, textvariable=self.status_var).pack(side='right')

    def setup_ollama_tab(self, parent):
        main_container = ttk.Frame(parent)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        right_frame = ttk.Frame(main_container)
        right_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))
        control_frame = ttk.LabelFrame(left_frame, text='OLLAMA服务控制', padding='10')
        control_frame.pack(fill='x', pady=(0, 10))
        self.start_ollama_button = ttk.Button(control_frame, text='启动OLLAMA', command=self.start_ollama_service)
        self.start_ollama_button.pack(side='left', padx=5)
        self.stop_ollama_button = ttk.Button(control_frame, text='停止OLLAMA', command=self.stop_ollama_service, state='disabled')
        self.stop_ollama_button.pack(side='left', padx=5)
        ttk.Button(control_frame, text='刷新状态', command=self.refresh_ollama_status).pack(side='left', padx=5)
        self.running_model_var = tk.StringVar(value='当前加载: 无')
        ttk.Label(control_frame, textvariable=self.running_model_var, foreground='navy').pack(side='left', padx=10)
        download_frame = ttk.LabelFrame(left_frame, text='在线模型下载', padding='10')
        download_frame.pack(fill='both', expand=True)
        search_bar_frame = ttk.Frame(download_frame)
        search_bar_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(search_bar_frame, text='搜索关键词:').pack(side='left')
        self.search_model_var = tk.StringVar()
        search_entry = ttk.Entry(search_bar_frame, textvariable=self.search_model_var, width=20)
        search_entry.pack(side='left', padx=5, expand=True, fill='x')
        search_button = ttk.Button(search_bar_frame, text='搜索', command=self.search_and_display_models)
        search_button.pack(side='left', padx=5)
        search_result_frame = ttk.Frame(download_frame)
        search_result_frame.pack(fill='both', expand=True, pady=(5, 5))
        self.online_model_listbox = tk.Listbox(search_result_frame, height=10)
        self.online_model_listbox.pack(side='left', fill='both', expand=True)
        online_scrollbar = ttk.Scrollbar(search_result_frame, orient='vertical', command=self.online_model_listbox.yview)
        online_scrollbar.pack(side='right', fill='y')
        self.online_model_listbox.config(yscrollcommand=online_scrollbar.set)
        self.online_model_listbox.bind('<<ListboxSelect>>', self.on_online_model_select)
        self.download_progress_var = tk.StringVar(value='')
        ttk.Label(download_frame, textvariable=self.download_progress_var).pack(fill='x')
        model_frame = ttk.LabelFrame(right_frame, text='模型管理', padding='10')
        model_frame.pack(fill='both', expand=True)
        installed_frame = ttk.LabelFrame(model_frame, text='已安装模型', padding='5')
        installed_frame.pack(fill='both', expand=True)
        list_frame = ttk.Frame(installed_frame)
        list_frame.pack(fill='both', expand=True)
        self.model_listbox = tk.Listbox(list_frame, height=10)
        self.model_listbox.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.model_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.model_listbox.config(yscrollcommand=scrollbar.set)
        select_frame = ttk.Frame(installed_frame)
        select_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(select_frame, text='选择模型', command=self.select_model).pack(side='left')
        ttk.Button(select_frame, text='刷新列表', command=self.refresh_ollama_status).pack(side='left', padx=10)

    def on_tab_changed(self, event):
        """当Notebook标签页切换时，在对应区域的标题行显示完整的标签名称。"""
        try:
            notebook = event.widget
            tab_id = notebook.select()
            if not tab_id:
                if notebook == self.positive_notebook:
                    self.positive_tab_full_name_var.set('')
                elif notebook == self.negative_notebook:
                    self.negative_tab_full_name_var.set('')
                return
            full_tab_name = notebook.tab(tab_id, 'text')
            if notebook == self.positive_notebook:
                self.positive_tab_full_name_var.set(f'— {full_tab_name}')
            elif notebook == self.negative_notebook:
                self.negative_tab_full_name_var.set(f'— {full_tab_name}')
        except tk.TclError:
            pass

    def create_context_menu(self, text_widget):
        """为文本框创建右键菜单"""
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label='全选', command=lambda : self.select_all_text(text_widget))
        context_menu.add_command(label='撤销', command=lambda : self.undo_text(text_widget))
        context_menu.add_separator()
        context_menu.add_command(label='复制', command=lambda : self.copy_text(text_widget))
        context_menu.add_command(label='粘贴', command=lambda : self.paste_text(text_widget))
        context_menu.add_command(label='剪切', command=lambda : self.cut_text(text_widget))
        context_menu.add_separator()
        context_menu.add_command(label='删除', command=lambda : self.delete_selected_text(text_widget))
        text_widget.bind('<Button-3>', lambda e: self.show_context_menu(e, context_menu))
        text_widget.bind('<Button-2>', lambda e: self.show_context_menu(e, context_menu))
        text_widget.bind('<Control-Button-1>', lambda e: self.show_context_menu(e, context_menu))
        text_widget.bind('<FocusIn>', lambda e: text_widget.focus_set())
        text_widget.bind('<Control-z>', lambda e: self.undo_text(text_widget))
        text_widget.bind('<Control-Z>', lambda e: self.undo_text(text_widget))
        text_widget.bind('<Control-y>', lambda e: self.redo_text(text_widget))
        text_widget.bind('<Control-Y>', lambda e: self.redo_text(text_widget))
        text_widget.bind('<Control-a>', lambda e: self.select_all_text(text_widget))
        text_widget.bind('<Control-A>', lambda e: self.select_all_text(text_widget))
        text_widget.bind('<Control-x>', lambda e: self.cut_text(text_widget))
        text_widget.bind('<Control-X>', lambda e: self.cut_text(text_widget))
        text_widget.bind('<Control-c>', lambda e: self.copy_text(text_widget))
        text_widget.bind('<Control-C>', lambda e: self.copy_text(text_widget))
        text_widget.bind('<Control-v>', lambda e: self.paste_text(text_widget))
        text_widget.bind('<Control-V>', lambda e: self.paste_text(text_widget))
        return context_menu

    def show_context_menu(self, event, context_menu):
        """显示右键菜单"""
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def undo_text(self, text_widget):
        """撤销操作"""
        try:
            text_widget.edit_undo()
        except tk.TclError:
            pass

    def cut_text(self, text_widget):
        """剪切文本"""
        try:
            if text_widget.selection_get():
                text_widget.event_generate('<<Cut>>')
        except tk.TclError:
            pass

    def copy_text(self, text_widget):
        """复制文本"""
        try:
            if text_widget.selection_get():
                text_widget.event_generate('<<Copy>>')
        except tk.TclError:
            text_widget.clipboard_clear()
            text_content = text_widget.get('1.0', tk.END).strip()
            if text_content:
                text_widget.clipboard_append(text_content)

    def paste_text(self, text_widget):
        """粘贴文本"""
        try:
            text_widget.event_generate('<<Paste>>')
        except tk.TclError:
            pass

    def select_all_text(self, text_widget):
        """全选文本"""
        text_widget.tag_add(tk.SEL, '1.0', tk.END)
        text_widget.mark_set(tk.INSERT, '1.0')
        text_widget.see(tk.INSERT)

    def delete_selected_text(self, text_widget):
        """删除选中的文本"""
        try:
            if text_widget.selection_get():
                text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass

    def browse_proj_path(self):
        """浏览选择PROJ路径"""
        path = filedialog.askdirectory(initialdir=self.proj_path.get())
        if path:
            self.proj_path.set(path)
            self.status_var.set(f'已选择新路径，请点击“识别工作流”')
            self.workflow_type_combo.set('')
            for combo in [self.workflow_type_combo, self.specific_workflow_combo]:
                combo.set('')
            self.workflow_type_combo['values'] = []
            self.specific_workflow_combo['values'] = []
            self.workflow_analysis_cache = {}
            self.workflow_files = {}

    def browse_image_path(self):
        path = filedialog.askopenfilename(filetypes=[('Image Files', '*.png *.jpg *.jpeg *.bmp *.gif *.webp'), ('All Files', '*.*')])
        if path:
            self.image_path_var.set(path)

    def _extract_keywords_from_title(self, title):
        KEYWORDS_priority = ['positive', 'negative', 'base', 'main', 'refine', 'inpaint', 'fix', 'face', 'hand', 'person', 'feet']
        keywords = []
        for keyword in KEYWORDS_priority:
            if re.search('\\b' + keyword + '\\b', title, re.IGNORECASE):
                keywords.append(keyword)
        return keywords

    def recognize_workflows_in_folder(self):
        """
        使用纯算法识别并分类文件夹中的所有工作流文件。
        """
        proj_path = self.proj_path.get()
        if not os.path.exists(proj_path):
            messagebox.showerror('错误', '工作流路径不存在。')
            return
        workflow_files_to_process = [f for f in os.listdir(proj_path) if f.lower().endswith('.json')]
        if not workflow_files_to_process:
            self.status_var.set('未找到任何.json工作流文件。')
            return
        self.status_var.set('开始使用算法识别工作流...')
        self.conversion_progressbar.start(40)

        def recognition_thread_task():
            """在后台线程中依次处理文件。"""
            temp_results = {}
            total_files = len(workflow_files_to_process)
            for (i, filename) in enumerate(workflow_files_to_process):
                self.root.after(0, lambda i=i, f=filename: self.status_var.set(f'正在分析 ({i + 1}/{total_files}): {f}'))
                json_path = os.path.join(proj_path, filename)
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if not content.strip():
                            continue
                        workflow_data = json.loads(content)
                    analysis_result = self._run_workflow_analysis_algorithm(workflow_data)
                    if analysis_result:
                        temp_results[filename] = analysis_result
                except Exception as e:
                    print(f'使用算法处理 {filename} 时出错: {e}')
            self.root.after(0, self.on_recognition_complete, temp_results)
        threading.Thread(target=recognition_thread_task, daemon=True).start()

    def _run_workflow_analysis_algorithm(self, workflow_data):
        """
        算法主入口，协调分类和注入点识别，并生成规定的简表。
        """
        try:
            nodes = self._normalize_nodes(workflow_data)
            if not nodes:
                return None
            (nodes_map, graph_topology) = self._get_graph_topology(nodes)
            category = self._categorize_workflow(nodes, nodes_map, graph_topology)
            if category == '未分类':
                return None
            summary_table = self._build_summary_table(nodes, nodes_map, graph_topology, workflow_data)
            if summary_table:
                return {'workflow_category': category, 'summary_table': summary_table}
            else:
                return {'workflow_category': category, 'summary_table': []}
        except Exception as e:
            print(f'算法分析失败: {e}')
            traceback.print_exc()
            return None

    def _build_summary_table(self, nodes, nodes_map, graph_topology, workflow_data):
        """
        根据用户要求，构建简表。
        核心逻辑：寻找注入点，分析节点，提取关键词，生成记录。
        """
        summary_table = []
        unnamed_counter = 1
        KEYWORDS_priority = ['positive', 'negative', 'base', 'main', 'refine', 'inpaint', 'fix', 'face', 'hand', 'person', 'feet']
        for (i, node) in enumerate(nodes):
            node['_order'] = i
            node_type = node.get('type', '')
            title = node.get('title', '').strip()
            node_id = str(node.get('id'))
            injection_item = None
            if 'CLIPTextEncode' in node_type:
                widget_info = None
                is_list_format = 'nodes' in workflow_data and isinstance(workflow_data['nodes'], list)
                original_node = None
                if is_list_format:
                    original_node = next((n for n in workflow_data['nodes'] if str(n.get('id')) == node_id), None)
                else:
                    original_node = workflow_data.get(node_id)
                if original_node:
                    if 'widgets_values' in original_node and isinstance(original_node.get('widgets_values'), list):
                        for (idx, value) in enumerate(original_node['widgets_values']):
                            if isinstance(value, str):
                                widget_info = {'type': 'widgets_values', 'index': idx, 'name': 'text'}
                                break
                    if not widget_info and 'inputs' in original_node and ('text' in original_node['inputs']):
                        widget_info = {'type': 'inputs', 'key': 'text', 'name': 'text', 'index': 0}
                if widget_info:
                    keywords = self._extract_keywords_from_title(title)
                    if not keywords:
                        downstream_consumers = self._get_downstream_consumers(node_id, nodes_map, workflow_data)
                        is_negative_by_connection = False
                        for consumer_id in downstream_consumers:
                            consumer_node = nodes_map.get(consumer_id)
                            if not consumer_node:
                                continue
                            for inp in consumer_node.get('inputs', []):
                                link_info = inp.get('link')
                                if link_info is not None and isinstance(link_info, list) and (str(link_info[0]) == node_id):
                                    if inp.get('name') == 'negative':
                                        is_negative_by_connection = True
                                        break
                            if is_negative_by_connection:
                                break
                        keywords.append('negative' if is_negative_by_connection else 'positive')
                    full_node_name = title if title else f'UNKNOWN{unnamed_counter}'
                    if not title:
                        unnamed_counter += 1
                    injection_item = {'injection_type': 'prompt', 'injection_location': {'node_id': node_id, 'widget_info': widget_info}, 'full_node_name': full_node_name, 'keywords': keywords, 'node_type': node_type, '_order': i}
            elif 'LoadImage' in node_type:
                widget_info = None
                if 'widgets_values' in node and isinstance(node.get('widgets_values'), list):
                    widget_info = {'type': 'widgets_values', 'index': 0, 'name': 'image'}
                elif 'inputs' in node and 'image' in node['inputs']:
                    widget_info = {'type': 'inputs', 'key': 'image', 'name': 'image', 'index': 0}
                if widget_info:
                    injection_item = {'injection_type': 'image', 'injection_location': {'node_id': node_id, 'widget_info': widget_info}, 'full_node_name': title or 'Load Image', 'keywords': ['image_input'], 'node_type': node_type, '_order': i}
            if injection_item:
                summary_table.append(injection_item)
        summary_table.sort(key=lambda x: x['_order'])
        for record in summary_table:
            del record['_order']
        return summary_table

    def _categorize_workflow_from_types(self, node_types):
        VIDEO_OUTPUT_NODE_TYPES = {'SaveAnimatedWEBP', 'SaveAnimatedPNG', 'SaveAnimation', 'VHS_VideoCombine', 'ExportVideo', 'VideoCombine'}
        IMAGE_INPUT_NODE_TYPES = {'LoadImage'}
        has_video_output = any((t in VIDEO_OUTPUT_NODE_TYPES for t in node_types))
        has_image_input = any((t in IMAGE_INPUT_NODE_TYPES for t in node_types))
        if has_video_output or has_image_input:
            return '未分类'
        else:
            return '文生图'

    def _get_downstream_consumers(self, node_id, nodes_map, workflow_data):
        """辅助函数，用于查找一个节点的所有直接下游消费者。"""
        consumers = set()
        if 'links' in workflow_data and isinstance(workflow_data['links'], list):
            for link in workflow_data['links']:
                try:
                    source_id = str(link[1])
                    target_id = str(link[3])
                    if source_id == node_id:
                        consumers.add(target_id)
                except (IndexError, TypeError):
                    continue
        for (n_id, node) in nodes_map.items():
            if 'inputs' in node:
                for inp in node.get('inputs', []):
                    link_info = inp.get('link')
                    if link_info is not None and isinstance(link_info, list) and (str(link_info[0]) == node_id):
                        consumers.add(n_id)
        return list(consumers)

    def _normalize_nodes(self, workflow_data):
        """将不同格式的工作流JSON转换为统一的节点列表格式。"""
        if 'nodes' in workflow_data and isinstance(workflow_data['nodes'], list):
            return workflow_data['nodes']
        nodes = []
        try:
            raw_nodes = {node_id: node_info for (node_id, node_info) in workflow_data.items() if isinstance(node_info, dict) and 'class_type' in node_info}
            for (node_id, node_info) in raw_nodes.items():
                node = {'id': int(node_id), 'type': node_info['class_type'], 'title': node_info.get('_meta', {}).get('title', ''), 'inputs': [], 'widgets_values': []}
                if 'inputs' in node_info:
                    widget_values_in_input = []
                    for (name, value) in node_info['inputs'].items():
                        if isinstance(value, list) and len(value) == 2:
                            node['inputs'].append({'name': name, 'type': '_LINK_', 'link': value})
                        else:
                            widget_values_in_input.append(value)
                    if widget_values_in_input:
                        node['widgets_values'] = widget_values_in_input
                nodes.append(node)
            return nodes
        except Exception as e:
            print(f'标准化节点时出错: {e}')
            return None

    def on_recognition_complete(self, results):
        """Callback after all workflows are recognized."""
        self.conversion_progressbar.stop()
        self.workflow_analysis_cache = results
        self.workflow_files = {}
        for (filename, analysis) in self.workflow_analysis_cache.items():
            category = analysis.get('workflow_category', '未分类')
            if category not in self.workflow_files:
                self.workflow_files[category] = []
            self.workflow_files[category].append(filename)
        categories = sorted(list(self.workflow_files.keys()))
        self.workflow_type_var.set('')
        self.workflow_type_combo['values'] = categories
        if categories:
            self.workflow_type_var.set(categories[0])
        self.on_workflow_type_change()
        self.status_var.set(f'识别完成: {len(self.workflow_analysis_cache)}个工作流。')
        if len(self.workflow_analysis_cache) > 0:
            messagebox.showinfo('识别完成', f'已成功分析 {len(self.workflow_analysis_cache)} 个工作流文件。')
        else:
            messagebox.showwarning('识别提醒', '未能成功分析任何工作流文件，请检查工作流文件或控制台错误。')

    def on_workflow_type_change(self, event=None):
        """工作流类型变化时更新具体工作流列表"""
        workflow_type = self.workflow_type_var.get()
        files = self.workflow_files.get(workflow_type, [])
        self.specific_workflow_combo['values'] = files
        self.specific_workflow_combo.set(files[0] if files else '')
        self.on_specific_workflow_change()

    def start_ollama_service(self):
        """启动OLLAMA服务"""
        self.status_var.set('正在启动OLLAMA...')

        def start_task():
            success = self.ollama_manager.start_ollama()
            self.root.after(0, lambda : self.on_ollama_start_complete(success))
        threading.Thread(target=start_task, daemon=True).start()

    def on_ollama_start_complete(self, success):
        """OLLAMA启动完成回调"""
        if success:
            self.ollama_status_var.set('运行中')
            self.ollama_status_label.config(foreground='green')
            self.status_var.set('OLLAMA已启动')
            self.start_ollama_button.config(state='disabled')
            self.stop_ollama_button.config(state='normal')
            self.refresh_model_list()
            self.client = self._create_openai_client()
        else:
            self.ollama_status_var.set('启动失败')
            self.ollama_status_label.config(foreground='red')
            self.status_var.set('OLLAMA启动失败')
            self.start_ollama_button.config(state='normal')
            self.stop_ollama_button.config(state='disabled')

    def stop_ollama_service(self):
        """停止OLLAMA服务"""
        self.ollama_manager.stop_ollama()
        self.ollama_status_var.set('已停止')
        self.ollama_status_label.config(foreground='red')
        self.selected_model_var.set('未选择')
        self.selected_model_for_conversion.set('')
        self.convert_en_button.config(state='disabled')
        self.convert_cn_button.config(state='disabled')
        self.status_var.set('OLLAMA已停止')
        self.start_ollama_button.config(state='normal')
        self.stop_ollama_button.config(state='disabled')
        self.running_model_var.set('当前加载: 无')

    def refresh_ollama_status(self):
        """刷新OLLAMA状态，并更新UI显示"""
        self.status_var.set('正在刷新状态...')

        def task():
            is_running = False
            running_models = []
            try:
                response = self.ollama_manager._request('GET', '/api/tags', timeout=2)
                if response.status_code == 200:
                    is_running = True
                    running_models = self.ollama_manager.get_running_models()
            except requests.exceptions.RequestException:
                is_running = False

            def update_ui():
                self.ollama_manager.is_running = is_running
                self.running_models_cache = running_models
                if is_running:
                    self.start_ollama_button.config(state='disabled')
                    self.stop_ollama_button.config(state='normal')
                    if not self.client:
                        self.client = self._create_openai_client()
                    self.refresh_model_list()
                    if running_models:
                        self.ollama_status_var.set('模型运行中')
                        self.ollama_status_label.config(foreground='green')
                        self.selected_model_var.set(f"运行中: {', '.join(running_models)}")
                        self.running_model_var.set(f"当前加载: {', '.join(running_models)}")
                    else:
                        self.ollama_status_var.set('服务运行中 (无模型)')
                        try:
                            self.ollama_status_label.config(foreground='orange')
                        except tk.TclError:
                            self.ollama_status_label.config(foreground='blue')
                        self.selected_model_var.set('无模型加载')
                        self.running_model_var.set('当前加载: 无')
                    self.status_var.set('OLLAMA状态已刷新')
                else:
                    self.client = None
                    self.ollama_status_var.set('未运行')
                    self.ollama_status_label.config(foreground='red')
                    self.start_ollama_button.config(state='normal')
                    self.stop_ollama_button.config(state='disabled')
                    self.running_model_var.set('当前加载: 无')
                    self.selected_model_var.set('服务未连接')
                    self.model_listbox.delete(0, tk.END)
                    self.status_var.set('OLLAMA未运行或连接失败')
                self.update_button_states()
            self.root.after(0, update_ui)
        threading.Thread(target=task, daemon=True).start()

    def search_and_display_models(self):
        """搜索并显示在线模型"""
        keyword = self.search_model_var.get()
        self.download_progress_var.set(f"正在搜索 '{keyword}'...")

        def search_task():
            models = self.ollama_manager.search_online_models(keyword)
            self.root.after(0, lambda : self.update_online_model_list(models))
        threading.Thread(target=search_task, daemon=True).start()

    def update_online_model_list(self, models):
        """更新在线模型列表"""
        self.online_model_listbox.delete(0, tk.END)
        for model in models:
            self.online_model_listbox.insert(tk.END, model)
        self.download_progress_var.set(f'找到 {len(models)} 个模型。点击名称以下载。')

    def on_online_model_select(self, event=None):
        """当在线模型被选择时，开始下载"""
        selection = self.online_model_listbox.curselection()
        if not selection:
            return
        model_name = self.online_model_listbox.get(selection[0])
        if messagebox.askyesno('确认下载', f"您确定要下载模型 '{model_name}' 吗?"):
            self.download_model(model_name)

    def download_model(self, model_name):
        """下载指定模型"""
        self.download_progress_var.set(f'开始下载 {model_name}...')

        def download_task():

            def progress_callback(data):
                if 'status' in data:
                    status = data['status']
                    if 'completed' in data and 'total' in data:
                        percent = data['completed'] / data['total'] * 100
                        self.root.after(0, lambda : self.download_progress_var.set(f'{status}: {percent:.1f}%'))
                    else:
                        self.root.after(0, lambda : self.download_progress_var.set(status))
            success = self.ollama_manager.pull_model(model_name, progress_callback)
            self.root.after(0, lambda : self.on_download_complete(success))
        threading.Thread(target=download_task, daemon=True).start()

    def on_download_complete(self, success):
        """下载完成回调"""
        if success:
            self.download_progress_var.set('下载完成！')
            self.refresh_model_list()
        else:
            self.download_progress_var.set('下载失败。')

    def refresh_model_list(self):
        """刷新模型列表"""

        def task():
            models = self.ollama_manager.get_available_models()
            self.root.after(0, lambda : (self.model_listbox.delete(0, tk.END), [self.model_listbox.insert(tk.END, m) for m in models]))
        threading.Thread(target=task, daemon=True).start()

    def select_model(self):
        """选择模型并立即在后台加载"""
        selection = self.model_listbox.curselection()
        if selection:
            model_name = self.model_listbox.get(selection[0])
            self.selected_model_for_conversion.set(model_name)
            self.selected_model_var.set(f'正在加载: {model_name}')
            self.status_var.set(f'开始加载模型: {model_name}...')
            self.load_model_in_background(model_name)

    def load_model_in_background(self, model_name):
        """发送一个虚拟请求以强制OLLAMA加载模型。"""

        def task():
            try:
                if not self.client:
                    self.root.after(0, lambda : self.status_var.set('加载失败: OLLAMA客户端未初始化'))
                    return
                self._chat_completion_with_retry(model_name=model_name, messages=[{'role': 'user', 'content': 'Hi'}], temperature=0.1, max_tokens=1)
                self.root.after(10000, self.refresh_ollama_status)
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.status_var.set(f'加载模型失败: {err}'))
                self.root.after(10000, self.refresh_ollama_status)
        threading.Thread(target=task, daemon=True).start()

    def on_specific_workflow_change(self, event=None):
        workflow_name = self.specific_workflow_var.get()
        self.current_workflow_type = ''
        has_image_input = False
        if workflow_name:
            analysis = self.workflow_analysis_cache.get(workflow_name, {})
            self.current_workflow_type = analysis.get('workflow_category', '')
            summary = analysis.get('summary_table', [])
            if not any((item['injection_type'] == 'prompt' for item in summary)):
                messagebox.showinfo('工作流提示', f"您选择的工作流 '{workflow_name}' 没有找到可用的提示词注入点。")
            has_image_input = any((item['injection_type'] == 'image' for item in summary))
        is_image_workflow = self.current_workflow_type in ['图生图', '图生视频']
        self.image_label.config(state='normal' if is_image_workflow else 'disabled')
        self.image_path_entry.config(state='normal' if is_image_workflow else 'disabled')
        self.image_browse_button.config(state='normal' if is_image_workflow else 'disabled')
        if not is_image_workflow:
            self.image_path_var.set('')
        self.clear_and_rewrite(clear_input=False)

    def on_style_change(self, event=None):
        self.status_var.set(f'已选择风格: {self.style_var.get()}')

    def update_button_states(self):
        """
        根据程序当前状态和用户的要求，更新四个主要操作按钮的激活状态。
        """
        is_model_ready = self.ollama_manager.is_running and bool(self.selected_model_for_conversion.get())
        is_workflow_selected = bool(self.specific_workflow_var.get())
        has_injection_points = False
        if is_workflow_selected:
            workflow_name = self.specific_workflow_var.get()
            analysis = self.workflow_analysis_cache.get(workflow_name, {})
            summary = analysis.get('summary_table', [])
            has_injection_points = any((item.get('injection_type') == 'prompt' for item in summary))
        can_generate_creative = is_model_ready and is_workflow_selected and has_injection_points and bool(self.chinese_input.get('1.0', tk.END).strip())
        self.convert_cn_button.config(state='normal' if can_generate_creative else 'disabled')
        creative_text_widget = self.prompt_text_widgets.get('创意全文')
        has_creative_text = creative_text_widget and bool(creative_text_widget.get('1.0', tk.END).strip())
        can_segment = is_model_ready and self.creative_chinese_generated and has_creative_text
        self.segment_button.config(state='normal' if can_segment else 'disabled')
        has_segmented_text = False
        if self.chinese_segmented:
            all_segment_widgets = list(self.prompt_text_widgets.values()) + list(self.negative_prompt_text_widgets.values())
            has_segmented_text = any((widget.get('1.0', tk.END).strip() for widget in all_segment_widgets))
        can_translate = is_model_ready and self.chinese_segmented and has_segmented_text
        self.convert_en_button.config(state='normal' if can_translate else 'disabled')
        has_translated_text = False
        if self.english_translated:
            all_segment_widgets = list(self.prompt_text_widgets.values()) + list(self.negative_prompt_text_widgets.values())
            has_translated_text = any((widget.get('1.0', tk.END).strip() for widget in all_segment_widgets))
        can_supplement = is_model_ready and self.english_translated and has_translated_text
        self.supplement_button.config(state='normal' if can_supplement else 'disabled')
        can_execute = self.english_supplemented
        self.execute_button.config(state='normal' if can_execute else 'disabled')

    def _prepare_and_run_ai_task(self, button, status_text, system_prompt_key, user_content_json, callback):
        if not self.selected_model_for_conversion.get():
            messagebox.showwarning('警告', '请先在“OLLAMA设置”标签页中选择并加载一个AI模型')
            return
        self.conversion_progressbar.start(40)
        self.status_var.set(status_text)
        button.config(state='disabled')

        def ai_task():
            try:
                model_name = self.selected_model_for_conversion.get()
                ollama_params = get_model_params(model_name)
                temp = ollama_params.get('temperature', 0.7)
                completion = self._chat_completion_with_retry(model_name=model_name, messages=[{'role': 'system', 'content': SYSTEM_PROMPTS[system_prompt_key]}, {'role': 'user', 'content': json.dumps(user_content_json, ensure_ascii=False)}], temperature=temp, json_mode=True)
                response_text = completion.choices[0].message.content
                self.root.after(0, callback, response_text)
            except Exception as e:
                self.root.after(0, self.on_task_error, str(e))
        threading.Thread(target=ai_task, daemon=True).start()

    def on_task_error(self, error_msg):
        self.conversion_progressbar.stop()
        messagebox.showerror('任务失败', error_msg)
        self.status_var.set('任务失败')
        self.update_button_states()

    def _process_ai_response(self, response_text, expected_keys, success_callback):
        try:
            cot_patterns = ['<thought>.*?</thought>', '<reasoning>.*?</reasoning>', '<\\|channel\\|>thought\\n.*?<channel\\|>']
            processed_text = response_text
            for pattern in cot_patterns:
                processed_text = re.sub(pattern, '', processed_text, flags=re.DOTALL | re.IGNORECASE)
            match = re.search('\\[START_JSON\\](.*?)(\\[END_JSON\\]|\\Z)', processed_text, re.DOTALL)
            json_string = ''
            if match:
                json_string = match.group(1).strip()
            else:
                try:
                    first_brace = processed_text.index('{')
                    last_brace = processed_text.rindex('}')
                    json_string = processed_text[first_brace:last_brace + 1]
                except ValueError:
                    try:
                        first_brace = response_text.index('{')
                        last_brace = response_text.rindex('}')
                        json_string = response_text[first_brace:last_brace + 1]
                    except ValueError:
                        raise ValueError('AI响应中未找到[START_JSON]标记，也未能定位到有效的JSON对象。')
            json_string = re.sub('^```json\\s*', '', json_string, flags=re.IGNORECASE)
            json_string = re.sub('\\s*```$', '', json_string)
            result = json.loads(json_string)
            missing_keys = [k for k in expected_keys if k not in result]
            if missing_keys:
                if not messagebox.askyesno('内容缺失', f"AI返回结果缺少以下部分: {', '.join(missing_keys)}.\n是否继续处理已有内容?"):
                    raise ValueError('用户取消操作')
                for k in missing_keys:
                    result[k] = ''
            success_callback(result)
        except Exception as e:
            self.on_task_error(f'处理AI响应失败: {e}')

    def generate_creative_chinese(self):
        self._reset_states(keep_creative_input=True)
        user_text = self.chinese_input.get('1.0', tk.END).strip()
        selected_style = self.style_var.get()
        if not user_text:
            messagebox.showwarning('警告', '请输入您的中文创意。')
            return
        content = f"请将以下描述文字('{user_text}')融合'{selected_style}'风格，进行润色、扩展和优化，使其更生动、更富有想象力、更包含细节和文采。"
        messages = [{'role': 'system', 'content': SYSTEM_PROMPTS['中文润色']}, {'role': 'user', 'content': content}]
        self.status_var.set('正在根据文本生成中文创意...')

        def callback(response_text):
            try:
                cot_patterns = ['<thought>.*?</thought>', '<\\|thought\\|>.*?<\\|thought\\|>', '<reasoning>.*?</reasoning>', '<\\|channel\\|>thought\\n.*?<channel\\|>', '<\\|begin_of_thought\\|>.*?<\\|end_of_thought\\|>', '思考过程：.*?(\\n\\n|\\Z)']
                processed_text = response_text
                for pattern in cot_patterns:
                    processed_text = re.sub(pattern, '', processed_text, flags=re.DOTALL | re.IGNORECASE)
                match = re.search('\\[START_TEXT\\](.*?)(\\[END_TEXT\\]|\\Z)', processed_text, re.DOTALL)
                if match:
                    self.creative_chinese_text = match.group(1).strip()
                else:
                    prefix_pattern = '^(?:THINKING|THINK|思考|分析|ANSWER|Action|输出|Result|正文|总结)[:：\\s]*'
                    cleaned_text = re.sub(prefix_pattern, '', processed_text, count=1).strip()
                    cleaned_text = cleaned_text.replace('[START_TEXT]', '').replace('[END_TEXT]', '')
                    if not cleaned_text.strip():
                        self.creative_chinese_text = response_text.strip()
                    else:
                        self.creative_chinese_text = cleaned_text.strip()
                self._update_ui_with_creative_chinese(self.creative_chinese_text)
                self.creative_chinese_generated = True
                self.status_var.set('1. 中文创意已生成')
            except Exception as e:
                self.on_task_error(f'处理AI响应失败: {e}')
            finally:
                self.conversion_progressbar.stop()
                self.update_button_states()
        if not self.selected_model_for_conversion.get():
            messagebox.showwarning('警告', '请先在“OLLAMA设置”标签页中选择并加载一个AI模型。')
            return
        self.conversion_progressbar.start(40)
        self.convert_cn_button.config(state='disabled')

        def ai_task():
            try:
                model_name = self.selected_model_for_conversion.get()
                ollama_params = get_model_params(model_name)
                temp = ollama_params.get('temperature', 0.7)
                completion = self._chat_completion_with_retry(model_name=model_name, messages=messages, temperature=temp, json_mode=False)
                self.root.after(0, callback, completion.choices[0].message.content)
            except Exception as e:
                self.root.after(0, self.on_task_error, str(e))
        threading.Thread(target=ai_task, daemon=True).start()

    def segment_chinese_text(self):
        summary_table = self._get_prepared_summary_table()
        if not summary_table:
            self.on_task_error('无法分段：未找到有效的提示词注入点。')
            return
        creative_text = self.prompt_text_widgets.get('创意全文', self.chinese_input).get('1.0', tk.END).strip()
        segments_info = [{'display_name': item['display_name'], 'keywords': item['keywords']} for item in summary_table]
        user_content = {'creative_text': creative_text, 'target_segments': segments_info}

        def callback(response_text):
            expected_keys = [item['display_name'] for item in summary_table if item['injection_type'] == 'prompt']
            self._process_ai_response(response_text, expected_keys, on_segmentation_success)

        def on_segmentation_success(result):
            self._setup_segment_tabs(result)
            self.chinese_segmented = True
            self.status_var.set('2. 中文分段完成')
            self.conversion_progressbar.stop()
            self.update_button_states()
        self._prepare_and_run_ai_task(self.segment_button, '正在进行中文分段...', 'Chinese Segmentation', user_content, callback)

    def translate_to_english(self):
        prompts = self._get_prompts_from_ui()
        user_content = self._build_grouped_translation_payload(prompts)

        def callback(response_text):
            self._process_ai_response(response_text, list(prompts.keys()), on_translation_success)

        def on_translation_success(result):
            self._update_ui_tabs(result)
            self.english_translated = True
            self.status_var.set('3. 英文转换完成')
            self.conversion_progressbar.stop()
            self.update_button_states()
        self._prepare_and_run_ai_task(self.convert_en_button, '正在转换为英文...', 'English Translation', user_content, callback)

    def _build_grouped_translation_payload(self, prompts):
        """
        构建“按提示词全名分组”的翻译输入，避免多段正负提示词互相串段。
        输出同时包含:
        - prompt_groups: 用于给模型提供分组上下文
        - flat_prompts: 用于强约束输出键与UI精确映射
        """
        summary_table = self._get_prepared_summary_table()
        if not summary_table:
            return {'prompt_groups': [], 'flat_prompts': prompts}
        grouped = {}
        for item in summary_table:
            if item.get('injection_type') != 'prompt':
                continue
            display_name = item.get('display_name')
            if display_name not in prompts:
                continue
            full_name = item.get('full_node_name', display_name)
            group = grouped.setdefault(full_name, {'full_name': full_name, 'segments': []})
            keywords = item.get('keywords', [])
            seg_type = 'negative' if 'negative' in keywords else 'positive'
            group['segments'].append({'display_name': display_name, 'keywords': keywords, 'type': seg_type, 'text': prompts.get(display_name, '')})
        return {'prompt_groups': list(grouped.values()), 'flat_prompts': prompts}

    def supplement_with_instructions(self):
        """专业化调整 (开源版默认跳过)"""
        prompts = self._get_prompts_from_ui()

        def on_supplement_success(result):
            self._update_ui_tabs(result)
            self.english_supplemented = True
            self.status_var.set('4. 专业化调整已跳过 (开源版)')
            self.conversion_progressbar.stop()
            self.update_button_states()
        self.root.after(100, lambda : on_supplement_success(prompts))

    def _clear_all_tabs(self):
        for nb in [self.positive_notebook, self.negative_notebook]:
            for i in reversed(range(nb.index('end'))):
                nb.forget(i)
        self.prompt_text_widgets.clear()
        self.negative_prompt_text_widgets.clear()
        self.positive_tab_full_name_var.set('')
        self.negative_tab_full_name_var.set('')

    def _reset_states(self, keep_creative_input=False, clear_ui=True):
        if not keep_creative_input:
            self.chinese_input.delete('1.0', tk.END)
        self.creative_chinese_text = ''
        self.creative_chinese_generated = False
        self.chinese_segmented = False
        self.english_translated = False
        self.english_supplemented = False
        if hasattr(self, 'preview_frame'):
            self.preview_frame.pack_forget()
            self.preview_label.config(image='', text='暂无预览图')
            self.current_preview_file = None
        if clear_ui:
            self._clear_all_tabs()
        self.update_button_states()

    def add_prompt_tab(self, title, content, height=9):
        """Adds a tab to the positive prompts notebook."""
        frame = ttk.Frame(self.positive_notebook)
        self.positive_notebook.add(frame, text=title)
        text_widget = scrolledtext.ScrolledText(frame, height=height, font=('微软雅黑', 10), wrap='word', undo=True)
        text_widget.pack(fill='both', expand=True, padx=2, pady=2)
        text_widget.insert('1.0', content)
        self.create_context_menu(text_widget)
        self.prompt_text_widgets[title] = text_widget

    def add_negative_prompt_tab(self, title, content, height=5):
        """Adds a tab to the negative prompts notebook."""
        frame = ttk.Frame(self.negative_notebook)
        self.negative_notebook.add(frame, text=title)
        text_widget = scrolledtext.ScrolledText(frame, height=height, font=('微软雅黑', 10), wrap='word', undo=True)
        text_widget.pack(fill='both', expand=True, padx=2, pady=2)
        text_widget.insert('1.0', content)
        self.create_context_menu(text_widget)
        self.negative_prompt_text_widgets[title] = text_widget

    def _setup_creative_text_tab(self, text):
        self._clear_all_tabs()
        self.add_prompt_tab('创意全文', text, 12)

    def _setup_segment_tabs(self, data):
        self._clear_all_tabs()
        summary_table = self._get_prepared_summary_table()
        for item in summary_table:
            display_name = item['display_name']
            content = data.get(display_name, '')
            if 'negative' in item['keywords']:
                self.add_negative_prompt_tab(display_name, content, 5)
            else:
                self.add_prompt_tab(display_name, content, 9)

    def _get_prepared_summary_table(self):
        """
        Returns the summary_table prepared for the UI.
        It ensures each prompt segment has a unique 'display_name', which is crucial for UI tabs and AI interaction.
        For example, if two nodes are named "Positive", they will become "Positive (1)" and "Positive (2)".
        """
        workflow_name = self.specific_workflow_var.get()
        analysis_data = self.workflow_analysis_cache.get(workflow_name, {})
        summary_table = [dict(item) for item in analysis_data.get('summary_table', [])]
        if not summary_table:
            return []
        name_counts = Counter((item['full_node_name'] for item in summary_table))
        processed_counts = Counter()
        for item in summary_table:
            full_name = item['full_node_name']
            if name_counts[full_name] > 1:
                processed_counts[full_name] += 1
                item['display_name'] = f'{full_name} ({processed_counts[full_name]})'
            else:
                item['display_name'] = full_name
        return summary_table

    def _update_ui_with_creative_chinese(self, text):
        """
        Displays the generated creative Chinese text in the UI.
        It clears all previous result tabs and creates a new tab named '创意全文'
        in the left-hand results panel, making it ready for the segmentation step.
        It no longer modifies the original user input box.
        """
        self._clear_all_tabs()
        self.add_prompt_tab('创意全文', text, 12)

    def _update_ui_tabs(self, data):
        for (name, content) in data.items():
            if name in self.prompt_text_widgets:
                self.prompt_text_widgets[name].delete('1.0', tk.END)
                self.prompt_text_widgets[name].insert('1.0', content)
            elif name in self.negative_prompt_text_widgets:
                self.negative_prompt_text_widgets[name].delete('1.0', tk.END)
                self.negative_prompt_text_widgets[name].insert('1.0', content)

    def _get_prompts_from_ui(self):
        """Gathers all current prompts from the UI tabs."""
        prompts = {}
        for (display_name, widget) in self.prompt_text_widgets.items():
            prompts[display_name] = widget.get('1.0', tk.END).strip()
        for (display_name, widget) in self.negative_prompt_text_widgets.items():
            prompts[display_name] = widget.get('1.0', tk.END).strip()
        return prompts

    def clear_and_rewrite(self, clear_input=True):
        if clear_input:
            self.chinese_input.delete('1.0', tk.END)
        self._reset_states(keep_creative_input=not clear_input)
        self.status_var.set('已清除，可重新输入')

    def _get_graph_topology(self, nodes):
        """构建图的拓扑结构，用于遍历。"""
        nodes_map = {str(node['id']): node for node in nodes}
        destination_node_ids = set()
        for (node_id, node) in nodes_map.items():
            node['downstream'] = []
            if 'inputs' in node:
                for an_input in node.get('inputs', []):
                    link_info = an_input.get('link')
                    if link_info is not None:
                        if isinstance(link_info, list) and len(link_info) > 0:
                            destination_node_ids.add(node_id)
                        elif isinstance(link_info, int):
                            destination_node_ids.add(node_id)
        return (nodes_map, {'destination_node_ids': destination_node_ids})

    def _categorize_workflow(self, nodes, nodes_map, graph_topology):
        """阶段一：基于节点类型的工作流分类算法。"""
        node_types = {n.get('type') for n in nodes}
        VIDEO_OUTPUT_NODE_TYPES = {'SaveAnimatedWEBP', 'SaveAnimatedPNG', 'SaveAnimation', 'VHS_VideoCombine', 'ExportVideo', 'VideoCombine'}
        IMAGE_INPUT_NODE_TYPES = {'LoadImage'}
        has_video_output = any((t in VIDEO_OUTPUT_NODE_TYPES for t in node_types))
        has_image_input = any((t in IMAGE_INPUT_NODE_TYPES for t in node_types))
        if has_video_output:
            return '文生图'
        else:
            return '文生图'

    def execute_workflow(self):
        """
        执行工作流注入。
        此函数从UI获取最终的、可能被用户修改过的提示词，
        然后将它们注入到选定的工作流JSON文件中，并将其复制到ComfyUI目录。
        """
        specific_workflow = self.specific_workflow_combo.get()
        if not specific_workflow:
            messagebox.showwarning('警告', '请选择具体工作流文件')
            return
        analysis_data = self.workflow_analysis_cache.get(specific_workflow)
        if not analysis_data:
            messagebox.showerror('错误', '未找到当前工作流的分析数据。请先执行“识别工作流”。')
            return
        summary_table = self._get_prepared_summary_table()
        if not summary_table:
            messagebox.showerror('错误', '工作流分析数据无效，缺少简表。')
            return
        prompts_to_inject = self._get_prompts_from_ui()
        image_path_to_inject = self.image_path_var.get()
        has_prompt_content = any((value.strip() for value in prompts_to_inject.values()))
        has_image_content = bool(image_path_to_inject.strip())
        if not has_prompt_content and (not has_image_content):
            return messagebox.showwarning('警告', '没有找到任何有效的提示词或图片进行注入。')
        try:
            workflow_path = os.path.join(self.proj_path.get(), specific_workflow)
            if not os.path.exists(workflow_path):
                messagebox.showerror('错误', f'工作流文件不存在: {workflow_path}')
                return
            backup_path = f'{workflow_path}.backup'
            shutil.copy2(workflow_path, backup_path)
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            updated_nodes_count = self.update_workflow_nodes(workflow_data, prompts_to_inject, image_path_to_inject, summary_table)
            if updated_nodes_count > 0:
                with open(workflow_path, 'w', encoding='utf-8') as f:
                    json.dump(workflow_data, f, indent=2, ensure_ascii=False)
                comfyui_base = self._find_comfyui_path()
                if not comfyui_base:
                    messagebox.showwarning('未找到 ComfyUI', '未能在程序前后三层目录内找到 ComfyUI 运行文件夹。\n\n工作流 JSON 已保存到源目录，但未自动同步到 ComfyUI。\n请手动将文件复制到 ComfyUI 的 user/default/workflows 目录。')
                    self.status_var.set(f'已注入工作流，但未找到 ComfyUI 目录。')
                    self.run_comfyui_button.config(state='normal', style='Run.TButton')
                    self.current_injected_workflow_path = workflow_path
                    return
                comfyui_workflows_dir = os.path.join(comfyui_base, 'user', 'default', 'workflows')
                if not os.path.exists(comfyui_workflows_dir):
                    try:
                        os.makedirs(comfyui_workflows_dir, exist_ok=True)
                    except OSError as e:
                        messagebox.showerror('创建目录失败', f'无法创建ComfyUI工作流目录:\n{comfyui_workflows_dir}\n错误: {e}')
                        return
                target_path = os.path.join(comfyui_workflows_dir, specific_workflow)
                shutil.copy2(workflow_path, target_path)
                self.status_var.set(f'已复制工作流到ComfyUI: {specific_workflow}')
                injected_parts = []
                if has_prompt_content:
                    injected_parts.append('提示词')
                if has_image_content:
                    injected_parts.append('图片')
                if injected_parts:
                    parts_str = ' 和 '.join(injected_parts)
                    final_message = f'{parts_str}已成功注入并复制到ComfyUI工作流:\n{specific_workflow}'
                    self.status_var.set(f'{parts_str}已成功注入！')
                    self.run_comfyui_button.config(state='normal', style='Run.TButton')
                    self.current_injected_workflow_path = target_path
                    messagebox.showinfo('注入成功', final_message)
                else:
                    success_message = '注入操作已完成。'
                    messagebox.showinfo('操作完成', success_message)
            else:
                messagebox.showinfo('注入提醒', '已生成提示词，但在工作流中没有找到可更新的节点。请检查工作流文件或算法分析结果。')
        except Exception as e:
            messagebox.showerror('执行错误', f'执行工作流时出错: {str(e)}')

    def update_workflow_nodes(self, workflow_data, prompts_to_inject, image_path_to_inject, summary_table):
        """根据简表分析结果，将UI中的提示词和图片路径精确注入到工作流节点中。"""
        updated_count = 0
        is_list_format = 'nodes' in workflow_data and isinstance(workflow_data['nodes'], list)
        nodes_dict = {str(node['id']): node for node in workflow_data['nodes']} if is_list_format else workflow_data
        for item in summary_table:
            injection_type = item['injection_type']
            details = item['injection_location']
            node_id = details['node_id']
            node = nodes_dict.get(node_id)
            if not node:
                continue
            injected = False
            if injection_type == 'prompt':
                display_name = item['display_name']
                prompt_text = prompts_to_inject.get(display_name)
                if prompt_text:
                    widget_info = details['widget_info']
                    if widget_info['type'] == 'widgets_values':
                        idx = widget_info['index']
                        if 'widgets_values' in node and idx < len(node['widgets_values']):
                            node['widgets_values'][idx] = prompt_text
                            injected = True
                    elif widget_info['type'] == 'inputs':
                        key = widget_info['key']
                        if 'inputs' in node:
                            node['inputs'][key] = prompt_text
                            injected = True
            elif injection_type == 'image':
                if image_path_to_inject:
                    widget_info = details['widget_info']
                    if widget_info['type'] == 'widgets_values':
                        idx = widget_info['index']
                        if 'widgets_values' in node and idx < len(node['widgets_values']):
                            node['widgets_values'][idx] = image_path_to_inject
                            injected = True
                    elif widget_info['type'] == 'inputs':
                        key = widget_info['key']
                        if 'inputs' in node:
                            node['inputs'][key] = image_path_to_inject
                            injected = True
            if injected:
                updated_count += 1
        return updated_count

    def _update_ui_with_segmented_prompts(self, segmented_data):
        """Helper to update the UI with segmented prompt data."""
        for i in reversed(range(self.positive_notebook.index('end'))):
            self.positive_notebook.forget(i)
        self.prompt_text_widgets.clear()
        for i in reversed(range(self.negative_notebook.index('end'))):
            self.negative_notebook.forget(i)
        self.negative_prompt_text_widgets.clear()
        workflow_filename = self.specific_workflow_var.get()
        analysis_data = self.workflow_analysis_cache.get(workflow_filename, {})
        summary_table = analysis_data.get('summary_table', [])
        added_positive_tabs = set()
        added_negative_tabs = set()
        for item in summary_table:
            full_node_name = item['full_node_name']
            modifier = item['prompt_properties']['modifier']
            prop_type = item['prompt_properties']['type']
            if prop_type == 'positive':
                if full_node_name not in added_positive_tabs:
                    positive_key = f'{modifier}_positive'
                    prompt_content = segmented_data.get(positive_key, '')
                    self.add_prompt_tab(full_node_name, prompt_content, height=9)
                    added_positive_tabs.add(full_node_name)
            elif prop_type == 'negative':
                if full_node_name not in added_negative_tabs:
                    negative_key = f'{modifier}_negative'
                    prompt_content = segmented_data.get(negative_key, '')
                    self.add_negative_prompt_tab(full_node_name, prompt_content, height=5)
                    added_negative_tabs.add(full_node_name)
        if not added_positive_tabs:
            self.add_prompt_tab('正文', segmented_data.get('base', ''), height=9)
        if not added_negative_tabs and segmented_data.get('negative'):
            self.add_negative_prompt_tab('负面提示词', segmented_data.get('negative', ''), height=5)

    def _find_comfyui_path(self):
        """
        在程序运行文件夹的前后三层内搜索 ComfyUI 文件夹。
        确保路径中不包含多余的 'proj'。
        """
        start_dir = os.path.dirname(os.path.abspath(__file__))
        current = start_dir
        for _ in range(4):
            candidate = os.path.join(current, 'ComfyUI')
            if os.path.isdir(candidate):
                if os.path.exists(os.path.join(candidate, 'main.py')) or os.path.exists(os.path.join(candidate, 'nodes.py')):
                    return candidate
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

        def search_down(path, depth):
            if depth > 3:
                return None
            try:
                items = os.listdir(path)
            except Exception:
                return None
            for item in items:
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    if item.lower() == 'comfyui':
                        if os.path.exists(os.path.join(full_path, 'main.py')) or os.path.exists(os.path.join(full_path, 'nodes.py')):
                            return full_path
                    res = search_down(full_path, depth + 1)
                    if res:
                        return res
            return None
        return search_down(start_dir, 1)

    def _init_watermark(self):
        """
        跨平台专家级镂空水印：针对 macOS M2 和 Windows 的深度兼容性修复
        """
        if not Image or not ImageTk:
            print('警告: 缺少 Pillow 库，水印功能不可用。')
            return
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            image_path = os.path.join(current_dir, 't1.png')
            if not os.path.exists(image_path):
                print(f'水印图片未找到: {image_path}')
                return
            is_mac = sys.platform == 'darwin'
            (ww, wh) = (60, 60)
            img = Image.open(image_path).convert('RGBA')
            try:
                resample_mode = Image.Resampling.LANCZOS
            except AttributeError:
                resample_mode = Image.LANCZOS
            img = img.resize((ww, wh), resample_mode)
            self._watermark_photo = ImageTk.PhotoImage(img)
            if hasattr(self, '_watermark_widget') and self._watermark_widget.winfo_exists():
                self._watermark_widget.destroy()
            self._watermark_widget = tk.Toplevel(self.root)
            wm = self._watermark_widget
            wm.overrideredirect(True)
            wm.attributes('-topmost', True)
            wm.config(bd=0, highlightthickness=0)
            if is_mac:
                bg_color = 'systemTransparent'
                wm.config(bg=bg_color)
                try:
                    wm.attributes('-transparent', True)
                    wm.attributes('-alpha', 1.0)
                except Exception:
                    pass
            else:
                bg_color = '#FF00FF'
                wm.attributes('-transparentcolor', bg_color)
                wm.configure(bg=bg_color)
            self._wm_canvas = tk.Canvas(wm, width=ww, height=wh, bg=bg_color, bd=0, highlightthickness=0)
            self._wm_canvas.pack(fill='both', expand=True)
            self._wm_canvas.create_image(ww // 2, wh // 2, image=self._watermark_photo)
            self._wm_canvas.image = self._watermark_photo
            self.root.update_idletasks()
            wm.update()
            wm.lift()
            wm.deiconify()
            rw = self.root.winfo_width()
            if rw <= 1:
                rw = 1200
            self._wm_rel_x = rw - ww - 40
            self._wm_rel_y = 40
            self._wm_canvas.bind('<Button-1>', self._start_wm_drag)
            self._wm_canvas.bind('<B1-Motion>', self._do_wm_drag)
            self._sync_wm_position()
            print(f'水印专家级修复完成 (原生透明模式): 系统={sys.platform}')
        except Exception as e:
            print(f'水印初始化异常: {e}')
            traceback.print_exc()

    def _sync_wm_position(self, event=None):
        """同步水印位置到主窗口右上角"""
        if not hasattr(self, '_watermark_widget') or not self._watermark_widget.winfo_exists():
            return
        try:
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            if rw <= 1:
                rw = 1200
            (ww, wh) = (60, 60)
            if not hasattr(self, '_wm_rel_x'):
                self._wm_rel_x = rw - ww - 25
            if not hasattr(self, '_wm_rel_y'):
                self._wm_rel_y = 25
            self._wm_rel_x = max(0, min(self._wm_rel_x, rw - ww))
            self._wm_rel_y = max(0, min(self._wm_rel_y, rh - wh))
            self._watermark_widget.geometry(f'+{rx + self._wm_rel_x}+{ry + self._wm_rel_y}')
            self._watermark_widget.lift()
        except Exception:
            pass

    def _start_wm_drag(self, event):
        self._wm_drag_offset_x = event.x
        self._wm_drag_offset_y = event.y

    def _do_wm_drag(self, event):
        try:
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            new_rel_x = event.x_root - rx - self._wm_drag_offset_x
            new_rel_y = event.y_root - ry - self._wm_drag_offset_y
            (ww, wh) = (60, 60)
            self._wm_rel_x = max(0, min(new_rel_x, rw - ww))
            self._wm_rel_y = max(0, min(new_rel_y, rh - wh))
            self._watermark_widget.geometry(f'+{rx + self._wm_rel_x}+{ry + self._wm_rel_y}')
        except Exception:
            pass

    def _ensure_watermark_integrity(self):
        try:
            if not hasattr(self, '_watermark_widget') or not self._watermark_widget.winfo_exists():
                self._init_watermark()
                return
            self._sync_wm_position()
            self._watermark_widget.attributes('-topmost', True)
        except Exception:
            pass
        finally:
            self.root.after(3000, self._ensure_watermark_integrity)

    def on_closing(self):
        """程序关闭时清理"""
        try:
            self.ollama_manager.stop_ollama()
        except Exception:
            pass
        self.root.destroy()

    def _convert_ui_to_api(self, workflow_data):
        """将 ComfyUI 的 UI 工作流格式 (含有 nodes 和 links) 转换为 API 格式 (Prompt)"""
        api_prompt = {}
        nodes = workflow_data.get('nodes', [])
        links = workflow_data.get('links', [])
        links_map = {link[0]: link for link in links}
        for node in nodes:
            node_id = str(node['id'])
            api_node = {'class_type': node['type'], 'inputs': {}}
            if 'inputs' in node and isinstance(node['inputs'], list):
                for inp in node['inputs']:
                    if 'link' in inp and inp['link'] is not None:
                        link_id = inp['link']
                        if link_id in links_map:
                            l = links_map[link_id]
                            api_node['inputs'][inp['name']] = [str(l[1]), l[2]]
                    elif 'value' in inp:
                        api_node['inputs'][inp['name']] = inp['value']
            if 'widgets_values' in node:
                w_values = node['widgets_values']
                if node['type'] == 'CLIPTextEncode' and len(w_values) > 0:
                    api_node['inputs']['text'] = w_values[0]
                elif node['type'] == 'LoadImage' and len(w_values) > 0:
                    api_node['inputs']['image'] = w_values[0]
                elif node['type'] == 'CheckpointLoaderSimple' and len(w_values) > 0:
                    api_node['inputs']['ckpt_name'] = w_values[0]
                elif node['type'] == 'EmptyLatentImage' and len(w_values) >= 2:
                    api_node['inputs']['width'] = w_values[0]
                    api_node['inputs']['height'] = w_values[1]
                elif node['type'] == 'KSampler' and len(w_values) >= 4:
                    api_node['inputs']['seed'] = w_values[0]
                    api_node['inputs']['steps'] = w_values[1]
                    api_node['inputs']['cfg'] = w_values[2]
                    api_node['inputs']['sampler_name'] = w_values[3]
                    if len(w_values) > 4:
                        api_node['inputs']['scheduler'] = w_values[4]
                    if len(w_values) > 5:
                        api_node['inputs']['denoise'] = w_values[5]
                else:
                    pass
            api_prompt[node_id] = api_node
        return api_prompt

    def run_comfyui_workflow(self):
        """向 ComfyUI 发送运行请求"""
        if not hasattr(self, 'current_injected_workflow_path') or not self.current_injected_workflow_path:
            messagebox.showerror('错误', '没有可运行的工作流。请先执行注入。')
            return
        workflow_path = self.current_injected_workflow_path
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_json = json.load(f)
        except Exception as e:
            messagebox.showerror('错误', f'无法读取注入后的工作流文件:\n{e}')
            return
        is_ui_format = 'nodes' in workflow_json and isinstance(workflow_json['nodes'], list)
        if is_ui_format:
            self.status_var.set('正在转换工作流格式 (UI -> API)...')
            try:
                workflow_json = self._convert_ui_to_api(workflow_json)
            except Exception as e:
                messagebox.showerror('转换失败', f'将工作流转换为 API 格式时出错:\n{e}')
                return
        comfyui_url = 'http://127.0.0.1:8188/prompt'
        client_id = str(uuid.uuid4())
        payload = {'prompt': workflow_json, 'client_id': client_id}
        self.status_var.set('正在发送工作流至 ComfyUI...')
        self.run_comfyui_button.config(state='disabled')
        self.preview_label.config(image='', text='正在连接 ComfyUI，请稍候...')
        self.preview_frame.pack(fill='both', expand=True, pady=(5, 0))
        self.root.update_idletasks()

        def send_request():
            try:
                response = requests.post(comfyui_url, json=payload, timeout=10)
                if response.status_code == 500:
                    error_data = response.text
                    self.root.after(0, lambda : messagebox.showerror('ComfyUI 服务器错误 (500)', f'ComfyUI 服务器拒绝了请求。这通常是因为节点输入缺失或格式不兼容。\n\n详细错误: {error_data}'))
                    self.root.after(0, lambda : self.run_comfyui_button.config(state='normal'))
                    self.root.after(0, lambda : self.status_var.set('ComfyUI 执行失败'))
                    return
                response.raise_for_status()
                data = response.json()
                prompt_id = data.get('prompt_id')
                if prompt_id:
                    self.root.after(0, lambda : self.status_var.set(f'已发送，正在生成 (ID: {prompt_id})...'))
                    self.root.after(0, lambda : self.preview_label.config(text=f'正在生成 (ID: {prompt_id})...\n请在 ComfyUI 控制台查看进度'))
                    self.poll_comfyui_result(prompt_id)
                else:
                    self.root.after(0, lambda : messagebox.showwarning('警告', 'ComfyUI 接受了请求但未返回 Prompt ID'))
                    self.root.after(0, lambda : self.run_comfyui_button.config(state='normal'))
            except requests.exceptions.RequestException as e:
                self.root.after(0, lambda : messagebox.showerror('连接失败', f'无法连接到 ComfyUI (127.0.0.1:8188)。请确保 ComfyUI 已启动。\n\n错误信息: {e}'))
                self.root.after(0, lambda : self.run_comfyui_button.config(state='normal'))
                self.root.after(0, lambda : self.status_var.set('ComfyUI 连接失败'))
        threading.Thread(target=send_request, daemon=True).start()

    def poll_comfyui_result(self, prompt_id):
        """轮询 ComfyUI 获取执行结果和生成的图像/视频"""
        comfyui_history_url = f'http://127.0.0.1:8188/history/{prompt_id}'

        def poll():
            max_attempts = 120
            attempts = 0
            while attempts < max_attempts:
                time.sleep(5)
                attempts += 1
                try:
                    res = requests.get(comfyui_history_url, timeout=5)
                    if res.status_code == 200:
                        history = res.json()
                        if prompt_id in history:
                            outputs = history[prompt_id].get('outputs', {})
                            generated_files = []
                            for (node_id, output_data) in outputs.items():
                                if 'images' in output_data:
                                    for img in output_data['images']:
                                        generated_files.append(img)
                                elif 'gifs' in output_data:
                                    for gif in output_data['gifs']:
                                        generated_files.append(gif)
                            self.root.after(0, lambda : self.on_comfyui_success(generated_files))
                            return
                except Exception as e:
                    print(f'轮询错误: {e}')
                    pass
            self.root.after(0, lambda : self.status_var.set('等待 ComfyUI 超时。'))
            self.root.after(0, lambda : self.run_comfyui_button.config(state='normal'))
        threading.Thread(target=poll, daemon=True).start()

    def on_comfyui_success(self, generated_files):
        """ComfyUI 执行成功回调，处理并显示预览"""
        self.status_var.set('ComfyUI 执行完毕！')
        self.run_comfyui_button.config(state='normal')
        if not generated_files:
            messagebox.showinfo('完成', 'ComfyUI 运行完成，但未找到输出图像或视频。')
            return
        first_file = generated_files[0]
        filename = first_file.get('filename')
        subfolder = first_file.get('subfolder', '')
        file_type = first_file.get('type', 'output')
        if not filename:
            return
        view_url = f'http://127.0.0.1:8188/view?filename={filename}&subfolder={subfolder}&type={file_type}'
        try:
            res = requests.get(view_url, timeout=10)
            res.raise_for_status()
            temp_dir = os.path.join(os.getcwd(), 'temp_preview')
            os.makedirs(temp_dir, exist_ok=True)
            local_path = os.path.join(temp_dir, filename)
            with open(local_path, 'wb') as f:
                f.write(res.content)
            self.current_preview_file = local_path
            self.preview_frame.pack(fill='both', expand=True, pady=(5, 0))
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                self.show_image_preview(local_path)
            else:
                self.preview_label.config(text=f'生成了视频/动图: {filename}\n(双击打开)')
            self.status_var.set(f'已生成: {filename} (双击预览框打开)')
        except Exception as e:
            print(f'下载预览文件失败: {e}')
            self.preview_label.config(text=f'已生成 {filename}，但在获取预览时失败。')

    def show_image_preview(self, image_path):
        """使用 PIL 缩放并显示预览图"""
        try:
            from PIL import Image, ImageTk
            img = Image.open(image_path)
            max_size = (400, 300)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.preview_label.image = photo
            self.preview_label.config(image=photo, text='')
        except ImportError:
            self.preview_label.config(text=f'已生成图片 (缺少 PIL 库无法预览)\n双击此处外部打开')
        except Exception as e:
            self.preview_label.config(text=f'图片预览失败\n{e}')

    def open_preview_file(self, event=None):
        """双击预览区域时使用系统默认程序打开文件"""
        if self.current_preview_file and os.path.exists(self.current_preview_file):
            try:
                if sys.platform == 'darwin':
                    subprocess.call(('open', self.current_preview_file))
                elif os.name == 'nt':
                    os.startfile(self.current_preview_file)
                elif os.name == 'posix':
                    subprocess.call(('xdg-open', self.current_preview_file))
                self.preview_frame.pack_forget()
                self.current_preview_file = None
            except Exception as e:
                messagebox.showerror('错误', f'无法打开文件: {e}')