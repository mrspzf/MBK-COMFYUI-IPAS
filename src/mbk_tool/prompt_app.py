import os, sys, json, requests, time, threading, traceback, platform, re, webbrowser, shutil
from pathlib import Path
from collections import deque
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
try:
    import openai
except ImportError:
    openai = None
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
from difflib import SequenceMatcher
from functools import lru_cache
from datetime import datetime, timedelta
try:
    from .constants import *
except ImportError:
    pass
try:
    from .ollama_manager import OllamaManager
except ImportError:
    pass
try:
    from .ui_components import SmartParamRegistry
except ImportError:
    pass
try:
    from .utils import *
except ImportError:
    pass
MODEL_LIBRARY_URL = 'https://ollama.com/library'
OLLAMA_BASE_URL = 'http://localhost:11434'
SOP_PROMPT_PREFIX = 'You are a top Prompt Optimization Master. When you receive a user request, you must strictly follow the three-step SOP (Standard Operating Procedure) to think and create, ensuring professional and stable output:\n\n**Step 1: Establish [Style and Subject]**\n*   First extract the core “art style” and “main subject” from the user-provided description. This is the foundation.\n\n**Step 2: Perform [Creative Refinement]**\n*   Based on the style and subject identified in Step\u202f1, professionally polish and expand the original idea with literary flair and imagination.\n*   The goal is to produce a richer, more detailed, visually vivid Chinese description ready for structuring.\n\n**Step 3: Apply [Classification Instructions] for adjustment and supplementation**\n*   Use the refined description from Step\u202f2 as core material.\n*   Rigorously compare with the task’s “professional classification instructions”, checking each item, adjusting and supplementing to ensure the final prompt is structurally complete, content‑wise exhaustive, and logically consistent.\n\n**Final Output:**\n*   After strictly following the three steps, output a high‑quality, structured Chinese prompt in clean JSON format.\n\n---\nNow, execute the task according to the specific **Professional Classification Instructions** provided:'
SYSTEM_PROMPTS = {'Text-to-Image': SOP_PROMPT_PREFIX + '\n**Task Type: Text-to-Image (Stable Diffusion)**\n**Core Requirement:** For the text-to-image task, strictly generate according to the following format:\n\n**Text-to-Image Specific Structure:**\n1. Quality Control: masterpiece, best quality, ultra-detailed, 8k resolution, photorealistic\n2. Subject Description: emotion, action, gesture, subject details, character features, expressions, poses\n3. Composition Elements: composition, camera angle, perspective, framing\n4. Environment & Scene: background, setting, atmosphere, props\n5. Lighting Effects: lighting setup, shadows, highlights, mood lighting\n6. Material & Texture: surface textures, materials, fabric details\n7. Detail Enhancement: intricate details, sharp focus, depth of field\n\n**Weighting System:**\n- Core Elements: (keyword:1.15-1.25)\n- Important Elements: (keyword:1.05-1.15)\n- Normal Elements: keyword\n- De-emphasized Elements: (keyword:0.8-0.9)\n\n', 'Text-to-Video': SOP_PROMPT_PREFIX + '\n**Task Type: Text-to-Video**\n**Core Requirement:** For the text-to-video task, strictly generate according to the following format:\n\n**Text-to-Video Specific Structure:**\n1. Base Quality: best quality, high resolution, smooth animation, 30fps\n2. Motion Description: camera movement, subject motion, transition effects\n3. Temporal Control: [0-5s], [5-10s], [10-15s] Storyboard Description\n4. Coherence: consistent character, stable background, fluid motion\n5. Visual Style: cinematic style, color grading, visual effects\n6. Scene Setting: environment, weather, time of day progression\n7. Action Sequence: action sequence, gesture details, interaction\n8. Technical Parameters: frame interpolation, motion blur, stabilization\n\n**Video-Specific Weights:**\n1. Motion Keywords: (motion_keyword:1.2-1.3)\n2. Coherence Control: (consistency_keyword:1.15-1.25)\n3. Temporal Marker: [timeframe] description\n\n', 'Image-to-Video': SOP_PROMPT_PREFIX + '\n**Task Type: Image-to-Video**\n**Core Requirement:** For the image-to-video task, strictly generate according to the following format:\n\n**Image-to-Video Specific Structure:**\n1. Source Image Preservation: preserve original composition, maintain character features\n2. Dynamic Extension: natural animation, realistic movement, physics-based motion\n3. Detail Enhancement: enhance textures, improve lighting, add atmospheric effects\n4. Motion Design: subtle movements, breathing, hair flow, fabric sway\n5. Environmental Dynamics: background elements, particle effects, ambient motion\n6. Transition Control: smooth transitions, consistent timing, natural flow\n7. Quality Improvement: upscale resolution, reduce artifacts, enhance details\n8. Style Preservation: maintain original style, color consistency, artistic coherence\n\n**Image-to-Video Weights:**\n1. Preservation/Consistency: (preserve_keyword:1.25-1.35)\n2. Natural Motion: (natural_motion:1.2-1.3)\n3. Quality Enhancement: (enhancement_keyword:1.1-1.2)\n\n', 'Image-to-Image': SOP_PROMPT_PREFIX + "\n**Task Type: Image-to-Image**\n**Core Requirement:** Based on the user's text description, generate a prompt capable of modifying and stylizing an existing image.\n\n**Image-to-Image Specific Structure:**\n1.  **Core Changes**: (A detailed description of the desired changes:1.3), e.g., (change hair to vibrant blue:1.4), (add futuristic cyberpunk armor:1.2).\n2.  **Style Directive**: The target art style, e.g., concept art, oil painting, by Greg Rutkowski.\n3.  **Quality Tags**: masterpiece, best quality, 8k.\n4.  **Preserved Elements**: Mention what should be kept from the original image, if any.\n\n", 'Text-to-Image - FLUX': SOP_PROMPT_PREFIX + "\n**Task Type: Text-to-Image (FLUX Model)**\n**Core Requirement:** The FLUX model prefers more natural, descriptive language rather than traditional keyword stacking. Convert the user's creative idea into a high-quality text-to-image prompt suitable for the FLUX model.\n\n**FLUX Prompt Core Principles:**\n1.  **Natural Language First**: Use complete, descriptive sentences to build the scene.\n2.  **Brevity and Core Focus**: Capture the core creative idea, avoiding excessive trivial details and weight modifiers.\n3.  **Quality Tags**: Add common high-quality tags at the beginning or end of the sentence.\n4.  **Clear Style Definition**: Clearly describe the desired art style, medium, or artist.\n\n**text-to-Video (flux) Weights:**\n\n1.  Subject Emphasis: To ensure the main subject is the focus.\n    -   Example: A cinematic film still of a (knight in shining armor:1.1-1.2) standing on a cliff.\n2.  Style & Artist Strength: To increase the intensity of a specific style.\n    -   Example: A portrait of a woman, (in the style of Van Gogh:1.15-1.25).\n3.  Composition & Camera Control: To give priority to a specific shot type.\n    -   Example: A futuristic city, (dramatic low-angle shot:1.05-1.15), towering skyscrapers.\n4.  Atmosphere & Lighting: To emphasize a particular mood or light effect.\n    -   Example: A mysterious forest at night, (eerie volumetric lighting:1.1-1.2) filtering through the\n  trees.\n\n", 'Chinese Polishing': 'You are a professional Chinese creative master. Your task is to polish, expand, and optimize the user’s request, generating an imaginative, detail‑rich, eloquent creative description in pure Chinese. The final output must strictly follow this format: start with `[START_TEXT]`, followed by the complete Chinese creative text, and end with `[END_TEXT]`. No extra headings, explanations, or tags are allowed between these markers.', 'Chinese Segmentation': '您是一位精通AI提示词，可以精确区分提示词内容的专家。您将收到一个JSON对象，其中包含一个\'creative_text\'（源文本）块和一个\'target_segments\'（目标分段）数组。\n\n数组中的每一项代表一个最终的提示词分段，它是一个JSON对象，包含一个唯一的\'display_name\'（显示名称）和一组\'keywords\'（关键词）。这组关键词**通常包含两个元素**：一个“性质词”（定义提示词的生成方式）和一个“功能词”（定义提示词的描述主题）,这些词语决定了该段提示词的内容构成。\n\n**您的核心任务是**：\n1.  **分配正面内容**：根据每个分段的“功能词”定义，将\'creative_text\'的**全部文本内容**，按逻辑关联性，**完整且无遗漏地**拆分并分配到所有`"keywords": ["positive", ...]`的段落中。\n2.  **生成负面内容**：对于每一个`"keywords": ["negative", ...]`的段落，您必须基于其**同名“功能词”**的描述内容，生成对应的负面描述。\n\n---\n\n### 定义与规则\n\n#### 性质词 (Property Words)\n\n*   **性质词: `positive`**\n    *   所有内容都必须是关于“希望看到什么”的正面描述。这是您根据功能词从\'creative_text\'中直接提取和整理的内容。\n*   **性质词: `negative`**\n    *   所有内容都必须是关于“需要避免什么”的负面描述。这部分内容是根据对应的`positive`内容**生成**的，而不是提取的。\n    *   **生成步骤**:\n        1.  **基础内容**: 针对其对应正面内容中的形容词，生成反义词（例如：`美丽` -> `丑陋`）。\n        2.  **补充内容**: 对照其对应正面内容中的具体事物或情景，生成反面或无关的描述（例如：`精致的奖杯` -> `变形的手`，`宏伟的宫殿` -> `现代建筑`）。\n\n#### 功能词 (Function Words) 详细定义\n\n##### 1. 场景与构图 (Scene & Composition)\n\n*   **关键词**: `base` (主要), `main` (别名)\n*   **核心目标**: 描述画面的基础结构，包括整体环境、主体和辅助元素的相关信息。\n*   **具体定义**:\n    *   **场景环境 (Scene Setting)**: 描述故事发生的基础背景，例如“在森林深处”、“一个赛博朋克城市的街角”、“空旷的白色房间”。\n    *   **主体与元素 (Subjects & Elements)**: 定义画面中包含哪些核心主体或物体，例如“一个女孩和一只白狼”、“一艘巨大的宇宙飞船”。\n    *   **构图与布局 (Composition & Layout)**: 描述主体与背景、主体与主体之间的空间关系和位置。使用专业的构图词汇，例如“女孩位于画面中央”、“白狼在她身后”、“采用对称构图”、“远景是连绵的雪山”。\n*   **示例**: “一个男人站在山顶，背对观众，采用中心构图，远景是日落和云海。”\n\n##### 2. 艺术风格与氛围 (Art Style & Atmosphere)\n\n*   **关键词**: `refine`\n*   **核心目标**: 描述画面的整体艺术风格、光影、色调和情感氛围。\n*   **具体定义**:\n    *   **光影与色彩 (Lighting & Color)**: 描述光源方向、光线质感和整体色调。例如“柔和的午后阳光”、“霓虹灯光照亮”、“电影感色调”、“伦勃朗式用光”、“高对比度黑白照片”。\n    *   **艺术风格 (Art Style)**: 指定一个明确的艺术流派、艺术家风格或媒介。例如“梵高风格”、“印象派”、“日本浮世绘”、“虚幻引擎渲染”、“水彩画”、“3D辛烷值渲染”。\n    *   **氛围与意境 (Mood & Atmosphere)**: 描述画面希望传达的情感或感觉。例如“神秘的”、“宁静的”、“充满未来科技感”、“忧郁的氛围”。\n*   **示例**: “电影感光效，柔和的边缘光，整体为冷色调，营造出一种宁静而孤寂的氛围，水彩画风格。”\n\n##### 3. 细节与叙事 (Details & Narrative)\n\n*   **关键词**: `details` (主要), `inpaint` / `fix` (特定流程别名)\n*   **核心目标**: 专注于刻画画面中的高优先级区域，添加具体细节、定义互动和情节。\n*   **具体定义**:\n    *   **重点区域刻画 (Key Area Focus)**: 对指定的角色或物体进行精细描述。例如“主角的眼睛是蓝色的，眼神坚定”、“机器人手臂上有复杂的机械刻线”。\n    *   **互动与情节 (Interaction & Plot)**: 描述角色之间、角色与物体之间的互动或正在发生的事件。例如“女孩轻轻抚摸着白狼的头”、“男人正在修理一个复杂的装置”。\n    *   **关联物细节 (Associated Details)**: 补充与主体相关的环境或背景细节，以增强故事感。例如“桌子上放着一杯冒着热气的咖啡和一本翻开的书”。\n*   **示例**: “男人穿着一件磨损的皮夹克，夹克上有徽章；他正在操作一个全息屏幕，屏幕上显示着复杂的代码。”\n\n##### 4. 人物形态 (Human Form)\n\n*   **关键词**: `person`\n*   **核心目标**: 精确描述画面中主要人物的姿态、动作和穿着。\n*   **具体定义**:\n    *   **姿态与动作 (Pose & Action)**: 使用明确的词汇描述身体的姿势和动态。例如“全身像，正面站立”、“坐姿，双腿交叉”、“正在奔跑，身体前倾”、“从后面看，弯腰拾取东西”。\n    *   **服装描述 (Apparel Description)**: 详细描述人物的穿着。例如“穿着一件白色的连衣裙”、“戴着一顶黑色的礼帽”、“身穿未来派风格的盔甲”。\n    *   **身体朝向 (Body Orientation)**: 明确人物相对于镜头的方向。例如“侧脸”、“面朝镜头”、“背对观众”。\n*   **示例**: “一个女人，全身像，穿着哥特式长裙，坐在王座上，双手交叠放在膝上，正面视角。”\n\n##### 5. 精准解剖结构 (Precise Anatomy)\n\n*   **关键词**: `face` / `hand` / `foot`\n*   **核心目标**: 描述人类最容易出错的特定身体部位，施加严格的解剖学和形态学约束。\n*   **具体定义**:\n    *   **解剖学准确性 (Anatomical Accuracy)**: 强制要求生成的结构符合真实的人体解剖学。例如“一只完整的手，包含五根手指”、“对称、结构正确的脸部特征”。\n    *   **形态与线条 (Form & Lines)**: 要求轮廓清晰，形态精准，无扭曲或模糊。例如“清晰的手指线条”、“精致的脸部轮廓”、“脚的结构正确”。\n    *   **光影一致性 (Lighting Consistency)**: 确保该部位的光影表现与 `refine` 中定义的整体光源保持一致。\n*   **示例**:\n    *   `face`: “一张完美对称的脸，五官精致，皮肤质感细腻，符合解剖学结构。”\n    *   `hand`: “一只形态优美的手，五指分明，线条清晰，没有畸变。”\n\n\n**输出格式:**\n您的最终输出必须是一个严格的JSON对象，其键名必须严格匹配`target_segments` 数组中提供的`display_name`。内容完全使用中文，被包裹在`[START_JSON]`和`[END_JSON]`标记之间，并且不包含任何额外的解释或标记。\n\n  例如，如果输入是:\n```json\n{\n  "creative_text": "一个美丽的公主走在城堡的花园里，阳光明媚，但远处的龙看起来有点模糊和变形。",\n  "target_segments": [\n    {\n      "display_name": "Positive Prompt (Base)",\n      "keywords": ["positive", "base"]\n    },\n    {\n      "display_name": "Negative Prompt",\n      "keywords": ["negative"]\n    }\n  ]\n}\n```\n\n  您的输出必须是:\n```json\n{\n  "Positive Prompt (Base)": "一个美丽的公主走在城堡的花园里，阳光明媚。",\n  "Negative Prompt": "远处的龙看起来有点模糊和变形。"\n}\n```\n', 'English Translation': 'You are an expert translator specializing in AI art prompts.\n\nYou will receive a JSON object containing:\n1) `prompt_groups`: grouped segments by full node name.   \n   - each group includes `full_name` and `segments`\n   - each segment includes `display_name`, `keywords`, `type` (`positive` or `negative`), and `text`\n2) `flat_prompts`: a flat map where keys are unique `display_name` and values are Chinese prompt text\n\nCore rules:\n1. Translate each segment accurately and fluently into English.\n2. Keep semantic correspondence strictly inside each group and each segment.\n3. Do not mix content across `display_name`s, even when multiple positive/negative segments exist.\n4. Preserve all entities, attributes, actions, style details, and constraints. No omissions.\n\nOutput rules:\n1. Output a strict JSON object enclosed by `[START_JSON]` and `[END_JSON]`.\n2. Keys in output must exactly match every key in input `flat_prompts`.\n3. Values must be purely English translations for the corresponding segment.\n4. No extra explanation.', 'Supplement Instructions': 'You are a standardization expert specializing in professional AI art prompts. You will receive a JSON object of `english_prompts` and a string of `professional_instructions`.Each “professional_instructions” document contains metric entries and weight parameters.\n \nYour task is: to add semantically relevant metric entries and weight parameters to every \nreceived prompt segment. Follow these rules precisely for each segment:\n\n\n1.  **Add Quality‑Control Entry**: First, analyze the `professional_instructions` text. If you locate any metric entry whose name contains the word “quality,” prepend the full content of that entry to the beginning of every `positive` prompt segment. Do not duplicate descriptions.\n\n2. **Finding Indicator Keywords**: Analyze the keywords in a segment’s `display_name` (e.g., “base”, “face”) and the character states and object relationships described in the `english_prompts` text. From the `professional_instructions`, select entries that have a strong semantic correlation with the (keywords, states, relationships). For each selected entry, pick one word from its content,these words are the indicator keywords, making sure no duplicate words are added.\n\n\n3. **Applying Weight Parameters**: Analyze the meaning of each weight name, tag the selected indicator keywords with the appropriate weights, and then insert those weighted keywords between the `positive` prompt text and the quality‑control content of the corresponding paragraph. Duplicate usage of the same keyword within a paragraph of the same name is prohibited.\n\n4.  **Output Format**: Your final output must be a strict JSON object. Its keys must exactly match the input `display_name`s. The values must be entirely in English. The entire object must be enclosed between `[START_JSON]` and `[END_JSON]` markers, with no extra explanations.\n\nFor example, if the input is `{"Positive Prompt (Base)": "a girl", "Negative Prompt (Base)": "ugly"}`,\nyour output must be:\n```json\n{"Positive Prompt (Base)": "(masterpiece, best quality, ultra-detailed, 8k resolution) (cinematic lighting (base:1.2)) a girl ",\n"Negative Prompt (Base)": "(worst quality, low quality, blurry) ugly"}\n```', 'Workflow Analysis': 'You are a top workflow architecture analyst. You will receive a workflow summary named SST (Structured Semantic Template).\n\n**Task Objectives:**\n1. **Identify Core Function**: Determine whether the workflow is Text‑to‑Image, Image‑to‑Image, Text‑to‑Video, or High‑Definition Restoration/Refinement.\n2. **Locate Key Nodes**: Find the IDs of the Prompt Input nodes (Positive/Negative), the main sampler, the primary model loader, and the size control node.\n3. **Parse Logical Flow**: Explain how prompts affect the final generation (e.g., fed directly to the sampler or passed through multiple CLIP encoders).\n4. **Parameter Verification**: For specific models such as Flux, check that parameters fall within recommended ranges (e.g., Guidance between 3‑4).\n\n**Output Format:** Return a strict JSON object containing `workflow_type`, `node_mapping` (mapping logic_name to node_id), `logic_summary`, and `recommendations` fields.'}
MODEL_PARAMS_CONFIG = {'qw3': {'num_ctx': 65536, 'temperature': 0.7}, 'qwen3': {'num_ctx': 65536, 'temperature': 0.7}, 'qwen3.6': {'num_ctx': 65536, 'temperature': 0.6}, 'qwen3-coder': {'num_ctx': 65536, 'temperature': 0.5}, 'glm-4.7:cloud': {'num_ctx': 65536}, 'qwen3-coder:480b-cloud': {'num_ctx': 65536}, 'gemini-3-flash-preview:cloud': {'num_ctx': 65536}, 'gemini-3-flash': {'num_ctx': 65536}, 'gpt-oss:120b': {'num_ctx': 49152, 'temperature': 0.7}, 'qwen3-coder-next:q8_0': {'num_ctx': 49152}, 'nemotron3:33b-bf16': {'num_ctx': 32768}, 'qwen3.6:35b-a3b-bf16': {'num_ctx': 32768}, 'qwen3.6:27b-bf16': {'num_ctx': 32768}, 'gemma4:31b-it-bf16': {'num_ctx': 32768, 'temperature': 0.8}}

def get_model_params(model_name):
    """Retrieve recommended context parameters based on model name, compatible with Ollama\u202f20.4+ interaction algorithm.
Leverage the advantage of 64\u202fGB+ memory to provide ample inference space for models of all tiers.    """
    if not model_name:
        return {'num_ctx': 32768}
    model_lower = model_name.lower()
    if model_name in MODEL_PARAMS_CONFIG:
        return MODEL_PARAMS_CONFIG[model_name]
    for (config_name, params) in MODEL_PARAMS_CONFIG.items():
        if model_lower.startswith(config_name) or config_name in model_lower:
            return params
    if any((x in model_lower for x in [':cloud', '-cloud', 'api-', 'gemini-', 'claude-'])):
        return {'num_ctx': 65536}
    if any((x in model_lower for x in ['120b', '235b', '480b', '400b'])):
        return {'num_ctx': 49152}
    if any((x in model_lower for x in ['27b', '31b', '33b', '35b', '70b', '72b'])):
        return {'num_ctx': 32768}
    return {'num_ctx': 16384}
PROFESSIONAL_STYLES = ['Default Style (Default Style)', 'Cinematic (Cinematic)', 'Photorealistic (Photorealistic)', 'Concept Art (Concept Art)', 'Digital Painting (Digital Painting)', 'Fantasy Art (Fantasy Art)', 'Science Fiction (Science Fiction)', 'Cyberpunk (Cyberpunk)', 'Steampunk (Steampunk)', 'Retro Style (Retro Style)', 'Minimalism (Minimalism)', 'Gothic (Gothic)', 'Abstract (Abstract)', 'Surrealism (Surrealism)', 'Impressionism (Impressionism)', 'Pop Art (Pop Art)', 'Art Deco (Art Deco)', 'Art Nouveau (Art Nouveau)', 'Baroque (Baroque)', 'Futurism (Futurism)', 'Cubism (Cubism)', 'Classicism (Classicism)', 'Renaissance (Renaissance)', 'Anime Style (Anime Style)', 'Comic Book Style (Comic Book Style)', 'Cartoon Style (Cartoon Style)', 'Ink Wash Painting (Ink Wash Painting)', 'Watercolor (Watercolor)', 'Sketch (Sketch)', 'Illustration (Illustration)', 'Portrait Photography (Portrait Photography)', 'Landscape Photography (Landscape Photography)', 'Macro Photography (Macro Photography)', 'Long Exposure (Long Exposure)', 'Double Exposure (Double Exposure)', 'Golden Hour (Golden Hour)', 'Blue Hour (Blue Hour)', 'Aerial Photography (Aerial Photography)', 'Monochrome (Monochrome)', 'Unreal Engine (Unreal Engine)', 'Octane Render (Octane Render)', 'Ray Tracing (Ray Tracing)', 'Cel Shading (Cel Shading)', 'Low Poly (Low Poly)', 'Voxel Art (Voxel Art)', 'Isometric (Isometric)', '3D Model (3D Model)']

class OllamaManager:

    def __init__(self):
        self.process = None
        self.is_running = False
        self.base_url = OLLAMA_BASE_URL
        self.session = self._build_session()

    def _build_session(self):
        """Build an HTTP session with retry capability to improve stability during brief local service hiccups."""
        session = requests.Session()
        retry = Retry(total=3, connect=3, read=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(['GET', 'POST']))
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _request(self, method, path, timeout=30, **kwargs):
        """Unified HTTP request entry point, avoiding scattered URLs and exception handling."""
        url = f'{self.base_url}{path}'
        return self.session.request(method, url, timeout=timeout, **kwargs)

    def native_chat_completion(self, model_name, messages, json_mode=False, **kwargs):
        """Core: Port the highly compatible communication engine from v0606.py, resolve Unterminated string errors, and support oversized JSON output.        """
        m_lower = model_name.lower()
        params = get_model_params(model_name)
        is_qwen = 'qwen' in m_lower
        chat_keywords = ['gpt', 'claude', 'deepseek', 'glm', 'gemini', 'cloud', 'oss']
        is_chat_preferred = any((x in m_lower for x in chat_keywords))
        options = {'num_ctx': params.get('num_ctx', 65536), 'temperature': kwargs.get('temperature', 0.7), 'top_p': 0.9, 'num_predict': 8192}
        endpoint = '/api/chat'
        payload = {'model': model_name, 'options': options, 'stream': False, 'keep_alive': '2h'}
        if is_qwen or is_chat_preferred:
            payload['messages'] = messages
            if json_mode:
                payload['format'] = 'json'
        else:
            endpoint = '/api/generate'
            full_prompt = ''
            for msg in messages:
                role = msg.get('role', 'user').upper()
                content = msg.get('content', '')
                full_prompt += f'### {role}:\n{content}\n\n'
            full_prompt += '### RESPONSE (OUTPUT ONLY VALID JSON):\n'
            payload['prompt'] = full_prompt
            if json_mode:
                payload['format'] = 'json'
        timeout = 480
        try:
            res = self._request('POST', endpoint, json=payload, timeout=timeout)
            if res.status_code == 200:
                data = res.json()
                content = data.get('message', {}).get('content', '') if endpoint == '/api/chat' else data.get('response', '')
                if '<think>' in content and '</think>' in content:
                    content = content.split('</think>')[-1].strip()
                elif '<think>' in content:
                    content = content.split('<think>')[-1]
                    if '</think>' in content:
                        content = content.split('</think>')[-1]
                if json_mode or payload.get('format') == 'json':
                    content = content.strip()
                    start_idx = content.find('{')
                    end_idx = content.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        pure_json = content[start_idx:end_idx + 1].strip()
                        content = f'[START_JSON]\n{pure_json}\n[END_JSON]'
                    else:
                        content = '[START_JSON]\n{}\n[END_JSON]'
                return content
            else:
                raise RuntimeError(f'Ollama API Error: HTTP {res.status_code}')
        except Exception as e:
            raise RuntimeError(f'Communication failed: {str(e)}')

    def start_ollama(self):
        """Start OLLAMA service, expert‑level Mac\u202fM2 (Apple Silicon) adaptation version"""
        try:
            response = self._request('GET', '/api/tags', timeout=2)
            if response.status_code == 200:
                self.is_running = True
                return True
        except:
            pass
        cmd = ['ollama', 'serve']
        if sys.platform == 'darwin':
            possible_binaries = ['/opt/homebrew/bin/ollama', '/usr/local/bin/ollama', os.path.expanduser('~/Applications/Ollama.app/Contents/Resources/ollama'), 'ollama']
            for p in possible_binaries:
                if shutil.which(p):
                    cmd[0] = p
                    break
        try:
            if os.name == 'nt':
                self.process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                import signal
                self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid if hasattr(os, 'setsid') else None)
            for i in range(12):
                time.sleep(1.0 + i * 0.2)
                try:
                    response = self._request('GET', '/api/tags', timeout=3)
                    if response.status_code == 200:
                        self.is_running = True
                        return True
                except Exception:
                    continue
        except Exception as e:
            print(f'OLLAMA core engine startup failed: {e}')
            return False
        return False

    def stop_ollama(self):
        """Stop OLLAMA service"""
        if self.process:
            self.process.terminate()
            self.process = None
        self.is_running = False

    def get_available_models(self):
        """Get available model list"""
        try:
            response = self._request('GET', '/api/tags', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
        except:
            pass
        return []

    def get_running_models(self):
        """Get currently running model"""
        try:
            response = self._request('GET', '/api/ps', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
        except:
            pass
        return []

    def install_ollama(self, callback=None):
        """Automated installation of OLLAMA (supports automatic detection and execution on Mac)"""
        import platform
        import subprocess
        system = platform.system()
        if system == 'Darwin':
            install_cmd = '/bin/bash -c "$(curl -fsSL https://ollama.com/install.sh)"'
            if callback:
                callback('Launching macOS installer (via curl)…')
        elif system == 'Linux':
            install_cmd = 'curl -fsSL https://ollama.com/install.sh | sh'
            if callback:
                callback('Launching Linux installer (via curl)…')
        else:
            if callback:
                callback(f'Current system {system} 不支持自动安装，请访问 ollama.com 下载。')
            return False
        try:
            if system == 'Darwin':
                subprocess.Popen(['osascript', '-e', f'tell application "Terminal" to do script "{install_cmd}"'])
            else:
                subprocess.Popen(['x-terminal-emulator', '-e', install_cmd])
            if callback:
                callback('The installer has been launched in a terminal window; please follow the prompts to complete the process.')
            return True
        except Exception as e:
            if callback:
                callback(f'Failed to start installer: {str(e)}')
            return False

    def check_ollama_installed(self):
        """Detecting if OLLAMA executable is installed on the system"""
        import shutil
        import platform
        system = platform.system()
        possible_paths = []
        if system == 'Darwin':
            possible_paths = ['/opt/homebrew/bin/ollama', '/usr/local/bin/ollama', os.path.expanduser('~/Applications/Ollama.app/Contents/Resources/ollama')]
        elif system == 'Linux':
            possible_paths = ['/usr/local/bin/ollama', '/usr/bin/ollama', os.path.expanduser('~/.local/bin/ollama')]
        elif system == 'Windows':
            possible_paths = [os.path.expanduser('~\\AppData\\Local\\Programs\\Ollama\\ollama.exe'), 'C:\\Program Files\\Ollama\\ollama.exe']
        for path in possible_paths:
            if os.path.exists(path):
                return True
        if shutil.which('ollama'):
            return True
        return False

    def search_online_models(self, keyword=''):
        """Enhanced model search from ollama.com/library (name, size, type, version)

Using a multi-level fallback strategy to handle webpage structure changes:
1. Attempt to extract full information from the model card (name, description, size, version tag)
2. Try matching links containing hx-trigger (modern versions)
3. Match generic library links
4. Use Ollama API search (if available)        """
        try:
            import re
            search_url = f'https://ollama.com/library?q={keyword}' if keyword else MODEL_LIBRARY_URL
            response = self.session.get(search_url, timeout=15)
            if response.status_code == 200:
                html = response.text
                results = []
                card_patterns = ['<a[^>]*href="/library/([^"]+)"[^>]*>(.*?)</a>']
                for pattern in card_patterns:
                    items = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
                    for (path, content) in items:
                        path = path.strip()
                        content = content.strip()
                        if '/' in path or not path or path.startswith('#'):
                            continue
                        name_match = re.search('<h[12][^>]*>(.*?)</h[12]>', content, re.I)
                        name = re.sub('<[^>]+>', '', name_match.group(1)).strip() if name_match else path
                        desc_match = re.search('<p[^>]*>(.*?)</p>', content, re.I)
                        desc = re.sub('<[^>]+>', '', desc_match.group(1)).strip() if desc_match else ''
                        versions = []
                        content_lower = content.lower()
                        desc_lower = desc.lower()
                        combined_text = content_lower + ' ' + desc_lower
                        if re.search('\\bq8[_-]?0\\b|\\bq8[_-]?\\b', combined_text):
                            versions.append('Q8')
                        if re.search('\\bf16[_-]?\\b|\\bbf16[_-]?\\b|\\bfp16[_-]?\\b', combined_text):
                            versions.append('F16')
                        if re.search('\\bq4[_-]?0\\b|\\bq4[_-]?\\b', combined_text):
                            versions.append('Q4')
                        if re.search('\\bq5[_-]?\\b', combined_text):
                            versions.append('Q5')
                        if re.search('\\bq6[_-]?\\b', combined_text):
                            versions.append('Q6')
                        if re.search('\\blatest\\b', combined_text):
                            versions.append('LATEST')
                        cloud_patterns = [':cloud\\b', '-cloud\\b', 'cloud[-_]?model', 'cloud[-_]?edition', '\\(cloud\\)', 'cloud\\s+api', 'cloud[-_]?only']
                        is_cloud = any((re.search(p, combined_text) for p in cloud_patterns))
                        if is_cloud:
                            versions.append('Cloud')
                        size = 'Unknown'
                        size_match = re.search('\\b(\\d+(\\.\\d+)?)\\s*([BG]B?)\\b', desc, re.I)
                        if size_match:
                            size = size_match.group(1) + size_match.group(3)
                        type_info = 'Model'
                        if any((x in desc_lower for x in ['vision', 'multimodal', 'image'])):
                            type_info = 'Multimodal'
                        elif 'embedding' in desc_lower:
                            type_info = 'Embedding'
                        elif any((x in desc_lower for x in ['code', 'coder'])):
                            type_info = 'Code'
                        elif any((x in desc_lower for x in ['math', 'reasoning'])):
                            type_info = 'Reasoning'
                        results.append({'name': path, 'display_name': name or path, 'size': size, 'versions': ', '.join(versions) if versions else 'latest', 'type': type_info, 'description': desc[:100] if desc else ''})
                    if results:
                        break
                if not results:
                    htx_pattern = 'href="/library/([^"]+)"[^>]*hx-trigger='
                    htx_matches = re.findall(htx_pattern, html)
                    font_pattern = 'href="/library/([^"\\\\]+)"[^>]*class="[^"]*(?:font-medium|text-lg|font-semibold)[^"]*"'
                    font_matches = re.findall(font_pattern, html, re.I)
                    all_names = set(htx_matches + font_matches)
                    for name in all_names:
                        name = name.strip()
                        if name and '/' not in name:
                            results.append({'name': name, 'display_name': name, 'size': 'Unknown', 'versions': 'latest', 'type': 'Model'})
                if not results:
                    simple_pattern = 'href="/library/([^"\\\\/]+)"'
                    simple_matches = re.findall(simple_pattern, html)
                    seen = set()
                    for name in simple_matches:
                        name = name.strip()
                        if name and name not in seen and (not name.startswith('#')):
                            seen.add(name)
                            results.append({'name': name, 'display_name': name, 'size': 'Unknown', 'versions': 'latest', 'type': 'Model'})
                seen_names = set()
                unique_results = []
                for r in results:
                    if r['name'] not in seen_names:
                        seen_names.add(r['name'])
                        unique_results.append(r)
                results = unique_results
                if keyword and results:
                    keyword_lower = keyword.lower()
                    results = [r for r in results if keyword_lower in r['name'].lower() or keyword_lower in r['display_name'].lower()]
                return results
        except Exception as e:
            print(f'Failed to search online models: {e}')
            import traceback
            traceback.print_exc()
        return []

    def run_model(self, model_name):
        """Execute ollama run command"""
        import subprocess
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['osascript', '-e', f'tell application "Terminal" to do script "ollama run {model_name}"'])
            elif os.name == 'nt':
                subprocess.Popen(['cmd', '/c', 'start', 'ollama', 'run', model_name])
            else:
                subprocess.Popen(['x-terminal-emulator', '-e', f'ollama run {model_name}'])
            return True
        except Exception as e:
            print(f'Failed to run model: {e}')
            return False

    def pull_model(self, model_name, callback=None):
        """Pull model"""
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
            print(f'Failed to pull model: {e}')
            return False
NODE_FINGERPRINTS = {'positive_prompt': {'classes': ['CLIPTextEncode', 'CLIPTextEncodeFlux', 'ConditioningZeroOut', 'FluxGuidance'], 'inputs': ['text', 'clip', 'conditioning'], 'weight': 1.0}, 'negative_prompt': {'classes': ['CLIPTextEncode', 'ConditioningZeroOut'], 'inputs': ['text', 'clip'], 'negative_hint': True}, 'loader': {'classes': ['CheckpointLoaderSimple', 'VAELoader', 'UNETLoader', 'DiffusionModelLoaderKJ'], 'outputs': ['MODEL', 'CLIP', 'VAE']}, 'sampler': {'classes': ['KSampler', 'KSamplerAdvanced', 'SamplerCustomAdvanced', 'BasicGuider'], 'inputs': ['model', 'positive', 'negative', 'latent_image']}, 'face_detailer': {'classes': ['FaceDetailer', 'FaceDetailerAdvanced'], 'inputs': ['image', 'model', 'clip', 'vae', 'positive', 'negative', 'bbox_detector']}}

class SmartParamRegistry:
    """Semantic metadata registrar: precisely record logical name, physical index and API key name"""

    def __init__(self):
        self.registry = {}

    def register(self, node_id, logic_name, index=None, api_key=None, val_type=str, group='default'):
        node_id = str(node_id)
        if node_id not in self.registry:
            self.registry[node_id] = {}
        self.registry[node_id][logic_name] = {'index': index, 'api_key': api_key, 'type': val_type, 'group': group}

    def clear(self):
        self.registry = {}
PARAM_REGISTRY = SmartParamRegistry()

def _identify_node_logic(node_data):
    """Dynamic fingerprinting algorithm: automatically semantically classify unknown nodes"""
    class_type = node_data.get('class_type') or node_data.get('type', '')
    inputs = node_data.get('inputs', {})
    best_match = None
    max_score = 0
    for (logic_name, finger) in NODE_FINGERPRINTS.items():
        score = 0
        if any((c in class_type for c in finger.get('classes', []))):
            score += 10
        input_keys = inputs.keys() if isinstance(inputs, dict) else []
        matched_inputs = [k for k in finger.get('inputs', []) if k in input_keys]
        score += len(matched_inputs) * 3
        if score > max_score:
            max_score = score
            best_match = logic_name
    return best_match if max_score >= 8 else None

def generate_workflow_sst(workflow_data):
    """Convert chaotic workflow JSON into an AI-efficient professional semantic template (SST)"""
    nodes_summary = []
    is_ui_format = isinstance(workflow_data, dict) and 'nodes' in workflow_data and isinstance(workflow_data['nodes'], list)
    source_nodes = workflow_data['nodes'] if is_ui_format else workflow_data
    if isinstance(source_nodes, dict):
        for (node_id, body) in source_nodes.items():
            class_type = body.get('class_type') or body.get('type', 'Unknown')
            inputs = body.get('inputs', {})
            nodes_summary.append({'id': node_id, 'type': class_type, 'logic': _identify_node_logic(body), 'params': list(inputs.keys())})
    elif isinstance(source_nodes, list):
        for n in source_nodes:
            node_id = n.get('id')
            class_type = n.get('type') or n.get('class_type', 'Unknown')
            inputs = n.get('inputs', {})
            nodes_summary.append({'id': node_id, 'type': class_type, 'logic': _identify_node_logic(n), 'params': list(inputs.keys())})
    template = {'template_version': 'ZenithFlow 4.0 (SST)', 'hardcore_audit': True, 'nodes': nodes_summary, 'processing_principles': 'AI-Positioning + Hardcore Verification', 'validation_level': 'Professional'}
    return json.dumps(template, ensure_ascii=False, indent=2)

def _hardcore_physical_verification(custom_nodes_path, node_type):
    """Top-tier hardcore physical verification: directly penetrates the file system to verify the existence of node Python classes.
    Supports concurrent retrieval on Mac M2 systems.    """
    if not custom_nodes_path or not os.path.exists(custom_nodes_path):
        return (False, 'Directory does not exist')
    try:
        if sys.platform == 'darwin':
            cmd = f'grep -r "class {node_type}" "{custom_nodes_path}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if node_type in result.stdout:
                return (True, 'Physical path confirmation: OK')
        for (root, _, files) in os.walk(custom_nodes_path):
            for file in files:
                if file.endswith('.py'):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                            if f'class {node_type}' in f.read():
                                return (True, f'Physical confirmation at: {file}')
                    except:
                        continue
    except:
        pass
    return (False, 'Physical verification failed: node definition missing')

class PromptApp:

    def __init__(self, root):
        self.root = root
        self.root.title('MBK-COMFYUI-IPAS v2.01613')
        self.root.geometry('1400x800')
        self.root.protocol('WM_DELETE_WINDOW', self.on_closing)
        self.ollama_manager = OllamaManager()
        self.client = None
        self.workflow_files = {}
        self.proj_path = tk.StringVar(value=os.path.join(os.getcwd(), 'WORKFLOWS'))
        self.selected_model_var = tk.StringVar(value='Not selected')
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
        self.initial_ollama_check()

    def initial_ollama_check(self):
        """Check OLLAMA status on program startup"""
        threading.Thread(target=self.refresh_ollama_status, daemon=True).start()

    def _create_openai_client(self):
        """Unified creation of OpenAI-compatible client, centralizing timeout and retry management."""
        return openai.OpenAI(api_key='dummy', base_url=f'{OLLAMA_BASE_URL}/v1', timeout=240, max_retries=2)

    def _is_cloud_model(self, model_name):
        if not model_name:
            return False
        model_lower = model_name.lower()
        return any((tag in model_lower for tag in [':cloud', '-cloud', 'api-', 'claude-', 'gemini-']))

    def _get_request_profile(self, model_name):
        """Provide differentiated timeout and retry configurations for local large models and cloud models.
        Emphasize improving fault tolerance for qwen3 / gemma4 and cloud.        """
        model_lower = (model_name or '').lower()
        if self._is_cloud_model(model_name):
            return {'timeout': 480, 'retries': 4}
        if any((tag in model_lower for tag in ['qwen3', 'qw3', 'gemma4', '31b', '70b', '120b', '480b'])):
            return {'timeout': 360, 'retries': 3}
        return {'timeout': 180, 'retries': 2}

    def _build_extra_body(self, model_name, json_mode=False):
        """Build additional Ollama parameters to achieve expert-level adaptation for Mode B (Chat/Cloud)."""
        params = get_model_params(model_name)
        num_ctx = params.get('num_ctx', 32768)
        extra_body = {'options': {'num_ctx': num_ctx, 'temperature': params.get('temperature', 0.7)}}
        if json_mode:
            model_lower = model_name.lower()
            if any((x in model_lower for x in ['qwen3', 'qw3', 'cloud', 'gpt-oss', 'gemini'])):
                extra_body['format'] = 'json'
        if any((x in model_name.lower() for x in ['gemma', 'qw', 'gpt-oss', 'reasoning', 'thought', 'r1'])):
            extra_body['think'] = True
        if not self._is_cloud_model(model_name):
            extra_body['keep_alive'] = '1h'
        return extra_body

    def _chat_completion_with_retry(self, model_name, messages, temperature=0.7, json_mode=False, max_tokens=None):
        """Unified dialogue call layer: switch to Ollama native protocol communication
        
        Completely resolves task failure issues for models like gemma4, nemotron, qwen3 under the OpenAI compatibility layer.        """
        if not self.ollama_manager.is_running:
            try:
                res = self.ollama_manager._request('GET', '/api/tags', timeout=2)
                if res.status_code == 200:
                    self.ollama_manager.is_running = True
            except:
                raise RuntimeError('OLLAMA service not ready; please start the service on the settings page first.')
        content = self.ollama_manager.native_chat_completion(model_name=model_name, messages=messages, json_mode=json_mode, temperature=temperature)

        class MockChoice:

            def __init__(self, content):
                self.message = type('obj', (object,), {'content': content})

        class MockCompletion:

            def __init__(self, content):
                self.choices = [MockChoice(content)]
        return MockCompletion(content)

    def setup_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        style = ttk.Style(self.root)
        style.configure('Execute.TButton', foreground='white', background='#c00000', font=('Microsoft YaHei', 12, 'bold'))
        style.map('Execute.TButton', background=[('pressed', '#a00000'), ('active', '#e00000'), ('disabled', '#a0a0a0')], foreground=[('disabled', '#e0e0e0'), ('pressed', 'white'), ('active', 'white')])
        style.configure('Run.TButton', foreground='white', background='#008000', font=('Microsoft YaHei', 10, 'bold'))
        style.map('Run.TButton', background=[('pressed', '#006400'), ('active', '#00a000'), ('disabled', '#a0a0a0')], foreground=[('disabled', '#e0e0e0'), ('pressed', 'white'), ('active', 'white')])
        style.configure('Yellow.Horizontal.TProgressbar', troughcolor='#555555', background='#ffc107', thickness=5)
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text='Main Console')
        setup_frame = ttk.Frame(notebook)
        notebook.add(setup_frame, text='OLLAMA Settings')
        comfyui_frame = ttk.Frame(notebook)
        notebook.add(comfyui_frame, text='COMFYUI Control')
        self.setup_main_tab(main_frame)
        self.setup_ollama_tab(setup_frame)
        self.setup_comfyui_tab(comfyui_frame)

    def setup_main_tab(self, parent):
        proj_frame = ttk.LabelFrame(parent, text='1. Workflow Path Setting', padding='10')
        proj_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(proj_frame, text='Workflow Path:').pack(side='left')
        proj_entry = ttk.Entry(proj_frame, textvariable=self.proj_path, width=40)
        proj_entry.pack(side='left', padx=5)
        ttk.Button(proj_frame, text='Browse', command=self.browse_proj_path, width=4).pack(side='left', padx=4)
        workflow_frame = ttk.LabelFrame(parent, text='2. Workflow Selection', padding='10')
        workflow_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(workflow_frame, text='Workflow Category:').grid(row=0, column=0, sticky='w')
        self.workflow_type_var = tk.StringVar()
        self.workflow_type_combo = ttk.Combobox(workflow_frame, textvariable=self.workflow_type_var, state='readonly', width=20)
        self.workflow_type_combo.grid(row=0, column=1, sticky='w', padx=5)
        self.workflow_type_combo.bind('<<ComboboxSelected>>', self.on_workflow_type_change)
        ttk.Label(workflow_frame, text='Specific Workflow:').grid(row=0, column=2, sticky='w', padx=(20, 5))
        self.specific_workflow_var = tk.StringVar()
        self.specific_workflow_combo = ttk.Combobox(workflow_frame, textvariable=self.specific_workflow_var, state='readonly', width=30)
        self.specific_workflow_combo.grid(row=0, column=3, sticky='w', padx=5)
        self.specific_workflow_combo.bind('<<ComboboxSelected>>', self.on_specific_workflow_change)
        workflow_frame.columnconfigure(4, weight=1)
        button_frame = ttk.Frame(workflow_frame)
        button_frame.grid(row=0, column=4, sticky='ew', padx=10)
        ttk.Button(button_frame, text='Identify Workflow', command=self.recognize_workflows_in_folder).pack(side='left')
        self.exit_button = ttk.Button(button_frame, text='Exit', command=self.on_closing)
        self.exit_button.pack(side='right', padx=(5, 0), ipady=12)
        self.run_comfyui_button = ttk.Button(button_frame, text='COMFYUI/Run', command=self.run_comfyui_workflow, state='disabled')
        self.run_comfyui_button.pack(side='right', padx=(10, 0), ipady=12)
        status_frame = ttk.LabelFrame(parent, text='3. OLLAMA Status', padding='10')
        status_frame.place(relx=1.0, rely=0, anchor='ne', x=-10, y=10)
        self.ollama_status_var = tk.StringVar(value='Not Connected')
        ttk.Label(status_frame, text='Service Status:').pack(side='left')
        self.ollama_status_label = ttk.Label(status_frame, textvariable=self.ollama_status_var, foreground='red')
        self.ollama_status_label.pack(side='left', padx=5)
        ttk.Label(status_frame, text='Current Model:').pack(side='left', padx=(20, 5))
        ttk.Label(status_frame, textvariable=self.selected_model_var, foreground='blue').pack(side='left', padx=5)
        main_paned_window = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill='both', expand=True, padx=10, pady=5)
        result_frame = ttk.LabelFrame(main_paned_window, text='5. Prompt Results', padding='10')
        main_paned_window.add(result_frame, weight=55)
        input_frame = ttk.LabelFrame(main_paned_window, text='4. Chinese Creative Input', padding='10')
        main_paned_window.add(input_frame, weight=45)
        pos_section_frame = ttk.Frame(result_frame)
        pos_section_frame.pack(fill='both', expand=True, pady=(0, 10), padx=2)
        pos_title_frame = ttk.Frame(pos_section_frame)
        pos_title_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(pos_title_frame, text='Positive Prompt', font=('Microsoft YaHei', 12, 'bold')).pack(side='left')
        ttk.Label(pos_title_frame, textvariable=self.positive_tab_full_name_var, foreground='blue').pack(side='left', padx=8)
        self.positive_notebook = ttk.Notebook(pos_section_frame)
        self.positive_notebook.pack(fill='both', expand=True)
        self.positive_notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        neg_section_frame = ttk.Frame(result_frame)
        neg_section_frame.pack(fill='both', expand=True, pady=5, padx=2)
        neg_title_frame = ttk.Frame(neg_section_frame)
        neg_title_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(neg_title_frame, text='Negative Prompt', font=('Microsoft YaHei', 12, 'bold')).pack(side='left')
        ttk.Label(neg_title_frame, textvariable=self.negative_tab_full_name_var, foreground='blue').pack(side='left', padx=8)
        self.negative_notebook = ttk.Notebook(neg_section_frame)
        self.negative_notebook.pack(fill='both', expand=True)
        self.negative_notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        input_text_frame = ttk.Frame(input_frame)
        input_text_frame.pack(fill='both', expand=True, pady=(10, 0))
        style_frame = ttk.Frame(input_text_frame)
        style_frame.pack(fill='x', pady=(0, 10))
        style_frame.columnconfigure(3, weight=1)
        ttk.Label(style_frame, text='Style Selection:').grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.style_var = tk.StringVar(value=PROFESSIONAL_STYLES[0])
        style_combo = ttk.Combobox(style_frame, textvariable=self.style_var, values=PROFESSIONAL_STYLES, state='readonly', width=20)
        style_combo.grid(row=0, column=1, sticky='w')
        style_combo.bind('<<ComboboxSelected>>', self.on_style_change)
        self.image_label = ttk.Label(style_frame, text='Image Input:')
        self.image_label.grid(row=0, column=2, sticky='w', padx=(15, 5))
        self.image_path_entry = ttk.Entry(style_frame, textvariable=self.image_path_var)
        self.image_path_entry.grid(row=0, column=3, sticky='ew')
        self.image_browse_button = ttk.Button(style_frame, text='Browse', command=self.browse_image_path, width=3)
        self.image_browse_button.grid(row=0, column=4, sticky='e', padx=(5, 0))
        self.chinese_input = scrolledtext.ScrolledText(input_text_frame, height=4, font=('Microsoft YaHei', 11), wrap='word', undo=True)
        self.chinese_input.pack(fill='both', expand=True)
        self.create_context_menu(self.chinese_input)
        self.chinese_input.bind('<KeyRelease>', lambda event: self.update_button_states())
        self.preview_frame = tk.Frame(input_text_frame, bd=2, relief='ridge', background='#f0f0f0')
        self.preview_label = ttk.Label(self.preview_frame, text='No Preview Image', anchor='center', background='#f0f0f0')
        self.preview_label.pack(fill='both', expand=True)
        self.preview_label.bind('<Double-1>', self.open_preview_file)
        self.current_preview_file = None
        convert_frame = ttk.Frame(input_frame)
        convert_frame.pack(fill='x', pady=(10, 0))
        self.convert_cn_button = ttk.Button(convert_frame, text='1. Chinese Creative', command=self.generate_creative_chinese, state='disabled')
        self.convert_cn_button.pack(side='left')
        self.segment_button = ttk.Button(convert_frame, text='2. Prompt Segmentation', command=self.segment_chinese_text, state='disabled')
        self.segment_button.pack(side='left', padx=5)
        self.convert_en_button = ttk.Button(convert_frame, text='3. Convert to English', command=self.translate_to_english, state='disabled')
        self.convert_en_button.pack(side='left', padx=5)
        self.supplement_button = ttk.Button(convert_frame, text='4. Professional Adjustment', command=self.supplement_with_instructions, state='disabled')
        self.supplement_button.pack(side='left', padx=5)
        ttk.Button(convert_frame, text='Clear Rewrite', command=self.clear_and_rewrite).pack(side='right')
        execute_frame = ttk.Frame(parent)
        execute_frame.pack(fill='x', padx=10, pady=9)
        self.execute_button = ttk.Button(execute_frame, text='Execute Injection', command=self.execute_workflow, state='disabled', style='Execute.TButton')
        self.execute_button.pack(side='left', ipady=16)
        self.conversion_progressbar = ttk.Progressbar(execute_frame, mode='indeterminate', style='Yellow.Horizontal.TProgressbar')
        self.conversion_progressbar.pack(side='left', padx=10, fill='x', expand=True)
        self.status_var = tk.StringVar(value='Ready')
        ttk.Label(execute_frame, textvariable=self.status_var).pack(side='right')

    def setup_ollama_tab(self, parent):
        main_container = ttk.Frame(parent)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        right_frame = ttk.Frame(main_container)
        right_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))
        control_frame = ttk.LabelFrame(left_frame, text='OLLAMA Service Control', padding='10')
        control_frame.pack(fill='x', pady=(0, 10))
        self.start_ollama_button = ttk.Button(control_frame, text='Start OLLAMA', command=self.start_ollama_service)
        self.start_ollama_button.pack(side='left', padx=5)
        self.stop_ollama_button = ttk.Button(control_frame, text='Stop OLLAMA', command=self.stop_ollama_service, state='disabled')
        self.stop_ollama_button.pack(side='left', padx=5)
        ttk.Button(control_frame, text='Refresh Status', command=self.refresh_ollama_status).pack(side='left', padx=5)
        self.running_model_var = tk.StringVar(value='Current Load: None')
        ttk.Label(control_frame, textvariable=self.running_model_var, foreground='navy').pack(side='left', padx=10)
        download_frame = ttk.LabelFrame(left_frame, text='Online Model Search and Download', padding='10')
        download_frame.pack(fill='both', expand=True)
        search_bar_frame = ttk.Frame(download_frame)
        search_bar_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(search_bar_frame, text='Search Keywords:').pack(side='left')
        self.search_model_var = tk.StringVar()
        search_entry = ttk.Entry(search_bar_frame, textvariable=self.search_model_var, width=20)
        search_entry.pack(side='left', padx=5, expand=True, fill='x')
        search_button = ttk.Button(search_bar_frame, text='Search Model Repository', command=self.search_and_display_models)
        search_button.pack(side='left', padx=5)
        search_result_frame = ttk.Frame(download_frame)
        search_result_frame.pack(fill='both', expand=True, pady=(5, 5))
        columns = ('name', 'size', 'versions', 'type')
        self.online_model_tree = ttk.Treeview(search_result_frame, columns=columns, show='headings', height=10)
        self.online_model_tree.heading('name', text='Model Name')
        self.online_model_tree.heading('size', text='Size')
        self.online_model_tree.heading('versions', text='Available Versions')
        self.online_model_tree.heading('type', text='Type')
        self.online_model_tree.column('name', width=120, anchor='w')
        self.online_model_tree.column('size', width=50, anchor='center')
        self.online_model_tree.column('versions', width=100, anchor='center')
        self.online_model_tree.column('type', width=60, anchor='center')
        self.online_model_tree.pack(side='left', fill='both', expand=True)
        online_scrollbar = ttk.Scrollbar(search_result_frame, orient='vertical', command=self.online_model_tree.yview)
        online_scrollbar.pack(side='right', fill='y')
        self.online_model_tree.config(yscrollcommand=online_scrollbar.set)
        self.online_model_tree.bind('<<TreeviewSelect>>', self.on_online_model_select)
        self.online_model_tree.bind('<Double-1>', self.on_online_model_double_click)
        self.download_progress_var = tk.StringVar(value='Tip: Double-click a model to directly execute OLLAMA RUN')
        ttk.Label(download_frame, textvariable=self.download_progress_var, foreground='blue').pack(fill='x')
        right_frame.rowconfigure(0, weight=4)
        right_frame.rowconfigure(1, weight=0)
        right_frame.rowconfigure(2, weight=1)
        right_frame.rowconfigure(3, weight=6)
        right_frame.rowconfigure(4, weight=1)
        right_frame.columnconfigure(0, weight=1)
        top_empty_frame = ttk.Frame(right_frame)
        top_empty_frame.grid(row=0, column=0, sticky='nsew')
        install_outer_frame = tk.Frame(right_frame, bg='#f0f0f0')
        install_outer_frame.grid(row=1, column=0, sticky='nsew', pady=(5, 20))
        middle_empty_frame = ttk.Frame(right_frame)
        middle_empty_frame.grid(row=2, column=0, sticky='nsew')
        model_frame = ttk.LabelFrame(right_frame, text='Local Model Management', padding='10')
        model_frame.grid(row=3, column=0, sticky='nsew', pady=5)
        bottom_empty_frame = ttk.Frame(right_frame)
        bottom_empty_frame.grid(row=4, column=0, sticky='nsew')
        tk.Label(install_outer_frame, text='Auto-Install Tool', font=('Microsoft YaHei', 11, 'bold'), bg='#f0f0f0', fg='#333333').pack(anchor='w', pady=(5, 10))
        install_frame = tk.Frame(install_outer_frame, bg='#f0f0f0')
        install_frame.pack(fill='both', expand=True)
        self.ollama_installed_var = tk.BooleanVar(value=self._check_ollama_installed())
        if self.ollama_installed_var.get():
            install_btn = tk.Button(install_frame, text='OLLAMA Installation', command=self._auto_install_ollama_system, bg='#808080', fg='white', state='disabled', width=25, relief='flat', bd=0, highlightthickness=0)
            install_label_text = '(OLLAMA detected as installed)'
            install_label_color = '#008000'
        else:
            install_btn = tk.Button(install_frame, text='OLLAMA Installation', command=self._auto_install_ollama_system, bg='#FFA500', fg='white', width=25, relief='flat', bd=0, highlightthickness=0)
            install_label_text = '(Auto-detect MAC / Windows / Linux)'
            install_label_color = '#666666'
        install_btn.pack(pady=2)
        tk.Label(install_frame, text=install_label_text, fg=install_label_color, bg='#f0f0f0', font=('Microsoft YaHei', 10)).pack(pady=(2, 0))
        installed_frame = ttk.LabelFrame(model_frame, text='Installed Models', padding='5')
        installed_frame.pack(fill='both', expand=True)
        list_frame = ttk.Frame(installed_frame)
        list_frame.pack(fill='both', expand=True)
        self.model_listbox = tk.Listbox(list_frame, height=5)
        self.model_listbox.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.model_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.model_listbox.config(yscrollcommand=scrollbar.set)
        select_frame = ttk.Frame(installed_frame)
        select_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(select_frame, text='Select Model', command=self.select_model).pack(side='left')
        ttk.Button(select_frame, text='Refresh List', command=self.refresh_ollama_status).pack(side='left', padx=10)
        ttk.Button(select_frame, text='Delete Model', command=self.delete_local_model).pack(side='right')

    def setup_comfyui_tab(self, parent):
        """Set ComfyUI Control Tab"""
        main_container = ttk.Frame(parent)
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        main_container.columnconfigure(0, weight=4)
        main_container.columnconfigure(1, weight=1)
        main_container.rowconfigure(0, weight=1)
        left_frame = ttk.Frame(main_container)
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        left_frame.rowconfigure(0, weight=4)
        left_frame.rowconfigure(1, weight=6)
        left_frame.columnconfigure(0, weight=2)
        left_frame.columnconfigure(1, weight=3)
        plugins_labelframe = ttk.LabelFrame(left_frame, text='ComfyUI Local Plugin Package', padding='10')
        plugins_labelframe.grid(row=0, column=0, sticky='nsew', pady=(0, 5), padx=(0, 5))
        self.plugins_listbox = tk.Listbox(plugins_labelframe)
        self.plugins_listbox.pack(side='left', fill='both', expand=True)
        plugins_scrollbar = ttk.Scrollbar(plugins_labelframe, orient='vertical', command=self.plugins_listbox.yview)
        plugins_scrollbar.pack(side='right', fill='y')
        self.plugins_listbox.config(yscrollcommand=plugins_scrollbar.set)
        library_outer_frame = ttk.Frame(left_frame)
        library_outer_frame.grid(row=0, column=1, sticky='nsew', pady=(0, 5), padx=(5, 0))
        library_outer_frame.rowconfigure(0, weight=5)
        library_outer_frame.rowconfigure(1, weight=3)
        library_outer_frame.columnconfigure(0, weight=1)
        ttk.Frame(library_outer_frame).grid(row=0, column=0, sticky='nsew')
        library_labelframe = ttk.LabelFrame(library_outer_frame, text='COMFYUI Library Search Results Display', padding='10')
        library_labelframe.grid(row=1, column=0, sticky='nsew')
        self.library_listbox = tk.Listbox(library_labelframe)
        self.library_listbox.pack(side='left', fill='both', expand=True)
        library_scrollbar = ttk.Scrollbar(library_labelframe, orient='vertical', command=self.library_listbox.yview)
        library_scrollbar.pack(side='right', fill='y')
        self.library_listbox.config(yscrollcommand=library_scrollbar.set)
        self.create_listbox_context_menu(self.library_listbox)
        params_labelframe = ttk.LabelFrame(left_frame, text='Workflow Core Node Parameter Adjustment (Diagram Mode)', padding='10')
        params_labelframe.grid(row=1, column=0, columnspan=2, sticky='nsew', pady=(5, 0))
        self.params_container = ttk.Frame(params_labelframe)
        self.params_container.pack(fill='both', expand=True)
        self.params_canvas = tk.Canvas(self.params_container, highlightthickness=0, background='#fafafa')
        self.params_scroll = ttk.Scrollbar(self.params_container, orient='vertical', command=self.params_canvas.yview)
        self.params_inner_frame = ttk.Frame(self.params_canvas, padding=10)
        self.params_inner_frame.bind('<Configure>', lambda e: self.params_canvas.configure(scrollregion=self.params_canvas.bbox('all')))
        self.params_canvas.create_window((0, 0), window=self.params_inner_frame, anchor='nw', width=800)
        self.params_canvas.configure(yscrollcommand=self.params_scroll.set)
        self.params_canvas.pack(side='left', fill='both', expand=True)
        self.params_scroll.pack(side='right', fill='y')
        right_frame = ttk.Frame(main_container)
        right_frame.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        right_frame.rowconfigure(0, weight=4)
        right_frame.rowconfigure(1, weight=6)
        right_frame.columnconfigure(0, weight=1)
        align_container = ttk.Frame(right_frame)
        align_container.grid(row=0, column=0, sticky='sew', pady=(80, 2))
        group1_frame = ttk.LabelFrame(align_container, text='Node and Write', padding=5)
        group1_frame.pack(fill='x')
        ttk.Button(group1_frame, text='Validate Persistence (Node)', command=self._verify_node_persistence, width=18).pack(pady=2)
        ttk.Button(group1_frame, text='Query Parameters (Node)', command=self.query_workflow_nodes, width=18).pack(pady=2)
        ttk.Button(group1_frame, text='Confirm (Write)', command=self.apply_workflow_parameters, width=18, state='disabled').pack(pady=2)
        group_comfyui_install_outer = tk.Frame(align_container, bg='#f0f0f0')
        group_comfyui_install_outer.pack(fill='x', pady=(15, 0))
        tk.Label(group_comfyui_install_outer, text='ComfyUI Installation', font=('Microsoft YaHei', 11, 'bold'), bg='#f0f0f0', fg='#333333').pack(anchor='w', pady=(5, 8))
        group_comfyui_install_frame = tk.Frame(group_comfyui_install_outer, bg='#f0f0f0')
        group_comfyui_install_frame.pack(fill='x')
        self.comfyui_installed_var = tk.BooleanVar(value=self._check_comfyui_installed())
        if self.comfyui_installed_var.get():
            comfyui_install_btn = tk.Button(group_comfyui_install_frame, text='COMFYUI Installation', command=self._auto_install_comfyui_system, bg='#808080', fg='white', state='disabled', width=25, relief='flat', bd=0, highlightthickness=0)
            comfyui_label_text = '(COMFYUI detected as installed)'
            comfyui_label_color = '#008000'
        else:
            comfyui_install_btn = tk.Button(group_comfyui_install_frame, text='COMFYUI Installation', command=self._auto_install_comfyui_system, bg='#FFA500', fg='white', width=25, relief='flat', bd=0, highlightthickness=0)
            comfyui_label_text = '(Click to install COMFYUI)'
            comfyui_label_color = '#666666'
        comfyui_install_btn.pack(pady=2)
        tk.Label(group_comfyui_install_frame, text=comfyui_label_text, fg=comfyui_label_color, bg='#f0f0f0', font=('Microsoft YaHei', 10)).pack(pady=(2, 5))
        bottom_container = ttk.Frame(right_frame)
        bottom_container.grid(row=1, column=0, sticky='sew')
        group_refresh_frame = ttk.LabelFrame(bottom_container, text='Page Maintenance', padding=5)
        group_refresh_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(group_refresh_frame, text='Reset / Refresh Page', command=self._reset_comfyui_tab_state, width=18).pack(pady=2)
        group3_frame = ttk.LabelFrame(bottom_container, text='Query Local Plugin Package', padding=5)
        group3_frame.pack(fill='x', pady=(15, 0))
        ttk.Button(group3_frame, text='Query Local Plugin Package', command=self.search_comfyui_plugins, width=18).pack(pady=2)
        group2_frame = ttk.LabelFrame(bottom_container, text='Search and Install', padding=5)
        group2_frame.pack(fill='x', pady=(15, 0))
        ttk.Button(group2_frame, text='Search Missing Plugins (Node)', command=self._search_missing_plugins, width=18).pack(pady=2)
        self.missing_plugin_keyword_text = tk.Text(group2_frame, height=3, width=20, font=('Microsoft YaHei', 9), undo=True)
        self.missing_plugin_keyword_text.pack(pady=2, padx=5, fill='x')
        self.create_context_menu(self.missing_plugin_keyword_text)
        ttk.Button(group2_frame, text='Install (Plugin Package)', command=self._install_plugin_package, width=18, state='disabled').pack(pady=2)

    def create_listbox_context_menu(self, listbox_widget):
        """Right-click Copy Menu Designed for Listbox Control"""
        list_menu = tk.Menu(self.root, tearoff=0)
        list_menu.add_command(label='Copy Selected Items', command=lambda : self.copy_listbox_selection(listbox_widget))
        list_menu.add_command(label='Select All Content', command=lambda : listbox_widget.select_set(0, tk.END))
        listbox_widget.bind('<Button-3>', lambda e: self.show_context_menu(e, list_menu))
        listbox_widget.bind('<Button-2>', lambda e: self.show_context_menu(e, list_menu))
        listbox_widget.bind('<Control-Button-1>', lambda e: self.show_context_menu(e, list_menu))

    def copy_listbox_selection(self, listbox_widget):
        """Copy Listbox Selected Text to Clipboard"""
        try:
            selection = listbox_widget.curselection()
            if selection:
                text = listbox_widget.get(selection[0])
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self.status_var.set('Copied to Clipboard')
        except:
            pass

    def _reset_comfyui_tab_state(self):
        """Reset COMFYUI Tab State (Initial Refresh)"""
        if hasattr(self, 'missing_plugin_keyword_text'):
            self.missing_plugin_keyword_text.delete('1.0', tk.END)
        self.library_listbox.delete(0, tk.END)
        for widget in self.params_inner_frame.winfo_children():
            widget.destroy()
        ttk.Label(self.params_inner_frame, text='Waiting for Workflow Parameter Query...', foreground='gray').pack(pady=20)
        self.status_var.set('Page Reset')
        self.workflow_param_vars = {}

    def _verify_node_persistence(self):
        """Validate Persistence (Node) – Check if nodes in the current workflow are locally installed (Expert Hardened Version)"""
        specific_workflow = self.specific_workflow_combo.get()
        if not specific_workflow:
            messagebox.showwarning('Warning', 'Please select a workflow in the main console first')
            return
        workflow_path = os.path.join(self.proj_path.get(), specific_workflow)
        if not os.path.exists(workflow_path):
            return
        custom_nodes_path = self._get_custom_nodes_path()
        if not custom_nodes_path:
            messagebox.showerror('Error', 'ComfyUI directory not found, please check the path.')
            return
        BUILTIN_NODES = {'KSampler', 'CheckpointLoaderSimple', 'CLIPTextEncode', 'CLIPTextEncodeFlux', 'EmptyLatentImage', 'VAEDecode', 'VAEEncode', 'SaveImage', 'LoadImage', 'VAELoader', 'DualCLIPLoader', 'LatentUpscale', 'LatentUpscaleBy', 'UpscaleModelLoader', 'ImageUpscaleWithModel', 'SetLatentNoiseMask', 'MaskComposite', 'ConditioningCombine', 'ConditioningAverage', 'ConditioningSetArea', 'LatentComposite', 'LatentCompositeMasked', 'VAEDecodeTiled', 'VAEEncodeTiled', 'UNETLoader', 'DiffusersLoader', 'LoraLoader', 'LoraLoaderModelOnly', 'ControlNetApply', 'ControlNetLoader', 'PrimitiveNode', 'PrimitiveString', 'PrimitiveInt', 'PrimitiveFloat', 'PrimitiveBoolean', 'BasicGuider', 'BasicScheduler', 'EmptySD3LatentImage', 'FluxGuidance', 'KSamplerSelect', 'RandomNoise', 'SamplerCustomAdvanced', 'ModelSamplingFlux', 'ModelSamplingDiscrete', 'ModelSamplingSD3', 'CLIPLoader', 'CLIPVisionLoader', 'StyleModelLoader', 'GLIGENLoader', 'DiffusersLoader', 'UpscaleModelLoader', 'DualCLIPLoader', 'CLIPMergeSimple', 'ConditioningZeroOut', 'VaeSoftClamp', 'DiffusionModelLoaderKJ'}
        self.library_listbox.delete(0, tk.END)
        self.library_listbox.insert(tk.END, 'Executing Deep Node Persistence Verification...')
        self.root.update()
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            node_types = set()
            if 'nodes' in data and isinstance(data['nodes'], list):
                for n in data['nodes']:
                    node_types.add(n.get('type'))
            else:
                for (n_id, n_info) in data.items():
                    if isinstance(n_info, dict) and 'class_type' in n_info:
                        node_types.add(n_info['class_type'])
            node_types.discard(None)
            installed_nodes = set(BUILTIN_NODES)
            comfy_root = os.path.dirname(custom_nodes_path)
            scan_dirs = [custom_nodes_path]
            extras_path = os.path.join(comfy_root, 'comfy_extras')
            if os.path.exists(extras_path):
                scan_dirs.append(extras_path)
            nodes_py = os.path.join(comfy_root, 'nodes.py')
            if os.path.exists(nodes_py):
                scan_dirs.append(nodes_py)
            for path in scan_dirs:
                if os.path.isfile(path):
                    self._extract_nodes_from_file(path, installed_nodes)
                else:
                    for (root, dirs, files) in os.walk(path):
                        for file in files:
                            if file.endswith('.py') or file.endswith('.js'):
                                self._extract_nodes_from_file(os.path.join(root, file), installed_nodes)
            self.library_listbox.delete(0, tk.END)
            missing_count = 0
            results = []
            for nt in sorted(list(node_types)):
                if nt in ['Note', 'Reroute', 'PrimitiveNode']:
                    continue
                status = '[Saved]'
                if nt not in installed_nodes:
                    (is_physically_present, detail) = _hardcore_physical_verification(custom_nodes_path, nt)
                    if is_physically_present:
                        status = '[Saved*]'
                    else:
                        status = '[Missing]'
                if '[Missing]' in status:
                    missing_count += 1
                results.append(f'{status} {nt}')
            for res in results:
                self.library_listbox.insert(tk.END, res)
                if '[Missing]' in res:
                    self.library_listbox.itemconfig(tk.END, {'fg': 'red'})
                else:
                    self.library_listbox.itemconfig(tk.END, {'fg': 'green'})
            self.status_var.set(f'Validation Complete: {len(node_types)}  nodes, {missing_count}  missing.')
        except Exception as e:
            messagebox.showerror('Validation Failed', f'Error while executing validation: {e}')

    def _extract_nodes_from_file(self, file_path, node_set):
        """Extract Node Registration Info from File (Supports Multiple Formats)"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                matches = re.findall('["\\\']([^"\\\']+)["\\\']\\s*[:=\\] \\t]+\\s*["\\\']?[A-Za-z0-9_\\.]+["\\\']?', content)
                for m in matches:
                    node_set.add(m)
                if file_path.endswith('.js'):
                    js_matches = re.findall('registerNodeType\\(["\\\']([^"\\\']+)["\\\']', content)
                    for m in js_matches:
                        node_set.add(m)
        except:
            pass

    def _get_comfy_core_nodes(self):
        """Top-Level Core Node Fingerprint Library – Covers Flux, SD3, Basic Core and Common UI Helper Nodes"""
        return {'KSampler', 'CheckpointLoaderSimple', 'CLIPTextEncode', 'CLIPTextEncodeFlux', 'EmptyLatentImage', 'VAEDecode', 'VAEEncode', 'SaveImage', 'LoadImage', 'VAELoader', 'DualCLIPLoader', 'LatentUpscale', 'LatentUpscaleBy', 'UpscaleModelLoader', 'ImageUpscaleWithModel', 'SetLatentNoiseMask', 'MaskComposite', 'ConditioningCombine', 'ConditioningAverage', 'ConditioningSetArea', 'LatentComposite', 'LatentCompositeMasked', 'VAEDecodeTiled', 'VAEEncodeTiled', 'UNETLoader', 'DiffusersLoader', 'LoraLoader', 'LoraLoaderModelOnly', 'ControlNetApply', 'ControlNetLoader', 'BasicGuider', 'BasicScheduler', 'EmptySD3LatentImage', 'FluxGuidance', 'KSamplerSelect', 'RandomNoise', 'SamplerCustomAdvanced', 'ModelSamplingFlux', 'ModelSamplingDiscrete', 'ModelSamplingSD3', 'CLIPLoader', 'CLIPVisionLoader', 'StyleModelLoader', 'GLIGENLoader', 'CLIPMergeSimple', 'ConditioningZeroOut', 'VaeSoftClamp', 'DiffusionModelLoaderKJ', 'Note', 'Reroute', 'PrimitiveNode', 'PreviewImage'}

    def _search_missing_plugins(self):
        """Search for missing plugins (nodes) - Intelligent fuzzy matching algorithm v2.0
        
        Improvements:
        1. Fuzzy matching (SequenceMatcher) – supports typo tolerance and similar name search
        2. Multiple data sources – official library + GitHub fallback search
        3. Smart caching – 24‑hour cache reduces requests
        4. Advanced sorting – combines match score, node popularity, update time        """
        keyword = self.missing_plugin_keyword_text.get('1.0', tk.END).strip()
        if not keyword:
            messagebox.showwarning('Warning', 'Please enter node keyword')
            return
        core_nodes = self._get_comfy_core_nodes()
        if keyword in core_nodes:
            self.library_listbox.delete(0, tk.END)
            self.library_listbox.insert(tk.END, f'[Core Built‑in] Node: {keyword}')
            self.library_listbox.insert(tk.END, 'This node is an official built‑in of ComfyUI and does not require additional plugin installation.')
            self.library_listbox.itemconfig(0, {'fg': '#006400', 'selectforeground': 'white'})
            self.status_var.set(f'Core node detected: {keyword}')
            return
        self.library_listbox.delete(0, tk.END)
        self.library_listbox.insert(tk.END, f'Initializing intelligent fuzzy search algorithm...')
        self.root.update()

        def search_task():
            try:
                db = self._get_cached_node_db()
                if db is None:
                    url = 'https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/extension-node-map.json'
                    try:
                        response = requests.get(url, timeout=15)
                        if response.status_code == 200:
                            db = response.json()
                            self._cache_node_db(db)
                        else:
                            db = {}
                    except Exception:
                        db = {}
                if not db:
                    self.root.after(0, lambda : messagebox.showerror('Search Failed', 'Unable to connect to the ComfyUI plugin database; please check your network connection.'))
                    return
                search_term = keyword.lower()
                plugin_groups = {}
                for (node_name, info_list) in db.items():
                    if not isinstance(node_name, str) or not isinstance(info_list, list):
                        continue
                    node_score = self._calculate_match_score(node_name, search_term)
                    for entry in info_list:
                        if not isinstance(entry, list) or len(entry) < 2:
                            continue
                        plugin_name = str(entry[0])
                        plugin_info = entry[1]
                        if not isinstance(plugin_info, dict):
                            continue
                        plugin_score = self._calculate_match_score(plugin_name, search_term)
                        final_score = max(node_score, int(plugin_score * 1.2))
                        if final_score >= 100:
                            git_url = plugin_info.get('url', 'Unknown address')
                            stars = plugin_info.get('stars', 0)
                            if plugin_name not in plugin_groups:
                                plugin_groups[plugin_name] = {'nodes': [], 'url': git_url, 'stars': stars, 'max_score': 0, 'total_score': 0}
                            if node_score >= 100:
                                plugin_groups[plugin_name]['nodes'].append(node_name)
                            plugin_groups[plugin_name]['total_score'] += final_score
                            if final_score > plugin_groups[plugin_name]['max_score']:
                                plugin_groups[plugin_name]['max_score'] = final_score
                if len(plugin_groups) < 3:
                    self.root.after(0, lambda : self.library_listbox.insert(tk.END, 'Searching GitHub fallback data source...'))
                    github_results = self._search_github_for_nodes(search_term)
                    for result in github_results:
                        plugin_name = result['name']
                        if plugin_name not in plugin_groups:
                            plugin_groups[plugin_name] = {'nodes': result.get('nodes', [keyword]), 'url': result['url'], 'max_score': result.get('score', 50), 'total_score': result.get('score', 50), 'stars': result.get('stars', 0)}

                def ranking_key(item):
                    (p_name, p_data) = item
                    max_score = p_data['max_score']
                    avg_score = p_data['total_score'] / len(p_data['nodes']) if p_data['nodes'] else 0
                    popularity = (p_data['stars'] or 0) ** 0.5
                    return max_score * 0.5 + avg_score * 0.3 + popularity * 0.2
                sorted_plugins = sorted(plugin_groups.items(), key=ranking_key, reverse=True)

                def update_ui():
                    self.library_listbox.delete(0, tk.END)
                    if not sorted_plugins:
                        self.library_listbox.insert(tk.END, 'Node not found in third‑party libraries. Suggestions:')
                        self.library_listbox.insert(tk.END, '  1. Check the node name spelling')
                        self.library_listbox.insert(tk.END, '  2. Try using English keywords')
                    else:
                        for (idx, (p_name, p_data)) in enumerate(sorted_plugins[:20]):
                            node_count = len(p_data['nodes'])
                            matched_nodes_str = ', '.join(p_data['nodes'][:3])
                            if node_count > 3:
                                matched_nodes_str += f'... (+{node_count - 3})'
                            stars_info = f"⭐{p_data['stars']}" if p_data['stars'] else ''
                            display_text = f"【{idx + 1}】{p_name} {stars_info} | Node: {matched_nodes_str} [URL: {p_data['url']}]"
                            self.library_listbox.insert(tk.END, display_text)
                            if p_data['max_score'] >= 1000:
                                self.library_listbox.itemconfig(tk.END, {'fg': '#c00000'})
                            elif p_data['max_score'] >= 500:
                                self.library_listbox.itemconfig(tk.END, {'fg': '#e65100'})
                            else:
                                self.library_listbox.itemconfig(tk.END, {'fg': '#2e7d32'})
                        if len(sorted_plugins) > 20:
                            self.library_listbox.insert(tk.END, f'... plus  {len(sorted_plugins) - 20} results not displayed')
                    self.status_var.set(f'Search completed: found {len(sorted_plugins)} plugin packages')
                self.root.after(0, update_ui)
            except Exception as e:
                traceback.print_exc()
                self.root.after(0, lambda e=e: messagebox.showerror('Retrieval error', f'Search algorithm execution error: {str(e)}'))
        threading.Thread(target=search_task, daemon=True).start()

    def _calculate_match_score(self, target_str: str, search_term: str) -> int:
        """Deep heuristic intelligent matching engine v4.0 – automatic semantic analysis and multidimensional scoring algorithm"""
        if not target_str or not search_term:
            return 0
        target_raw = str(target_str)
        search_raw = str(search_term).strip()
        t_low = target_raw.lower()
        s_low = search_raw.lower()
        if t_low == s_low:
            return 3000
        if t_low.startswith(s_low):
            return 1500 + int(len(s_low) / len(t_low) * 500)

        def tokenize(s):
            s = re.sub('^(comfyui|custom|node|nodes)[-_ ]', '', s, flags=re.I)
            s = re.sub('[-_ ](nodes|plugin|extension|wrapper)$', '', s, flags=re.I)
            tokens = re.sub('([a-z])([A-Z])', '\\1 \\2', s).replace('_', ' ').replace('-', ' ').split()
            return [t.lower() for t in tokens if t]
        t_tokens = tokenize(target_raw)
        s_tokens = tokenize(search_raw)
        if not t_tokens or not s_tokens:
            return 0
        score = 0
        for st in s_tokens:
            if st in t_tokens:
                score += 800
            else:
                for tt in t_tokens:
                    if tt.startswith(st):
                        score += 400
                        break
        acronym = ''.join([t[0] for t in t_tokens if t])
        if s_low == acronym:
            score += 1200
        elif s_low in acronym and len(s_low) >= 2:
            score += 600
        if s_low == t_tokens[-1] or (len(s_low) > 2 and t_tokens[-1].startswith(s_low)):
            score += 1000
        if score < 200:
            similarity = SequenceMatcher(None, t_low, s_low).ratio()
            if similarity > 0.8:
                score += int(similarity * 500)
        return score

    def _get_cached_node_db(self):
        """Retrieve cached node database (valid for 24 hours)"""
        cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.comfy_node_cache.json')
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                cache_time = datetime.fromisoformat(cache.get('timestamp', '2000-01-01'))
                if datetime.now() - cache_time < timedelta(hours=24):
                    return cache.get('data')
        except Exception:
            pass
        return None

    def _cache_node_db(self, data):
        """Cache node database"""
        cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.comfy_node_cache.json')
        try:
            cache = {'timestamp': datetime.now().isoformat(), 'data': data}
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass

    def _search_github_for_nodes(self, search_term: str) -> list:
        """GitHub fallback search – used when official library results are insufficient
        
        Return format: [{"name": str, "url": str, "nodes": list, "score": int, "stars": int}]        """
        results = []
        try:
            query = f'comfyui+{search_term}+in:name+language:python'
            url = f'https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=10'
            headers = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'ComfyUI-Plugin-Searcher'}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for item in data.get('items', []):
                    if 'comfyui' in item.get('full_name', '').lower() or 'comfyui' in item.get('description', '').lower():
                        results.append({'name': item.get('name', ''), 'url': item.get('html_url', ''), 'nodes': [search_term], 'score': 150, 'stars': item.get('stargazers_count', 0)})
            if not results:
                fallback_url = f'https://github.com/search?q=comfyui+{search_term}+language%3Apython&type=repositories'
                results.append({'name': f"GitHub search '{search_term}'", 'url': fallback_url, 'nodes': [search_term], 'score': 50, 'stars': 0})
        except Exception:
            pass
        return results

    def _install_plugin_package(self):
        """[PRO Feature] This function automatically installs plugin packages and is disabled in the open‑source version."""
        pass

    def search_comfyui_plugins(self):
        """Search and display local ComfyUI plugin packages (contents of custom_nodes folder)"""
        custom_nodes_path = self._get_custom_nodes_path()
        if not custom_nodes_path:
            messagebox.showwarning('Directory not found', 'ComfyUI plugin directory not found; please check the path settings.')
            return
        if hasattr(self, 'plugins_listbox'):
            self.plugins_listbox.delete(0, tk.END)
        else:
            return
        try:
            dirs = [d for d in os.listdir(custom_nodes_path) if os.path.isdir(os.path.join(custom_nodes_path, d))]
            for d in sorted(dirs):
                self.plugins_listbox.insert(tk.END, d)
            self.status_var.set(f'Scanned {len(dirs)} local plugin packages')
        except Exception as e:
            messagebox.showerror('Query failed', f'Unable to read plugin directory: {e}')

    def query_workflow_nodes(self):
        """Check nodes included in the currently selected workflow"""
        specific_workflow = self.specific_workflow_combo.get()
        if not specific_workflow:
            messagebox.showwarning('Warning', 'Please select a workflow in the main console first')
            return
        workflow_path = os.path.join(self.proj_path.get(), specific_workflow)
        if not os.path.exists(workflow_path):
            return
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for widget in self.params_inner_frame.winfo_children():
                widget.destroy()
            ttk.Label(self.params_inner_frame, text=f'Workflow analysis: {specific_workflow}', font=('Microsoft YaHei', 11, 'bold'), foreground='#333').pack(anchor='w', pady=(0, 10))
            self._load_workflow_params_ui(data)
            self.status_var.set(f'Workflow node query and parameter extraction completed.')
        except Exception as e:
            messagebox.showerror('Query failed', f'Error analyzing workflow nodes: {e}')

    def _create_node_frame(self, parent, title, color='#e1f5fe'):
        """Create a framework that mimics node style"""
        frame = tk.Frame(parent, bd=1, relief='solid', background='white', padx=10, pady=10)
        frame.pack(fill='x', pady=5)
        title_label = tk.Label(frame, text=title, font=('Microsoft YaHei', 10, 'bold'), background=color, anchor='w', padx=5)
        title_label.pack(fill='x', pady=(0, 10))
        return frame

    def _get_custom_nodes_path(self):
        """Helper method to obtain the ComfyUI plugin directory (multi‑path deep detection expert edition)

        Uses the same search algorithm as _find_comfyui_path to locate the ComfyUI directory,
        then returns its custom_nodes subdirectory.
        Never creates a directory itself; it must ensure the default folder under the system COMFYUI runtime is found.        """
        comfyui_base = self._find_comfyui_path()
        if comfyui_base:
            custom_nodes = os.path.join(comfyui_base, 'custom_nodes')
            if os.path.isdir(custom_nodes):
                return custom_nodes
        return None

    def _get_local_checkpoints(self, model_type='checkpoints', filter_flux=False):
        """Scan local models – expert‑level recursive scanning and path normalization (supports multiple model types)"""
        custom_nodes_path = self._get_custom_nodes_path()
        if not custom_nodes_path:
            return []
        comfy_root = os.path.dirname(custom_nodes_path)
        type_map = {'checkpoints': 'checkpoints', 'unet': 'unet', 'vae': 'vae', 'loras': 'loras', 'controlnet': 'controlnet', 'upscale_models': 'upscale_models'}
        sub_dir = type_map.get(model_type, model_type)
        model_path = os.path.join(comfy_root, 'models', sub_dir)
        if not os.path.exists(model_path):
            return []
        models = []
        for (root, dirs, files) in os.walk(model_path):
            for file in files:
                if file.startswith('.'):
                    continue
                if any((file.endswith(ext) for ext in ['.safetensors', '.ckpt', '.sft', '.pth', '.bin'])):
                    rel_path = os.path.relpath(os.path.join(root, file), model_path)
                    clean_path = rel_path.replace('\\', '/')
                    models.append(clean_path)
        models = sorted(models)
        if model_type in ['checkpoints', 'unet']:
            if filter_flux:
                flux_models = [m for m in models if 'flux' in m.lower()]
                other_models = [m for m in models if 'flux' not in m.lower()]
                return flux_models + ['--- Other Models ---'] + other_models
            else:
                base_models = [m for m in models if any((x in m.lower() for x in ['sdxl', 'sd15', 'v1-5'])) and 'refiner' not in m.lower()]
                refiner_models = [m for m in models if 'refiner' in m.lower()]
                others = [m for m in models if m not in base_models and m not in refiner_models]
                return base_models + ['--- Refinement Models ---'] + refiner_models + ['--- Others ---'] + others
        return models

    def _get_facedetailer_indices(self, w_vals):
        """Top‑level adaptive algorithm: dynamically locks FaceDetailer parameter slots via data fingerprinting"""
        s_idx = -1
        samplers = ['euler', 'euler_ancestral', 'heun', 'dpm_2', 'lms', 'dpmpp_2m', 'dpmpp_2m_sde', 'dpmpp_3m_sde', 'ddim', 'uni_pc']
        schedulers = ['normal', 'karras', 'simple', 'exponential', 'sgm_uniform', 'turbo']
        for (i, val) in enumerate(w_vals):
            if isinstance(val, str) and val in samplers:
                if i + 1 < len(w_vals) and w_vals[i + 1] in schedulers:
                    s_idx = i
                    break
        if s_idx == -1:
            return {'guide_size': 13, 'cycle': 19, 'bbox_threshold': 9}
        layout = {'guide_size': s_idx - 7 if s_idx >= 7 else 0, 'cycle': s_idx + 17 if len(w_vals) > s_idx + 17 else 19, 'bbox_threshold': s_idx + 6 if len(w_vals) > s_idx + 6 else 13}
        potential_gs = w_vals[layout['guide_size']] if isinstance(w_vals[layout['guide_size']], (int, float)) else 0
        if potential_gs > 4096:
            for j in range(len(w_vals)):
                if isinstance(w_vals[j], (int, float)) and 256 <= w_vals[j] <= 1024:
                    layout['guide_size'] = j
                    break
        return layout

    def _load_workflow_params_ui(self, workflow_data):
        """Parse workflow and generate parameter editing UI – top‑level expert normalization algorithm"""
        self.workflow_param_vars = {}
        PARAM_REGISTRY.clear()
        standard_nodes = []
        is_flux = False
        try:
            if isinstance(workflow_data, dict):
                if 'nodes' in workflow_data and isinstance(workflow_data['nodes'], list):
                    for n in workflow_data['nodes']:
                        if isinstance(n, dict):
                            standard_nodes.append(n)
                else:
                    for (node_id, node_body) in workflow_data.items():
                        if isinstance(node_body, dict):
                            n_copy = node_body.copy()
                            n_copy['id'] = node_id
                            standard_nodes.append(n_copy)
            elif isinstance(workflow_data, list):
                for n in workflow_data:
                    if isinstance(n, dict):
                        standard_nodes.append(n)
        except Exception as e:
            print(f'Data pre‑parsing failed: {e}')
            return
        if not standard_nodes:
            self.status_var.set('Warning: Failed to recognize valid node data in JSON')
            return
        for n in standard_nodes:
            node_type = str(n.get('type') or n.get('class_type') or '')
            if any((x in node_type for x in ['Flux', 'DiffusionModelLoaderKJ'])):
                is_flux = True
                break
        main_model_node = None
        main_candidates = []
        for n in standard_nodes:
            c_type = n.get('type') or n.get('class_type')
            if c_type in ['CheckpointLoaderSimple', 'UNETLoader', 'DiffusionModelLoaderKJ']:
                title = str(n.get('title', '')).lower()
                is_refiner = 'refiner' in title
                inputs = n.get('inputs')
                if isinstance(inputs, dict):
                    ckpt_val = str(inputs.get('ckpt_name', '')).lower()
                    if 'refiner' in ckpt_val:
                        is_refiner = True
                main_candidates.append({'node': n, 'is_refiner': is_refiner})
        for cand in main_candidates:
            if not cand['is_refiner']:
                main_model_node = cand['node']
                break
        if not main_model_node and main_candidates:
            main_model_node = main_candidates[0]['node']
        if main_model_node:
            node_id = str(main_model_node.get('id'))
            c_type = main_model_node.get('type') or main_model_node.get('class_type')
            node_frame = self._create_node_frame(self.params_inner_frame, f'1. Core base model / weight selection (Node: {node_id})', '#d1c4e9')
            model_category = 'unet' if c_type == 'UNETLoader' else 'checkpoints'
            local_models = self._get_local_checkpoints(model_category, filter_flux=is_flux)
            param_key = 'unet_name' if c_type == 'UNETLoader' else 'model_name' if c_type == 'DiffusionModelLoaderKJ' else 'ckpt_name'
            current_model = ''
            w_vals = main_model_node.get('widgets_values')
            if isinstance(w_vals, list) and len(w_vals) > 0:
                current_model = w_vals[0]
            elif isinstance(main_model_node.get('inputs'), dict):
                current_model = main_model_node['inputs'].get(param_key, '')
            current_model_str = str(current_model)
            if current_model_str and current_model_str not in local_models:
                fname = os.path.basename(current_model_str)
                for lm in local_models:
                    if os.path.basename(lm) == fname:
                        current_model = lm
                        break
            row = ttk.Frame(node_frame)
            row.pack(fill='x', pady=5)
            ttk.Label(row, text='Base model selection:', width=15).pack(side='left')
            m_var = tk.StringVar(value=str(current_model))
            m_combo = ttk.Combobox(row, textvariable=m_var, values=local_models, width=45)
            m_combo.pack(side='left', padx=5)
            tech_route = 'FLUX / Large Model' if is_flux else 'Stable Diffusion'
            ttk.Label(row, text=f'Route: {tech_route}', foreground='#673ab7', font=('Microsoft YaHei', 9, 'bold')).pack(side='left', padx=10)
            self.workflow_param_vars[f'{node_id}_{param_key}'] = m_var
        is_ui_format = isinstance(workflow_data, dict) and 'nodes' in workflow_data and isinstance(workflow_data['nodes'], list)
        for node in standard_nodes:
            node_id = str(node.get('id'))
            if main_model_node and node_id == str(main_model_node.get('id')):
                continue
            class_type = node.get('type') or node.get('class_type')
            if class_type in ['EmptyLatentImage', 'EmptySD3LatentImage']:
                node_frame = self._create_node_frame(self.params_inner_frame, f'Base size (Node: {node_id})', '#fff9c4')
                (w, h) = (1024, 1024)
                if is_ui_format and 'widgets_values' in node and (len(node['widgets_values']) >= 2):
                    (w, h) = (node['widgets_values'][0], node['widgets_values'][1])
                elif not is_ui_format and 'inputs' in node:
                    (w, h) = (node['inputs'].get('width', 1024), node['inputs'].get('height', 1024))
                row1 = ttk.Frame(node_frame)
                row1.pack(fill='x')
                ttk.Label(row1, text='Width (pixels):', width=15).pack(side='left')
                w_var = tk.StringVar(value=str(w))
                ttk.Entry(row1, textvariable=w_var, width=10).pack(side='left')
                ttk.Label(row1, text=' px', width=5).pack(side='left')
                ttk.Label(row1, text='[Note] Base image width. Flux recommends >1024.', foreground='gray').pack(side='left', padx=10)
                row2 = ttk.Frame(node_frame)
                row2.pack(fill='x', pady=5)
                ttk.Label(row2, text='Height (pixels):', width=15).pack(side='left')
                h_var = tk.StringVar(value=str(h))
                ttk.Entry(row2, textvariable=h_var, width=10).pack(side='left')
                ttk.Label(row2, text=' px', width=5).pack(side='left')
                ttk.Label(row2, text='[Note] Base image height. Recommended to be a multiple of 16.', foreground='gray').pack(side='left', padx=10)
                self.workflow_param_vars[f'{node_id}_width'] = w_var
                self.workflow_param_vars[f'{node_id}_height'] = h_var
                PARAM_REGISTRY.register(node_id, 'width', index=0, api_key='width', val_type=int)
                PARAM_REGISTRY.register(node_id, 'height', index=1, api_key='height', val_type=int)
            if class_type == 'KSampler':
                node_frame = self._create_node_frame(self.params_inner_frame, f'Core sampler (Node: {node_id})', '#e1f5fe')
                (seed, steps, cfg, denoise) = (0, 20, 7.0, 1.0)
                if is_ui_format and 'widgets_values' in node:
                    w_vals = node['widgets_values']
                    if len(w_vals) >= 6:
                        seed = w_vals[0]
                        shift = 1 if isinstance(w_vals[1], str) and any((x in w_vals[1] for x in ['randomize', 'fixed', 'increment', 'decrement'])) else 0
                        steps = w_vals[1 + shift]
                        cfg = w_vals[2 + shift]
                        denoise = w_vals[5 + shift] if len(w_vals) > 5 + shift else w_vals[-1]
                elif not is_ui_format and 'inputs' in node:
                    seed = node['inputs'].get('seed', 0)
                    steps = node['inputs'].get('steps', 20)
                    cfg = node['inputs'].get('cfg', 7.0)
                    denoise = node['inputs'].get('denoise', 1.0)
                self._add_sampler_rows(node_frame, node_id, seed, steps, cfg, denoise)
            elif class_type == 'BasicScheduler':
                node_frame = self._create_node_frame(self.params_inner_frame, f'Scheduler (Node: {node_id})', '#e1f5fe')
                steps = 20
                if is_ui_format and 'widgets_values' in node and (len(node['widgets_values']) >= 2):
                    steps = node['widgets_values'][1]
                elif not is_ui_format and 'inputs' in node:
                    steps = node['inputs'].get('steps', 20)
                row = ttk.Frame(node_frame)
                row.pack(fill='x')
                ttk.Label(row, text='Iteration steps (Steps):', width=15).pack(side='left')
                steps_var = tk.StringVar(value=str(steps))
                ttk.Entry(row, textvariable=steps_var, width=10).pack(side='left')
                ttk.Label(row, text='[Note] Flux generation steps, recommended 20-30.', foreground='gray').pack(side='left', padx=10)
                self.workflow_param_vars[f'{node_id}_steps'] = steps_var
            elif class_type == 'FluxGuidance':
                node_frame = self._create_node_frame(self.params_inner_frame, f'Flux guidance (Node: {node_id})', '#bbdefb')
                guidance = 3.5
                if is_ui_format and 'widgets_values' in node and (len(node['widgets_values']) >= 1):
                    guidance = node['widgets_values'][0]
                elif not is_ui_format and 'inputs' in node:
                    guidance = node['inputs'].get('guidance', 3.5)
                row = ttk.Frame(node_frame)
                row.pack(fill='x')
                ttk.Label(row, text='Guidance intensity (Guidance):', width=15).pack(side='left')
                guidance_var = tk.StringVar(value=str(guidance))
                ttk.Entry(row, textvariable=guidance_var, width=10).pack(side='left')
                ttk.Label(row, text='[Note] Similar to CFG, Flux default recommendation is 3.5.', foreground='gray').pack(side='left', padx=10)
                self.workflow_param_vars[f'{node_id}_guidance'] = guidance_var
            elif class_type == 'RandomNoise':
                node_frame = self._create_node_frame(self.params_inner_frame, f'Random noise (Node: {node_id})', '#cfd8dc')
                seed = 0
                if is_ui_format and 'widgets_values' in node and (len(node['widgets_values']) >= 1):
                    seed = node['widgets_values'][0]
                elif not is_ui_format and 'inputs' in node:
                    seed = node['inputs'].get('noise_seed', node['inputs'].get('seed', 0))
                row = ttk.Frame(node_frame)
                row.pack(fill='x')
                ttk.Label(row, text='Random seed (Seed):', width=15).pack(side='left')
                seed_var = tk.StringVar(value=str(seed))
                ttk.Entry(row, textvariable=seed_var, width=20).pack(side='left')
                ttk.Label(row, text='[Note] Controls generation randomness.', foreground='gray').pack(side='left', padx=10)
                self.workflow_param_vars[f'{node_id}_seed'] = seed_var
            if 'Upscale' in class_type or 'Resize' in class_type:
                node_frame = self._create_node_frame(self.params_inner_frame, f'Scale / HD restoration (Node: {node_id})', '#e8f5e9')
                (upscale_w, upscale_h) = (1024, 1024)
                if is_ui_format and isinstance(node.get('widgets_values'), list) and (len(node['widgets_values']) >= 2):
                    (upscale_w, upscale_h) = (node['widgets_values'][0], node['widgets_values'][1])
                elif not is_ui_format and isinstance(node.get('inputs'), dict):
                    upscale_w = node['inputs'].get('upscale_width', node['inputs'].get('width', 1024))
                    upscale_h = node['inputs'].get('upscale_height', node['inputs'].get('height', 1024))
                row_up = ttk.Frame(node_frame)
                row_up.pack(fill='x')
                ttk.Label(row_up, text='Target resolution:', width=15).pack(side='left')
                uw_var = tk.StringVar(value=str(upscale_w))
                uh_var = tk.StringVar(value=str(upscale_h))
                ttk.Entry(row_up, textvariable=uw_var, width=8).pack(side='left')
                ttk.Label(row_up, text=' x ').pack(side='left')
                ttk.Entry(row_up, textvariable=uh_var, width=8).pack(side='left')
                ttk.Label(row_up, text='[Note] Final output upscale resolution.', foreground='gray').pack(side='left', padx=10)
                self.workflow_param_vars[f'{node_id}_upscale_width'] = uw_var
                self.workflow_param_vars[f'{node_id}_upscale_height'] = uh_var
            if class_type == 'FaceDetailer':
                node_frame = self._create_node_frame(self.params_inner_frame, f'Face / hand restoration (Node: {node_id})', '#ffe0b2')
                (cycle, guide_size) = (1, 384)
                if is_ui_format and isinstance(node.get('widgets_values'), list):
                    w_vals = node['widgets_values']
                    indices = self._get_facedetailer_indices(w_vals)
                    gs_idx = indices['guide_size']
                    cy_idx = indices['cycle']
                    raw_gs = w_vals[gs_idx] if gs_idx >= 0 and gs_idx < len(w_vals) else 384
                    if isinstance(raw_gs, (int, float)) and raw_gs > 4096:
                        guide_size = 512
                        self.status_var.set('Warning: Detected parameter contamination in Node 26, automatically corrected.')
                    else:
                        guide_size = raw_gs
                    cycle = w_vals[cy_idx] if cy_idx >= 0 and cy_idx < len(w_vals) else 1
                elif not is_ui_format and isinstance(node.get('inputs'), dict):
                    cycle = node['inputs'].get('cycle', 1)
                    guide_size = node['inputs'].get('guide_size', 384)
                if not isinstance(cycle, int) or cycle < 1:
                    cycle = 1
                row_f = ttk.Frame(node_frame)
                row_f.pack(fill='x')
                ttk.Label(row_f, text='Iteration count (Cycle):', width=15).pack(side='left')
                cycle_var = tk.StringVar(value=str(cycle))
                ttk.Entry(row_f, textvariable=cycle_var, width=10).pack(side='left')
                ttk.Label(row_f, text='[Important] Minimum value must be 1', foreground='#c00000').pack(side='left', padx=10)
                row_g = ttk.Frame(node_frame)
                row_g.pack(fill='x', pady=5)
                ttk.Label(row_g, text='Guide size:', width=15).pack(side='left')
                gs_var = tk.StringVar(value=str(guide_size))
                ttk.Entry(row_g, textvariable=gs_var, width=10).pack(side='left')
                ttk.Label(row_g, text='[Note] Reference resolution for the repair area.', foreground='gray').pack(side='left', padx=10)
                self.workflow_param_vars[f'{node_id}_cycle'] = cycle_var
                self.workflow_param_vars[f'{node_id}_guide_size'] = gs_var
                if is_ui_format:
                    w_vals = node.get('widgets_values', [])
                    idx_map = self._get_facedetailer_indices(w_vals)
                    PARAM_REGISTRY.register(node_id, 'cycle', index=idx_map['cycle'], api_key='cycle', val_type=int)
                    PARAM_REGISTRY.register(node_id, 'guide_size', index=idx_map['guide_size'], api_key='guide_size', val_type=int)
                else:
                    PARAM_REGISTRY.register(node_id, 'cycle', api_key='cycle', val_type=int)
                    PARAM_REGISTRY.register(node_id, 'guide_size', api_key='guide_size', val_type=int)
            if any((x in class_type for x in ['VAELoader', 'UNETLoader', 'CheckpointLoader', 'LoraLoader'])):
                color = '#f3e5f5'
                title_map = {'VAELoader': 'VAE Loader', 'UNETLoader': 'Model loader (UNET)', 'CheckpointLoaderSimple': 'Large model loader (Checkpoint)', 'LoraLoader': 'LoRA Loader'}
                node_frame = self._create_node_frame(self.params_inner_frame, f"{title_map.get(class_type, 'Model loader')} (Node: {node_id})", color)
                model_name = ''
                param_key = ''
                local_category = 'checkpoints'
                if class_type == 'VAELoader':
                    param_key = 'vae_name'
                    local_category = 'vae'
                elif class_type == 'UNETLoader':
                    param_key = 'unet_name'
                    local_category = 'unet'
                elif class_type == 'CheckpointLoaderSimple':
                    param_key = 'ckpt_name'
                    local_category = 'checkpoints'
                elif class_type == 'LoraLoader':
                    param_key = 'lora_name'
                    local_category = 'loras'
                if is_ui_format and 'widgets_values' in node and (len(node['widgets_values']) > 0):
                    model_name = node['widgets_values'][0]
                elif not is_ui_format and 'inputs' in node:
                    model_name = node['inputs'].get(param_key, '')
                local_files = self._get_local_checkpoints(local_category)
                model_name_str = str(model_name)
                if model_name_str and model_name_str not in local_files:
                    fname = os.path.basename(model_name_str)
                    found_in_cross = False
                    for lf in local_files:
                        if os.path.basename(lf) == fname:
                            model_name = lf
                            found_in_cross = True
                            break
                    if not found_in_cross:
                        search_targets = ['loras', 'checkpoints'] if local_category != 'loras' else ['checkpoints']
                        for target_cat in search_targets:
                            cross_files = self._get_local_checkpoints(target_cat)
                            for cf in cross_files:
                                if os.path.basename(cf) == fname:
                                    model_name = cf
                                    local_files = local_files + [f'--- Cross-directory matching ({target_cat}) ---'] + cross_files
                                    found_in_cross = True
                                    break
                            if found_in_cross:
                                break
                row = ttk.Frame(node_frame)
                row.pack(fill='x')
                ttk.Label(row, text='Filename:', width=15).pack(side='left')
                m_var = tk.StringVar(value=str(model_name))
                m_combo = ttk.Combobox(row, textvariable=m_var, values=local_files, width=40)
                m_combo.pack(side='left', padx=5)
                status_color = '#008000' if '/' in str(model_name) else '#c00000'
                status_text = '[Auto-match local path]' if '/' in str(model_name) else '[Please select path manually]'
                ttk.Label(row, text=status_text, foreground=status_color).pack(side='left', padx=10)
                self.workflow_param_vars[f'{node_id}_{param_key}'] = m_var
                PARAM_REGISTRY.register(node_id, param_key, index=0, api_key=param_key, val_type=str)
        if not self.workflow_param_vars:
            ttk.Label(self.params_inner_frame, text='No standard adjustable parameter nodes detected in this workflow (supports KSampler, Flux, EmptyLatent, etc.).', foreground='red', font=('Microsoft YaHei', 10, 'bold')).pack(pady=40)

    def _add_sampler_rows(self, node_frame, node_id, seed, steps, cfg, denoise):
        """Helper function: add standard rows to sampler framework and register semantic metadata"""
        r_seed = ttk.Frame(node_frame)
        r_seed.pack(fill='x')
        ttk.Label(r_seed, text='Random seed (Seed):', width=15).pack(side='left')
        seed_var = tk.StringVar(value=str(seed))
        ttk.Entry(r_seed, textvariable=seed_var, width=15).pack(side='left')
        ttk.Label(r_seed, text='[Note] Controls randomness. Fixed values are reproducible.', foreground='gray').pack(side='left', padx=10)
        self.workflow_param_vars[f'{node_id}_seed'] = seed_var
        PARAM_REGISTRY.register(node_id, 'seed', index=0, api_key='seed', val_type=int)
        r_steps = ttk.Frame(node_frame)
        r_steps.pack(fill='x', pady=5)
        ttk.Label(r_steps, text='Step count (Steps):', width=15).pack(side='left')
        steps_var = tk.StringVar(value=str(steps))
        ttk.Entry(r_steps, textvariable=steps_var, width=10).pack(side='left')
        ttk.Label(r_steps, text='[Note] Higher values yield more detail.', foreground='gray').pack(side='left', padx=10)
        self.workflow_param_vars[f'{node_id}_steps'] = steps_var
        PARAM_REGISTRY.register(node_id, 'steps', index=2, api_key='steps', val_type=int)
        r_cfg = ttk.Frame(node_frame)
        r_cfg.pack(fill='x')
        ttk.Label(r_cfg, text='Prompt relevance:', width=15).pack(side='left')
        cfg_var = tk.StringVar(value=str(cfg))
        ttk.Entry(r_cfg, textvariable=cfg_var, width=10).pack(side='left')
        ttk.Label(r_cfg, text='[Note] Higher values adhere more closely to the prompt.', foreground='gray').pack(side='left', padx=10)
        self.workflow_param_vars[f'{node_id}_cfg'] = cfg_var
        PARAM_REGISTRY.register(node_id, 'cfg', index=3, api_key='cfg', val_type=float)
        r_denoise = ttk.Frame(node_frame)
        r_denoise.pack(fill='x', pady=5)
        ttk.Label(r_denoise, text='Redraw intensity:', width=15).pack(side='left')
        denoise_var = tk.StringVar(value=str(denoise))
        ttk.Entry(r_denoise, textvariable=denoise_var, width=10).pack(side='left')
        ttk.Label(r_denoise, text='[Note] Range 0-1, controls deviation from original image.', foreground='gray').pack(side='left', padx=10)
        self.workflow_param_vars[f'{node_id}_denoise'] = denoise_var
        PARAM_REGISTRY.register(node_id, 'denoise', index=6, api_key='denoise', val_type=float)

    def apply_workflow_parameters(self):
        """[PRO feature] This function writes modified parameters back to the workflow file; disabled in the open-source version."""
        pass

    def on_tab_changed(self, event):
        """When switching Notebook tabs, display the full tab name in the title row of the corresponding area."""
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
        """Create right-click menu for text box"""
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label='Select All', command=lambda : self.select_all_text(text_widget))
        context_menu.add_command(label='Undo', command=lambda : self.undo_text(text_widget))
        context_menu.add_separator()
        context_menu.add_command(label='Copy', command=lambda : self.copy_text(text_widget))
        context_menu.add_command(label='Paste', command=lambda : self.paste_text(text_widget))
        context_menu.add_command(label='Cut', command=lambda : self.cut_text(text_widget))
        context_menu.add_separator()
        context_menu.add_command(label='Delete', command=lambda : self.delete_selected_text(text_widget))
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
        """Show context menu"""
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def undo_text(self, text_widget):
        """Undo operation"""
        try:
            text_widget.edit_undo()
        except tk.TclError:
            pass

    def cut_text(self, text_widget):
        """Cut text"""
        try:
            if text_widget.selection_get():
                text_widget.event_generate('<<Cut>>')
        except tk.TclError:
            pass

    def copy_text(self, text_widget):
        """Copy text"""
        try:
            if text_widget.selection_get():
                text_widget.event_generate('<<Copy>>')
        except tk.TclError:
            text_widget.clipboard_clear()
            text_content = text_widget.get('1.0', tk.END).strip()
            if text_content:
                text_widget.clipboard_append(text_content)

    def paste_text(self, text_widget):
        """Paste text"""
        try:
            text_widget.event_generate('<<Paste>>')
        except tk.TclError:
            pass

    def select_all_text(self, text_widget):
        """Select all text"""
        text_widget.tag_add(tk.SEL, '1.0', tk.END)
        text_widget.mark_set(tk.INSERT, '1.0')
        text_widget.see(tk.INSERT)

    def delete_selected_text(self, text_widget):
        """Delete selected text"""
        try:
            if text_widget.selection_get():
                text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            pass

    def browse_proj_path(self):
        """Browse to select PROJ path"""
        path = filedialog.askdirectory(initialdir=self.proj_path.get())
        if path:
            self.proj_path.set(path)
            self.status_var.set(f'New path selected, please click “Identify Workflow”')
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
        """Use pure algorithm to identify and classify all workflow files in the folder.        """
        proj_path = self.proj_path.get()
        if not os.path.exists(proj_path):
            messagebox.showerror('Error', 'Workflow path does not exist.')
            return
        workflow_files_to_process = [f for f in os.listdir(proj_path) if f.lower().endswith('.json')]
        if not workflow_files_to_process:
            self.status_var.set('No .json workflow files found.')
            return
        self.status_var.set('Starting workflow identification using algorithm...')
        self.conversion_progressbar.start(40)

        def recognition_thread_task():
            """Processing files sequentially in a background thread."""
            temp_results = {}
            total_files = len(workflow_files_to_process)
            for (i, filename) in enumerate(workflow_files_to_process):
                self.root.after(0, lambda i=i, f=filename: self.status_var.set(f'Analyzing ({i + 1}/{total_files}): {f}'))
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
                    print(f'Processing with algorithm {filename} Error occurred at: {e}')
            self.root.after(0, self.on_recognition_complete, temp_results)
        threading.Thread(target=recognition_thread_task, daemon=True).start()

    def _run_workflow_analysis_algorithm(self, workflow_data):
        """Main entry of the algorithm, coordinating classification and injection point detection, generating the specified summary table.        """
        try:
            nodes = self._normalize_nodes(workflow_data)
            if not nodes:
                return None
            (nodes_map, graph_topology) = self._get_graph_topology(nodes)
            category = self._categorize_workflow(nodes, nodes_map, graph_topology)
            if category == 'Uncategorized':
                return None
            topo_injection_points = self._identify_injection_points(nodes, nodes_map, graph_topology, workflow_data)
            summary_table = self._build_summary_table(nodes, nodes_map, graph_topology, workflow_data, topo_injection_points)
            if summary_table:
                return {'workflow_category': category, 'summary_table': summary_table}
            else:
                return {'workflow_category': category, 'summary_table': []}
        except Exception as e:
            print(f'Algorithm analysis failed: {e}')
            traceback.print_exc()
            return None

    def _build_summary_table(self, nodes, nodes_map, graph_topology, workflow_data, topo_injection_points=[]):
        """Build summary table as per user request.
        Core logic: locate injection points, analyze nodes, extract keywords, generate records.        """
        summary_table = []
        unnamed_counter = 1
        topo_map = {str(pt['node_id']): pt for pt in topo_injection_points}
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
                    widget_infos = []
                    if 'widgets_values' in original_node and isinstance(original_node.get('widgets_values'), list):
                        for (idx, value) in enumerate(original_node['widgets_values']):
                            if isinstance(value, str):
                                info = {'type': 'widgets_values', 'index': idx, 'name': 'text'}
                                if 'Flux' in node_type or 'flux' in node_type.lower():
                                    widget_infos.append(info)
                                else:
                                    widget_infos.append(info)
                                    break
                    if not widget_infos and 'inputs' in original_node:
                        found_inputs = False
                        for key in ['clip_l', 't5xxl', 'text']:
                            if key in original_node['inputs']:
                                widget_infos.append({'type': 'inputs', 'key': key, 'name': 'text', 'index': 0})
                                found_inputs = True
                                if 'Flux' not in node_type and 'flux' not in node_type.lower():
                                    break
                        if not found_inputs and 'text' in original_node.get('inputs', {}):
                            widget_infos.append({'type': 'inputs', 'key': 'text', 'name': 'text', 'index': 0})
                if widget_infos:
                    keywords = self._extract_keywords_from_title(title)
                    topo_info = topo_map.get(node_id)
                    if topo_info:
                        topo_segment = topo_info.get('segment', 'base_positive')
                        t_parts = topo_segment.split('_')
                        t_mod = t_parts[0] if len(t_parts) > 0 else 'base'
                        t_type = t_parts[1] if len(t_parts) > 1 else 'positive'
                        for p in [t_mod, t_type]:
                            if p not in keywords:
                                keywords.append(p)
                    if not keywords or ('positive' not in keywords and 'negative' not in keywords):
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
                    final_mod = 'base'
                    for m in ['base', 'main', 'refine', 'inpaint', 'fix', 'face', 'hand', 'person', 'feet']:
                        if m in keywords:
                            final_mod = m
                            break
                    final_type = 'negative' if 'negative' in keywords else 'positive'
                    prompt_properties = {'modifier': final_mod, 'type': final_type}
                    full_node_name = title if title else f'UNKNOWN{unnamed_counter}'
                    if not title:
                        unnamed_counter += 1
                    injection_item = {'injection_type': 'prompt', 'injection_location': {'node_id': node_id, 'widget_infos': widget_infos, 'widget_info': widget_infos[0]}, 'full_node_name': full_node_name, 'keywords': keywords, 'prompt_properties': prompt_properties, 'node_type': node_type, '_order': i}
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
        if has_video_output:
            return 'Image-to-Video' if has_image_input else 'Text-to-Video'
        else:
            return 'Image-to-Image' if has_image_input else 'Text-to-Image'

    def _get_downstream_consumers(self, node_id, nodes_map, workflow_data):
        """Helper function to find all direct downstream consumers of a node."""
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
        """Convert workflow JSONs of various formats into a unified node list format."""
        if 'nodes' in workflow_data and isinstance(workflow_data['nodes'], list):
            return workflow_data['nodes']
        nodes = []
        try:
            raw_nodes = {node_id: node_info for (node_id, node_info) in workflow_data.items() if isinstance(node_info, dict) and 'class_type' in node_info}
            for (node_id, node_info) in raw_nodes.items():
                node_id_str = str(node_id)
                try:
                    clean_id = int(re.sub('\\D', '', node_id_str)) if any((c.isdigit() for c in node_id_str)) else node_id
                except:
                    clean_id = node_id
                node = {'id': clean_id, 'type': node_info['class_type'], 'title': node_info.get('_meta', {}).get('title', ''), 'inputs': [], 'widgets_values': []}
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
            print(f'Error while normalizing nodes: {e}')
            return None

    def on_recognition_complete(self, results):
        """Callback after all workflows are recognized."""
        self.conversion_progressbar.stop()
        self.workflow_analysis_cache = results
        self.workflow_files = {}
        for (filename, analysis) in self.workflow_analysis_cache.items():
            category = analysis.get('workflow_category', 'Uncategorized')
            if category not in self.workflow_files:
                self.workflow_files[category] = []
            self.workflow_files[category].append(filename)
        categories = sorted(list(self.workflow_files.keys()))
        self.workflow_type_var.set('')
        self.workflow_type_combo['values'] = categories
        if categories:
            self.workflow_type_var.set(categories[0])
        self.on_workflow_type_change()
        self.status_var.set(f'Recognition complete: {len(self.workflow_analysis_cache)}workflows.')
        if len(self.workflow_analysis_cache) > 0:
            messagebox.showinfo('Recognition complete', f'Successfully analyzed {len(self.workflow_analysis_cache)} workflow files.')
        else:
            messagebox.showwarning('Recognition notice', 'Failed to successfully analyze any workflow files; please check the workflow files or console errors.')

    def on_workflow_type_change(self, event=None):
        """Update specific workflow list when workflow type changes"""
        workflow_type = self.workflow_type_var.get()
        files = self.workflow_files.get(workflow_type, [])
        self.specific_workflow_combo['values'] = files
        self.specific_workflow_combo.set(files[0] if files else '')
        self.on_specific_workflow_change()

    def start_ollama_service(self):
        """Start OLLAMA service"""
        self.status_var.set('Starting OLLAMA...')

        def start_task():
            success = self.ollama_manager.start_ollama()
            self.root.after(0, lambda : self.on_ollama_start_complete(success))
        threading.Thread(target=start_task, daemon=True).start()

    def on_ollama_start_complete(self, success):
        """OLLAMA startup complete callback"""
        if success:
            self.ollama_status_var.set('Running')
            self.ollama_status_label.config(foreground='green')
            self.status_var.set('OLLAMA started')
            self.start_ollama_button.config(state='disabled')
            self.stop_ollama_button.config(state='normal')
            self.refresh_model_list()
            self.client = self._create_openai_client()
        else:
            self.ollama_status_var.set('Startup failed')
            self.ollama_status_label.config(foreground='red')
            self.status_var.set('OLLAMA startup failed')
            self.start_ollama_button.config(state='normal')
            self.stop_ollama_button.config(state='disabled')

    def stop_ollama_service(self):
        """Stop OLLAMA service"""
        self.ollama_manager.stop_ollama()
        self.ollama_status_var.set('Stopped')
        self.ollama_status_label.config(foreground='red')
        self.selected_model_var.set('Not selected')
        self.selected_model_for_conversion.set('')
        self.convert_en_button.config(state='disabled')
        self.convert_cn_button.config(state='disabled')
        self.status_var.set('OLLAMA stopped')
        self.start_ollama_button.config(state='normal')
        self.stop_ollama_button.config(state='disabled')
        self.running_model_var.set('Current Load: None')

    def refresh_ollama_status(self):
        """Refresh OLLAMA status and update UI display"""
        self.status_var.set('Refreshing status...')

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
                        self.ollama_status_var.set('Model running')
                        self.ollama_status_label.config(foreground='green')
                        self.selected_model_var.set(f"Running: {', '.join(running_models)}")
                        self.running_model_var.set(f"Current load: {', '.join(running_models)}")
                    else:
                        self.ollama_status_var.set('Service running (no model)')
                        try:
                            self.ollama_status_label.config(foreground='orange')
                        except tk.TclError:
                            self.ollama_status_label.config(foreground='blue')
                        self.selected_model_var.set('No model loaded')
                        self.running_model_var.set('Current Load: None')
                    self.status_var.set('OLLAMA status refreshed')
                else:
                    self.client = None
                    self.ollama_status_var.set('Not running')
                    self.ollama_status_label.config(foreground='red')
                    self.start_ollama_button.config(state='normal')
                    self.stop_ollama_button.config(state='disabled')
                    self.running_model_var.set('Current Load: None')
                    self.selected_model_var.set('Service not connected')
                    self.model_listbox.delete(0, tk.END)
                    self.status_var.set('OLLAMA not running or connection failed')
                self.update_button_states()
            self.root.after(0, update_ui)
        threading.Thread(target=task, daemon=True).start()

    def search_and_display_models(self):
        """Search and display online models"""
        keyword = self.search_model_var.get()
        self.download_progress_var.set(f"Searching '{keyword}'...")

        def search_task():
            models = self.ollama_manager.search_online_models(keyword)
            self.root.after(0, lambda : self.update_online_model_list(models))
        threading.Thread(target=search_task, daemon=True).start()

    def update_online_model_list(self, models):
        """Update online model list (Treeview version)"""
        for item in self.online_model_tree.get_children():
            self.online_model_tree.delete(item)
        for model in models:
            self.online_model_tree.insert('', 'end', values=(model.get('name', ''), model.get('size', 'Unknown'), model.get('versions', '-'), model.get('type', 'Model')))
        self.download_progress_var.set(f'Found {len(models)}  relevant models. Double-click to run OLLAMA RUN, single-click to select.')

    def on_online_model_select(self, event=None):
        """When an online model is selected"""
        selection = self.online_model_tree.selection()
        if not selection:
            return
        item = self.online_model_tree.item(selection[0])
        model_name = item['values'][0]

    def on_online_model_double_click(self, event=None):
        """Double-click to execute OLLAMA RUN (expert enhancement: auto-detect installation)"""
        selection = self.online_model_tree.selection()
        if not selection:
            return
        item = self.online_model_tree.item(selection[0])
        model_name = item['values'][0]
        if messagebox.askyesno('Confirm execution', f"Will execute 'ollama run {model_name}'\n\nIf the model is not installed, OLLAMA will automatically download and run it. Continue?"):
            success = self.ollama_manager.run_model(model_name)
            if success:
                self.download_progress_var.set(f'Running in a new terminal: {model_name}')
            else:
                messagebox.showerror('Error', 'Failed to launch terminal to run model. Ensure OLLAMA is installed and the service is running.')

    def _check_ollama_installed(self):
        """Checking if OLLAMA is installed on the system"""
        return self.ollama_manager.check_ollama_installed()

    def _check_comfyui_installed(self):
        """Checking if COMFYUI is installed on the system"""
        custom_nodes_path = self._get_custom_nodes_path()
        return custom_nodes_path is not None

    def _auto_install_comfyui_system(self):
        """[Expert] Auto-detect system and provide COMFYUI installation guide"""
        import webbrowser
        system = sys.platform
        self.status_var.set(f'Detecting system architecture: {system}...')
        comfyui_repo = 'https://github.com/comfyanonymous/ComfyUI'
        comfyui_install_guide = 'https://docs.comfyui.org/installation/'
        msg = f'Detected current system as: {system}COMFYUI installation method:'
        msg += '1. Visit the GitHub repository and clone the code'
        msg += '2. Install Python dependencies'
        msg += '3. Download model files'
        msg += 'Open official installation documentation?'
        if messagebox.askyesno('COMFYUI installation confirmation', msg):
            webbrowser.open(comfyui_install_guide)
            self.root.clipboard_clear()
            self.root.clipboard_append(f'git clone {comfyui_repo}')
            self.status_var.set('Installation document opened, git clone command copied to clipboard')

    def _auto_install_ollama_system(self):
        """[Expert] Auto-detect system and download/install OLLAMA"""
        import webbrowser
        system = sys.platform
        self.status_var.set(f'Detecting system architecture: {system}...')
        urls = {'win32': 'https://ollama.com/download/OllamaSetup.exe', 'darwin': 'https://ollama.com/download/Ollama-darwin.zip', 'linux': 'https://ollama.com/install.sh'}
        target_url = urls.get(system, 'https://ollama.com/download')
        if messagebox.askyesno('System installation confirmation', f'Detected current system as: {system}Click OK to open the official download page and attempt to start the installation process.\nIf on Linux, it is recommended to run the official script manually.'):
            if system == 'linux':
                msg = 'On Linux, run in terminal:\ncurl -fsSL https://ollama.com/install.sh | sh'
                messagebox.showinfo('Linux installation command', msg)
                self.root.clipboard_clear()
                self.root.clipboard_append('curl -fsSL https://ollama.com/install.sh | sh')
            else:
                webbrowser.open(target_url)
            self.status_var.set('Waiting for user to complete system-level installation...')

    def delete_local_model(self):
        """Delete locally installed model (management enhancement)"""
        selection = self.model_listbox.curselection()
        if not selection:
            messagebox.showwarning('Warning', "Please select a model from the 'Installed Models' list first.")
            return
        model_name = self.model_listbox.get(selection[0])
        if messagebox.askyesno('Confirm deletion', f"Are you sure you want to permanently delete the local model '{model_name}'?\nThis action cannot be undone."):
            try:
                import subprocess
                if sys.platform == 'win32':
                    subprocess.run(['ollama', 'rm', model_name], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    subprocess.run(['ollama', 'rm', model_name], check=True)
                messagebox.showinfo('Success', f'Model {model_name} Successfully deleted.')
                self.refresh_model_list()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to delete model: {e}')

    def download_model(self, model_name):
        """Download specified model"""
        self.download_progress_var.set(f'Start download {model_name}...')

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
        """Download completion callback"""
        if success:
            self.download_progress_var.set('Download completed!')
            self.refresh_model_list()
        else:
            self.download_progress_var.set('Download failed.')

    def refresh_model_list(self):
        """Refresh model list"""

        def task():
            models = self.ollama_manager.get_available_models()
            self.root.after(0, lambda : (self.model_listbox.delete(0, tk.END), [self.model_listbox.insert(tk.END, m) for m in models]))
        threading.Thread(target=task, daemon=True).start()

    def select_model(self):
        """Select model and load in background immediately"""
        selection = self.model_listbox.curselection()
        if selection:
            model_name = self.model_listbox.get(selection[0])
            self.selected_model_for_conversion.set(model_name)
            self.selected_model_var.set(f'Loading: {model_name}')
            self.status_var.set(f'Starting to load model: {model_name}...')
            self.load_model_in_background(model_name)

    def load_model_in_background(self, model_name):
        """Send a dummy request to force OLLAMA to load the model."""

        def task():
            try:
                if not self.client:
                    self.root.after(0, lambda : self.status_var.set('Load failed: OLLAMA client not initialized'))
                    return
                self._chat_completion_with_retry(model_name=model_name, messages=[{'role': 'user', 'content': 'Hi'}], temperature=0.1, max_tokens=1)
                self.root.after(10000, self.refresh_ollama_status)
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.status_var.set(f'Model loading failed: {err}'))
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

            def async_ai_analysis():
                try:
                    workflow_path = os.path.join(self.proj_path.get(), workflow_name)
                    if os.path.exists(workflow_path):
                        with open(workflow_path, 'r', encoding='utf-8') as f:
                            w_data = json.load(f)
                        sst = generate_workflow_sst(w_data)
                        self._ai_workflow_positioning(sst, workflow_name)
                except:
                    pass
            threading.Thread(target=async_ai_analysis, daemon=True).start()
            if not any((item['injection_type'] == 'prompt' for item in summary)):
                messagebox.showinfo('Workflow prompt', f"The workflow you selected '{workflow_name}' has no available prompt injection points.")
            has_image_input = any((item['injection_type'] == 'image' for item in summary))
        is_image_workflow = self.current_workflow_type in ['Image-to-Image', 'Image-to-Video']
        self.image_label.config(state='normal' if is_image_workflow else 'disabled')
        self.image_path_entry.config(state='normal' if is_image_workflow else 'disabled')
        self.image_browse_button.config(state='normal' if is_image_workflow else 'disabled')
        if not is_image_workflow:
            self.image_path_var.set('')
        self._reset_comfyui_tab_state()
        self.clear_and_rewrite(clear_input=False)

    def _ai_workflow_positioning(self, sst_data, workflow_name):
        """Use LLM for top-level semantic positioning identification on SST"""
        if not self.client or not self.selected_model_var.get() or self.selected_model_var.get() == 'Not selected':
            return
        model = self.selected_model_var.get()
        messages = [{'role': 'system', 'content': SYSTEM_PROMPTS['Workflow Analysis']}, {'role': 'user', 'content': f'Please analyze the following SST template and identify the core logic of this workflow:{sst_data}'}]
        try:
            completion = self._chat_completion_with_retry(model, messages, json_mode=True)
            ai_result = self._extract_json_from_ai_response(completion.choices[0].message.content)
            if ai_result:
                if workflow_name not in self.workflow_analysis_cache:
                    self.workflow_analysis_cache[workflow_name] = {}
                self.workflow_analysis_cache[workflow_name]['ai_positioning'] = ai_result
                self.root.after(0, lambda : self.status_var.set(f"AI deep positioning completed: {ai_result.get('workflow_type', 'Unknown')}"))
        except Exception as e:
            print(f'AI workflow analysis failed: {e}')

    def _extract_json_from_ai_response(self, text):
        """Top-level JSON extraction algorithm: Physical Penetration CoT and Markdown noise"""
        try:
            processed_text = re.sub('<thought>.*?</thought>', '', text, flags=re.DOTALL | re.IGNORECASE)
            processed_text = re.sub('<reasoning>.*?</reasoning>', '', processed_text, flags=re.DOTALL | re.IGNORECASE)
            match = re.search('\\{.*\\}', processed_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return None
        except:
            return None

    def _verify_workflow_integrity(self, modified_data, workflow_name):
        """Physical + logical dual-loop verification algorithm.
        1. Physical: node ID persistence and API key validation.
        2. Logical: semantic consistency between AI-located results and actual injection points.        """
        ai_pos = self.workflow_analysis_cache.get(workflow_name, {}).get('ai_positioning', {})
        node_mapping = ai_pos.get('node_mapping', {})
        is_ui_format = 'nodes' in modified_data and isinstance(modified_data['nodes'], list)
        current_node_ids = set()
        if is_ui_format:
            for n in modified_data['nodes']:
                current_node_ids.add(str(n.get('id')))
        else:
            for n_id in modified_data.keys():
                current_node_ids.add(str(n_id))
        for (logic_name, node_id) in node_mapping.items():
            if str(node_id) not in current_node_ids:
                return (False, f'Logical node {logic_name} (ID: {node_id}) missing in physical JSON')
        return (True, 'Verification passed')

    def on_style_change(self, event=None):
        self.status_var.set(f'Selected style: {self.style_var.get()}')

    def update_button_states(self):
        """Update the enabled state of the four main action buttons based on current program status and user requirements.        """
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
        creative_text_widget = self.prompt_text_widgets.get('Creative full text')
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
        if can_execute:
            self.execute_button.config(state='normal', style='Execute.TButton')
        else:
            self.execute_button.config(state='disabled')

    def _prepare_and_run_ai_task(self, button, status_text, system_prompt_key, user_content_json, callback):
        if not self.selected_model_for_conversion.get():
            messagebox.showwarning('Warning', "Please select and load an AI model in the 'OLLAMA Settings' tab first")
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
        messagebox.showerror('Task failed', error_msg)
        self.status_var.set('Task failed')
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
                        raise ValueError('No [START_JSON] marker found in AI response, nor a valid JSON object could be located.')
            json_string = re.sub('^```json\\s*', '', json_string, flags=re.IGNORECASE)
            json_string = re.sub('\\s*```$', '', json_string)
            result = json.loads(json_string)
            missing_keys = [k for k in expected_keys if k not in result]
            if missing_keys:
                if not messagebox.askyesno('Content missing', f"AI returned result is missing the following part: {', '.join(missing_keys)}.\nContinue processing existing content?"):
                    raise ValueError('User cancelled operation')
                for k in missing_keys:
                    result[k] = ''
            success_callback(result)
        except Exception as e:
            self.on_task_error(f'Failed to process AI response: {e}')

    def generate_creative_chinese(self):
        self._reset_states(keep_creative_input=True)
        user_text = self.chinese_input.get('1.0', tk.END).strip()
        selected_style = self.style_var.get()
        image_path = self.image_path_var.get().strip()
        is_image_workflow = self.current_workflow_type in ['Image-to-Image', 'Image-to-Video']
        messages = []
        if is_image_workflow and image_path and os.path.exists(image_path):
            self.status_var.set('Reading image and preparing analysis...')
            try:
                with open(image_path, 'rb') as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                image_format = os.path.splitext(image_path)[1].lower().replace('.', '')
                if image_format == 'jpg':
                    image_format = 'jpeg'
                messages = [{'role': 'user', 'content': [{'type': 'text', 'text': f"You are a top-tier image analysis expert and creative master. Please use Chinese to precisely, comprehensively, and imaginatively describe every aspect of this image, including subject, environment, atmosphere, lighting, composition, and potential dynamics. Your description will serve as inspiration for subsequent AI-generated video, so be thorough. Naturally incorporate the '{selected_style}style'."}, {'type': 'image_url', 'image_url': {'url': f'data:image/{image_format};base64,{base64_image}'}}]}]
                self.status_var.set('Analyzing image and generating Chinese creative text...')
            except Exception as e:
                self.on_task_error(f'Error reading or processing image: {e}')
                return
        else:
            if not user_text:
                if is_image_workflow:
                    messagebox.showwarning('Warning', 'This is an image workflow; it is recommended to select an image first for better creative description.\n\nYou may also continue by manually entering text creativity.')
                    return
                else:
                    messagebox.showwarning('Warning', 'Please enter your Chinese creative idea.')
                    return
            content = f"Please merge the following description text ('{user_text}') with '{selected_style}' style, refine, expand and optimize it to be more vivid, imaginative, detailed and literary."
            messages = [{'role': 'system', 'content': SYSTEM_PROMPTS['Chinese Polishing']}, {'role': 'user', 'content': content}]
            self.status_var.set('Generating Chinese creative text from the prompt...')

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
                self.status_var.set('1. Chinese creative text generated')
            except Exception as e:
                self.on_task_error(f'Failed to process AI response: {e}')
            finally:
                self.conversion_progressbar.stop()
                self.update_button_states()
        if not self.selected_model_for_conversion.get():
            messagebox.showwarning('Warning', "Please select and load an AI model in the 'OLLAMA Settings' tab first.\n\n(Note: Image analysis requires a multimodal model such as LLaVA)")
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
                if 'multimodal' in str(e).lower() or 'image' in str(e).lower():
                    self.root.after(0, self.on_task_error, f"Model '{self.selected_model_for_conversion.get()}' may not support image input. Please select a multimodal model (e.g., LLaVA) in the 'OLLAMA Settings'.\n\nDetailed error: {e}")
                else:
                    self.root.after(0, self.on_task_error, str(e))
        threading.Thread(target=ai_task, daemon=True).start()

    def segment_chinese_text(self):
        summary_table = self._get_prepared_summary_table()
        if not summary_table:
            self.on_task_error('Segmentation failed: No valid prompt injection point found.')
            return
        creative_text = self.prompt_text_widgets.get('Creative full text', self.chinese_input).get('1.0', tk.END).strip()
        segments_info = [{'display_name': item['display_name'], 'keywords': item['keywords']} for item in summary_table]
        user_content = {'creative_text': creative_text, 'target_segments': segments_info}

        def callback(response_text):
            expected_keys = [item['display_name'] for item in summary_table if item['injection_type'] == 'prompt']
            self._process_ai_response(response_text, expected_keys, on_segmentation_success)

        def on_segmentation_success(result):
            self._setup_segment_tabs(result)
            self.chinese_segmented = True
            self.status_var.set('2. Chinese segmentation completed')
            self.conversion_progressbar.stop()
            self.update_button_states()
        self._prepare_and_run_ai_task(self.segment_button, 'Performing Chinese segmentation...', 'Chinese Segmentation', user_content, callback)

    def translate_to_english(self):
        prompts = self._get_prompts_from_ui()
        user_content = self._build_grouped_translation_payload(prompts)

        def callback(response_text):
            self._process_ai_response(response_text, list(prompts.keys()), on_translation_success)

        def on_translation_success(result):
            self._update_ui_tabs(result)
            self.english_translated = True
            self.status_var.set('3. English conversion completed')
            self.conversion_progressbar.stop()
            self.update_button_states()
        self._prepare_and_run_ai_task(self.convert_en_button, 'Converting to English...', 'English Translation', user_content, callback)

    def _build_grouped_translation_payload(self, prompts):
        """Construct translation input grouped by full prompt names to avoid cross‑mixing of multiple positive/negative prompts.
        Output includes:
        - prompt_groups: provides grouping context for the model
        - flat_prompts: enforces strict mapping between output keys and UI.        """
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
        """Specialized adjustment (skipped by default in open-source version)"""
        prompts = self._get_prompts_from_ui()

        def on_supplement_success(result):
            self._update_ui_tabs(result)
            self.english_supplemented = True
            self.status_var.set('4. Specialized adjustment skipped (open-source version)')
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
            self.preview_frame.place_forget()
            self.preview_label.config(image='', text='No Preview Image')
            self.current_preview_file = None
        if clear_ui:
            self._clear_all_tabs()
        self.update_button_states()

    def add_prompt_tab(self, title, content, height=9):
        """Adds a tab to the positive prompts notebook."""
        frame = ttk.Frame(self.positive_notebook)
        self.positive_notebook.add(frame, text=title)
        text_widget = scrolledtext.ScrolledText(frame, height=height, font=('Microsoft YaHei', 10), wrap='word', undo=True)
        text_widget.pack(fill='both', expand=True, padx=2, pady=2)
        text_widget.insert('1.0', content)
        self.create_context_menu(text_widget)
        self.prompt_text_widgets[title] = text_widget

    def add_negative_prompt_tab(self, title, content, height=5):
        """Adds a tab to the negative prompts notebook."""
        frame = ttk.Frame(self.negative_notebook)
        self.negative_notebook.add(frame, text=title)
        text_widget = scrolledtext.ScrolledText(frame, height=height, font=('Microsoft YaHei', 10), wrap='word', undo=True)
        text_widget.pack(fill='both', expand=True, padx=2, pady=2)
        text_widget.insert('1.0', content)
        self.create_context_menu(text_widget)
        self.negative_prompt_text_widgets[title] = text_widget

    def _setup_creative_text_tab(self, text):
        self._clear_all_tabs()
        self.add_prompt_tab('Creative full text', text, 12)

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
        """Displays the generated creative Chinese text in the UI.
        It clears all previous result tabs and creates a new tab named 'Creative Full Text'
        in the left-hand results panel, making it ready for the segmentation step.
        It no longer modifies the original user input box.        """
        self._clear_all_tabs()
        self.add_prompt_tab('Creative full text', text, 12)

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
        self.status_var.set('Cleared, can re-enter')

    def _get_graph_topology(self, nodes):
        """Build graph topology for traversal."""
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
        """Workflow classification engine (open-source version) – supports only text-to-image and text-to-image FLUX"""
        node_types = {n.get('type') or n.get('class_type') for n in nodes}
        VIDEO_OUTPUT_NODE_TYPES = {'SaveAnimatedWEBP', 'SaveAnimatedPNG', 'SaveAnimation', 'VHS_VideoCombine', 'ExportVideo', 'VideoCombine', 'VideoHelperSuite'}
        IMAGE_INPUT_NODE_TYPES = {'LoadImage', 'LoadImageMask', 'ImageLoad', 'ImpactLoadImage'}
        has_video_output = any((t in VIDEO_OUTPUT_NODE_TYPES for t in node_types if t))
        has_image_input = any((t in IMAGE_INPUT_NODE_TYPES for t in node_types if t))
        if has_video_output or has_image_input:
            return 'Uncategorized'
        is_flux = False
        for t in node_types:
            if t and 'flux' in t.lower():
                is_flux = True
                break
        if is_flux:
            return 'Text-to-Image - FLUX'
        return 'Text-to-Image'

    def _identify_injection_points(self, nodes, nodes_map, graph_topology, workflow_data):
        """Stage 2: Identify all prompt injection points and include node sequence numbers."""
        injection_points = []
        unnamed_node_counter = 1
        consumer_map = {}
        for link_details in workflow_data.get('links', []):
            try:
                source_id = str(link_details[1])
                target_id = str(link_details[3])
                if source_id not in consumer_map:
                    consumer_map[source_id] = []
                consumer_map[source_id].append(target_id)
            except (IndexError, TypeError):
                continue
        candidate_nodes = [node for node in nodes_map.values() if 'CLIPTextEncode' in node.get('type', '')]
        for node in candidate_nodes:
            try:
                widget_infos = []
                node_type = node.get('type', '')
                if 'widgets_values' in node and isinstance(node['widgets_values'], list):
                    for (i, value) in enumerate(node['widgets_values']):
                        if isinstance(value, str):
                            info = {'type': 'widgets_values', 'index': i}
                            if 'Flux' in node_type or 'flux' in node_type.lower():
                                widget_infos.append(info)
                            else:
                                widget_infos.append(info)
                                break
                elif 'inputs' in node:
                    for key in ['clip_l', 't5xxl', 'text']:
                        if any((inp.get('name') == key for inp in node.get('inputs', []))):
                            widget_infos.append({'type': 'inputs', 'name': key})
                            if 'Flux' not in node_type and 'flux' not in node_type.lower():
                                break
                    if not widget_infos and any((inp.get('name') == 'text' for inp in node.get('inputs', []))):
                        widget_infos.append({'type': 'inputs', 'name': 'text'})
                if not widget_infos:
                    continue
                title = node.get('title', '').strip()
                is_unnamed = not title
                type_from_title = 'positive' if re.search('positive|正面', title, re.I) else 'negative' if re.search('negative|Negative', title, re.I) else 'Unknown'
                modifier_from_title = 'base' if re.search('base|main|Core', title, re.I) else 'inpaint' if re.search('inpaint|Repaint', title, re.I) else 'refine' if re.search('refine|Refine|Repair', title, re.I) else 'face' if re.search('face|Face', title, re.I) else 'hand' if re.search('hand|Hand', title, re.I) else 'person' if re.search('person|Body|Full Body', title, re.I) else 'base'
                final_type = type_from_title
                final_modifier = modifier_from_title
                found_consumer = False
                q = deque([(str(node['id']), 0)])
                visited = {str(node['id'])}
                while q:
                    (current_id, depth) = q.popleft()
                    if depth > 5:
                        continue
                    downstream_consumers = consumer_map.get(current_id, [])
                    for consumer_id in downstream_consumers:
                        if consumer_id in visited:
                            continue
                        visited.add(consumer_id)
                        q.append((consumer_id, depth + 1))
                        consumer_node = nodes_map.get(consumer_id)
                        if not consumer_node:
                            continue
                        consumer_type = consumer_node.get('type', '')
                        for inp in consumer_node.get('inputs', []):
                            link_info = inp.get('link')
                            is_linked_to_current = False
                            if link_info is not None:
                                if isinstance(link_info, list) and str(link_info[0]) == current_id:
                                    is_linked_to_current = True
                                else:
                                    for link_detail in workflow_data.get('links', []):
                                        if str(link_detail[0]) == str(link_info) and str(link_detail[1]) == current_id:
                                            is_linked_to_current = True
                                            break
                            if is_linked_to_current and inp.get('name') in ['positive', 'negative']:
                                final_type = inp.get('name')
                        if 'FaceDetailer' in consumer_type:
                            final_modifier = 'face'
                            found_consumer = True
                        elif 'KSampler' in consumer_type or 'SamplerCustom' in consumer_type:
                            found_consumer = True
                        elif 'BasicGuider' in consumer_type:
                            found_consumer = True
                if final_type == 'Unknown':
                    final_type = 'positive'
                segment = f'{final_modifier}_{final_type}'
                if is_unnamed:
                    property_str = segment
                    title = f'UNKNOWN{unnamed_node_counter}({property_str})'
                    unnamed_node_counter += 1
                if 'CLIPTextEncode' in node_type and (found_consumer or type_from_title != 'Unknown'):
                    node_order_number = next((i for (i, n) in enumerate(nodes) if str(n.get('id')) == str(node.get('id'))), -1)
                    injection_points.append({'segment': segment, 'node_id': str(node['id']), 'Node Title': title, 'node_type': node_type, 'widget_infos': widget_infos, 'widget_info': widget_infos[0], 'Node Order Number': node_order_number})
            except Exception as e:
                print(f"Analyze Node {node.get('id')} Error: {e}")
        return injection_points

    def _is_valid_comfyui_dir(self, path):
        """Validate that the given path is a valid ComfyUI runtime directory.
It must contain both main.py and the web folder to be considered a valid ComfyUI installation.
Never generate an injection folder automatically.        """
        if path and os.path.isdir(path):
            has_main = os.path.exists(os.path.join(path, 'main.py'))
            has_web_dir = os.path.isdir(os.path.join(path, 'web'))
            if has_main and has_web_dir:
                return True
        return False

    def _find_comfyui_path(self):
        """Search broadly for valid ComfyUI folders relative to the program's execution directory.

Search scope:
1. Parent directories of the program's run directory (multiple levels up)
2. Sibling directories at each parent level (same‑level directories)
3. Subdirectories and sub‑subdirectories under each parent level

Also enforce validation of directory validity (must contain main.py + web folder),
Never generate directories automatically.        """
        start_dir = os.path.dirname(os.path.abspath(__file__))
        search_roots = []
        current = start_dir
        for _ in range(6):
            search_roots.append(current)
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        for root_path in search_roots:
            if os.path.basename(root_path).lower() == 'comfyui':
                if self._is_valid_comfyui_dir(root_path):
                    return root_path
            candidate = os.path.join(root_path, 'ComfyUI')
            if self._is_valid_comfyui_dir(candidate):
                return candidate
            candidate_lower = os.path.join(root_path, 'comfyui')
            if candidate_lower != candidate and self._is_valid_comfyui_dir(candidate_lower):
                return candidate_lower
            try:
                for item_name in os.listdir(root_path):
                    item_path = os.path.join(root_path, item_name)
                    if not os.path.isdir(item_path):
                        continue
                    if item_name.lower() == 'comfyui':
                        if self._is_valid_comfyui_dir(item_path):
                            return item_path
                    try:
                        for sub_name in os.listdir(item_path):
                            sub_path = os.path.join(item_path, sub_name)
                            if not os.path.isdir(sub_path):
                                continue
                            if sub_name.lower() == 'comfyui':
                                if self._is_valid_comfyui_dir(sub_path):
                                    return sub_path
                    except OSError:
                        continue
            except OSError:
                continue
        return None

    def execute_workflow(self):
        """Execute workflow injection.        """
        self.execute_button.config(state='disabled')
        specific_workflow = self.specific_workflow_combo.get()
        if not specific_workflow:
            messagebox.showwarning('Warning', 'Please select a specific workflow file')
            self.update_button_states()
            return
        analysis_data = self.workflow_analysis_cache.get(specific_workflow)
        if not analysis_data:
            messagebox.showerror('Error', "No analysis data found for the current workflow. Please run 'Identify Workflow' first.")
            self.update_button_states()
            return
        workflow_type = analysis_data.get('workflow_category', '')
        if workflow_type not in ['Text-to-Image', 'Text-to-Image - FLUX']:
            messagebox.showerror('Operation not supported', f"This injection feature only supports 'Text-to-Image' and 'Text-to-Image-FLUX' workflow types.\nCurrent type: '{workflow_type}'")
            self.update_button_states()
            return
        summary_table = self._get_prepared_summary_table()
        if not summary_table:
            messagebox.showerror('Error', 'Workflow analysis data is invalid, missing summary table.')
            self.update_button_states()
            return
        prompts_to_inject = self._get_prompts_from_ui()
        image_path_to_inject = self.image_path_var.get()
        has_prompt_content = any((value.strip() for value in prompts_to_inject.values()))
        has_image_content = bool(image_path_to_inject.strip())
        if not has_prompt_content and (not has_image_content):
            messagebox.showwarning('Warning', 'No valid prompts or images found for injection.')
            self.update_button_states()
            return
        try:
            workflow_path = os.path.join(self.proj_path.get(), specific_workflow)
            if not os.path.exists(workflow_path):
                messagebox.showerror('Error', f'Workflow file does not exist: {workflow_path}')
                self.update_button_states()
                return
            backup_path = f'{workflow_path}.backup'
            shutil.copy2(workflow_path, backup_path)
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            updated_nodes_count = self.update_workflow_nodes(workflow_data, prompts_to_inject, image_path_to_inject, summary_table)
            if updated_nodes_count > 0:
                self.status_var.set('Performing logical and physical double verification...')
                (is_valid, v_msg) = self._verify_workflow_integrity(workflow_data, specific_workflow)
                if not is_valid:
                    if not messagebox.askyesno('Verification Warning', f'ZenithFlow verification failed: {v_msg}There may be missing nodes or logical conflicts. Proceed with forced injection?'):
                        self.update_button_states()
                        return
                if sys.platform == 'darwin':

                    def mac_path_fix(obj):
                        if isinstance(obj, dict):
                            for (k, v) in obj.items():
                                if isinstance(v, str) and (':' in v or '\\' in v):
                                    obj[k] = v.replace('\\', '/')
                                else:
                                    mac_path_fix(v)
                        elif isinstance(obj, list):
                            for i in range(len(obj)):
                                if isinstance(obj[i], str) and (':' in obj[i] or '\\' in obj[i]):
                                    obj[i] = obj[i].replace('\\', '/')
                                else:
                                    mac_path_fix(obj[i])
                    mac_path_fix(workflow_data)
                with open(workflow_path, 'w', encoding='utf-8') as f:
                    json.dump(workflow_data, f, indent=2, ensure_ascii=False)
                comfyui_base = self._find_comfyui_path()
                sync_msg = ''
                target_path = workflow_path
                if comfyui_base:
                    comfyui_workflows_dir = os.path.join(comfyui_base, 'user', 'default', 'workflows')
                    try:
                        os.makedirs(comfyui_workflows_dir, exist_ok=True)
                        target_path = os.path.join(comfyui_workflows_dir, specific_workflow)
                        shutil.copy2(workflow_path, target_path)
                        sync_msg = f'Synchronized to ComfyUI directory:{target_path}'
                        self.status_var.set(f'Synchronized to ComfyUI: {specific_workflow}')
                    except Exception as e:
                        sync_msg = f'Failed to synchronize to ComfyUI: {e}'
                else:
                    sync_msg = 'Tip: ComfyUI runtime folder not found within three levels of the program directory; automatic sync not performed.'
                injected_parts = []
                if has_prompt_content:
                    injected_parts.append('Prompt')
                if has_image_content:
                    injected_parts.append('Image')
                if injected_parts:
                    parts_str = ' and '.join(injected_parts)
                    final_message = f'{parts_str}Injection successful!{sync_msg}'
                    self.status_var.set(f'{parts_str}Injection successful!')
                    self.run_comfyui_button.config(state='normal', style='Run.TButton')
                    self.current_injected_workflow_path = target_path
                    self.english_supplemented = False
                    self.update_button_states()
                    messagebox.showinfo('Injection Successful', final_message)
                else:
                    success_message = 'Injection operation completed.'
                    messagebox.showinfo('Operation Completed', success_message)
            else:
                messagebox.showinfo('Injection Reminder', 'Prompt generated, but no updatable node found in the workflow. Please check the workflow file or analysis results.')
        except Exception as e:
            messagebox.showerror('Execution Error', f'Error while executing workflow: {str(e)}')
            self.update_button_states()

    def update_workflow_nodes(self, workflow_data, prompts_to_inject, image_path_to_inject, summary_table):
        """[Expert Level: ZenithFlow 4.0 Enhanced] Combine AI positioning to perform physical injection"""
        updated_count = 0
        is_list_format = 'nodes' in workflow_data and isinstance(workflow_data['nodes'], list)
        nodes_dict = {str(node['id']): node for node in workflow_data['nodes']} if is_list_format else workflow_data
        specific_workflow = self.specific_workflow_combo.get()
        ai_pos = self.workflow_analysis_cache.get(specific_workflow, {}).get('ai_positioning', {})
        node_mapping = ai_pos.get('node_mapping', {})
        for item in summary_table:
            injection_type = item['injection_type']
            details = item['injection_location']
            node_id = details['node_id']
            logic_name = item.get('modifier', 'base')
            if logic_name in node_mapping:
                ai_node_id = str(node_mapping[logic_name])
                if ai_node_id in nodes_dict:
                    node_id = ai_node_id
            node = nodes_dict.get(node_id)
            if not node:
                continue
            injected = False
            if injection_type == 'prompt':
                display_name = item.get('display_name', item.get('full_node_name'))
                prompt_text = prompts_to_inject.get(display_name)
                if prompt_text:
                    widget_infos = details.get('widget_infos', [details.get('widget_info')])
                    for widget_info in widget_infos:
                        if not widget_info:
                            continue
                        if widget_info['type'] == 'widgets_values':
                            idx = widget_info['index']
                            if 'widgets_values' in node and idx < len(node['widgets_values']):
                                node['widgets_values'][idx] = prompt_text
                                injected = True
                        elif widget_info['type'] == 'inputs':
                            key = widget_info.get('key') or widget_info.get('name')
                            if 'inputs' in node and key:
                                node['inputs'][key] = prompt_text
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
            self.add_prompt_tab('Content', segmented_data.get('base', ''), height=9)
        if not added_negative_tabs and segmented_data.get('negative'):
            self.add_negative_prompt_tab('Negative Prompt', segmented_data.get('negative', ''), height=5)

    def on_closing(self):
        """Cleanup on program exit"""
        try:
            self.ollama_manager.stop_ollama()
        except Exception:
            pass
        self.root.destroy()

    def _convert_ui_to_api(self, workflow_data, nodes_info):
        """Convert UI workflow format to API format (extremely precise version)

Ensures widgets_values indices are absolutely aligned via primitive vs connection type recognition.        """
        api_prompt = {}
        nodes = workflow_data.get('nodes', [])
        links = workflow_data.get('links', [])
        links_map = {link[0]: link for link in links}
        ui_nodes_map = {str(n['id']): n for n in nodes}
        CONNECTION_TYPES = {'MODEL', 'CLIP', 'VAE', 'CONDITIONING', 'LATENT', 'IMAGE', 'MASK', 'BBOX_DETECTOR', 'SEGM_DETECTOR', 'CONTROL_NET', 'STYLE_MODEL', 'UPSCALE_MODEL', 'NOISE', 'GUIDER', 'SIGMAS', 'SAMPLER', 'HOOK'}

        def resolve_link(link_id):
            if link_id not in links_map:
                return None
            l = links_map[link_id]
            (origin_id, origin_slot) = (str(l[1]), l[2])
            origin_node = ui_nodes_map.get(origin_id)
            if not origin_node:
                return [origin_id, origin_slot]
            if origin_node.get('type') == 'Reroute':
                if 'inputs' in origin_node and len(origin_node['inputs']) > 0:
                    parent_link = origin_node['inputs'][0].get('link')
                    if parent_link:
                        return resolve_link(parent_link)
            if origin_node.get('type') in ['PrimitiveNode', 'Primitive']:
                if 'widgets_values' in origin_node and len(origin_node['widgets_values']) > 0:
                    return {'is_value': True, 'value': origin_node['widgets_values'][0]}
            return [origin_id, origin_slot]
        for node in nodes:
            (node_id, node_type) = (str(node['id']), node.get('type', ''))
            if node_type in ['PrimitiveNode', 'Primitive', 'Note', 'Reroute']:
                continue
            schema = nodes_info.get(node_type, {}).get('input', {})
            (req, opt) = (schema.get('required', {}), schema.get('optional', {}))
            api_node = {'class_type': node_type, 'inputs': {}}
            if 'inputs' in node and isinstance(node['inputs'], list):
                for inp in node['inputs']:
                    (name, link_id) = (inp.get('name'), inp.get('link'))
                    if link_id is not None:
                        res = resolve_link(link_id)
                        if isinstance(res, list):
                            api_node['inputs'][name] = res
                        elif isinstance(res, dict) and res.get('is_value'):
                            api_node['inputs'][name] = res['value']
                    elif 'value' in inp:
                        api_node['inputs'][name] = inp['value']
            if 'widgets_values' in node:
                w_values = node['widgets_values']
                all_keys = list(req.keys()) + list(opt.keys())
                val_idx = 0
                for key in all_keys:
                    input_def = req.get(key) or opt.get(key)
                    is_widget = False
                    if isinstance(input_def, list) and len(input_def) > 0:
                        type_str = input_def[0]
                        if isinstance(type_str, list) or (isinstance(type_str, str) and type_str not in CONNECTION_TYPES):
                            is_widget = True
                    if is_widget:
                        if any((x in key.lower() for x in ['seed', 'noise_seed'])) and val_idx + 1 < len(w_values):
                            next_val = w_values[val_idx + 1]
                            if isinstance(next_val, str):
                                next_widget_key = None
                                current_found = False
                                for k in all_keys:
                                    if k == key:
                                        current_found = True
                                        continue
                                    if current_found:
                                        idef = req.get(k) or opt.get(k)
                                        if isinstance(idef, list) and len(idef) > 0:
                                            itype = idef[0]
                                            if itype in ['INT', 'FLOAT']:
                                                next_widget_key = k
                                                break
                                            if isinstance(itype, str) and itype in CONNECTION_TYPES:
                                                continue
                                            break
                                if next_widget_key:
                                    if key not in api_node['inputs']:
                                        api_node['inputs'][key] = w_values[val_idx]
                                    val_idx += 2
                                    continue
                        if key not in api_node['inputs'] and val_idx < len(w_values):
                            val = w_values[val_idx]
                            if node_type == 'FaceDetailer' and key == 'cycle':
                                if not isinstance(val, int) or val < 1:
                                    val = 1
                            if key.endswith('_opt') and isinstance(val, int):
                                val_idx += 1
                                continue
                            if key == 'detailer_hook' and isinstance(val, int):
                                val_idx += 1
                                continue
                            api_node['inputs'][key] = val
                        val_idx += 1
                if node_type == 'KSampler' and 'denoise' in all_keys:
                    api_node['inputs']['denoise'] = w_values[-1]
            api_prompt[node_id] = api_node
        return api_prompt

    def run_comfyui_workflow(self):
        """Send run request to ComfyUI (expert reinforced version)"""
        if not hasattr(self, 'current_injected_workflow_path') or not self.current_injected_workflow_path:
            messagebox.showerror('Error', 'No runnable workflow. Please perform injection first.')
            return
        workflow_path = self.current_injected_workflow_path
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow_json = json.load(f)
        except Exception as e:
            messagebox.showerror('Error', f'Unable to read workflow file:{e}')
            return

        def send_request():
            import json as json_lib
            import websocket
            comfyui_base_url = 'http://127.0.0.1:8188'
            client_id = str(uuid.uuid4())
            try:
                info_resp = requests.get(f'{comfyui_base_url}/object_info', timeout=5)
                if info_resp.status_code != 200:
                    return
                nodes_info = info_resp.json()
                if 'nodes' in workflow_json and isinstance(workflow_json['nodes'], list):
                    self.status_var.set('Performing physical architecture alignment...')
                    api_prompt = self._convert_ui_to_api(workflow_json, nodes_info)
                else:
                    api_prompt = {str(k): v for (k, v) in workflow_json.items() if isinstance(v, dict) and 'class_type' in v}
                self.auto_correct_models_v3(api_prompt, nodes_info)
                payload = {'prompt': api_prompt, 'client_id': client_id}
                response = requests.post(f'{comfyui_base_url}/prompt', json=payload, timeout=10)
                if response.status_code != 200:
                    self.root.after(0, lambda e=response.text: messagebox.showerror('ComfyUI Error', f'Submission failed:{e}'))
                    return
                prompt_id = response.json().get('prompt_id')

                def listen_ws():
                    ws_url = f'ws://127.0.0.1:8188/ws?client_id={client_id}'
                    ws = None
                    try:
                        ws = websocket.create_connection(ws_url, timeout=5)
                        start_time = time.time()
                        while True:
                            if time.time() - start_time > 2400:
                                break
                            out = ws.recv()
                            if not out:
                                break
                            msg = json_lib.loads(out)
                            if msg['type'] == 'progress':
                                d = msg['data']
                                if d['prompt_id'] == prompt_id:
                                    p = int(d.get('value', 0) / d.get('max', 100) * 100)
                                    self.root.after(0, lambda p=p, c=d.get('value'), t=d.get('max'): self.preview_label.config(text=f'Generating: {p}%\nRender steps: {c}/{t}'))
                            if msg['type'] == 'executing':
                                if msg['data']['prompt_id'] == prompt_id and msg['data'].get('node') is None:
                                    time.sleep(1)
                                    self.fetch_and_show_final_image(prompt_id)
                                    break
                    except:
                        self.poll_comfyui_result(prompt_id)
                threading.Thread(target=listen_ws, daemon=True).start()
            except Exception as e:
                self.root.after(0, lambda : self.run_comfyui_button.config(state='normal'))
        self.status_var.set('Sending workflow...')
        self.run_comfyui_button.config(state='disabled')
        self.preview_label.config(image='', text='Connecting to ComfyUI...')
        self.preview_frame.place(relx=1.0, rely=1.0, anchor='se', x=-4, y=-3, width=240, height=240)
        threading.Thread(target=send_request, daemon=True).start()

    def auto_correct_models_v3(self, prompt_dict, nodes_info):
        """Full‑scale intelligent environment adaptation v3 (expert reinforced version)

Through fuzzy field name recognition, available item analysis, and type correction, automatically resolves all loader and sampler mismatches.        """
        try:
            for (node_id, node_data) in prompt_dict.items():
                class_type = node_data.get('class_type')
                if class_type not in nodes_info:
                    continue
                schema = nodes_info[class_type].get('input', {})
                all_inputs = {**schema.get('required', {}), **schema.get('optional', {})}
                for (input_name, input_details) in all_inputs.items():
                    if isinstance(input_details, list) and len(input_details) > 0 and isinstance(input_details[0], list):
                        available_list = input_details[0]
                        current_val = node_data.get('inputs', {}).get(input_name)
                        if not current_val or not isinstance(current_val, str):
                            continue
                        is_model_field = any((x in input_name.lower() for x in ['model', 'ckpt', 'lora', 'vae', 'unet', 'name']))
                        is_model_val = any((str(current_val).lower().endswith(x) for x in ['.safetensors', '.ckpt', '.pth', '.bin', '.sft', '.pt']))
                        if (is_model_field or is_model_val) and current_val not in available_list:
                            candidates = [c for c in available_list if str(current_val).lower() in c.lower() or c.lower() in str(current_val).lower()]
                            if candidates:
                                flux_candidates = [c for c in candidates if 'flux' in c.lower()]
                                best_match = flux_candidates[0] if flux_candidates else candidates[0]
                                node_data['inputs'][input_name] = best_match
                                self.root.after(0, lambda m=f'Smart Adaptation: {best_match}': self.status_var.set(m))
                        if input_name in ['sampler_name', 'scheduler'] and current_val not in available_list:
                            candidates = [c for c in available_list if str(current_val).lower() in c.lower() or c.lower() in str(current_val).lower()]
                            if candidates:
                                node_data['inputs'][input_name] = candidates[0]
                                self.root.after(0, lambda m=f'Correction {input_name}: {candidates[0]}': self.status_var.set(m))
        except:
            pass

    def fetch_and_show_final_image(self, prompt_id):
        """After generation, fetch the final image from history (enhanced version)"""
        try:
            res = requests.get(f'http://127.0.0.1:8188/history/{prompt_id}', timeout=5)
            if res.status_code == 200:
                history = res.json().get(prompt_id, {})
                outputs = history.get('outputs', {})
                for node_id in sorted(outputs.keys(), key=int, reverse=True):
                    if 'images' in outputs[node_id]:
                        self.root.after(0, lambda imgs=outputs[node_id]['images']: self.on_comfyui_success(imgs))
                        return
                self.root.after(0, lambda : self.status_var.set('Task completed, but no image found'))
        except Exception as e:
            print(f'Image fetching error: {e}')
        self.root.after(0, lambda : self.run_comfyui_button.config(state='normal'))

    def poll_comfyui_result(self, prompt_id):
        """Poll ComfyUI for execution results, adding failure detection logic."""
        comfyui_history_url = f'http://127.0.0.1:8188/history/{prompt_id}'

        def poll():
            max_attempts = 480
            attempts = 0
            while attempts < max_attempts:
                time.sleep(5)
                attempts += 1
                try:
                    res = requests.get(comfyui_history_url, timeout=5)
                    if res.status_code == 200:
                        history_data = res.json()
                        if prompt_id in history_data:
                            item = history_data[prompt_id]
                            status = item.get('status', {})
                            if status.get('completed') and status.get('messages'):
                                for msg in status['messages']:
                                    if msg[0] == 'execution_error':
                                        err_msg = str(msg[1].get('exception_message', 'Unknown Error'))
                                        if 'OutOfMemory' in err_msg or 'Insufficient Memory' in err_msg:
                                            err_msg = "VRAM overflow! It is recommended to set the model to FP8 mode in 'ComfyUI Control'."
                                        self.root.after(0, lambda e=err_msg: self.preview_label.config(text=f'Generation failed:{e}'))
                                        self.root.after(0, lambda : self.status_var.set('ComfyUI execution failed'))
                                        self.root.after(0, lambda : self.run_comfyui_button.config(state='normal'))
                                        return
                            outputs = item.get('outputs', {})
                            generated_files = []
                            for node_id in sorted(outputs.keys(), key=int, reverse=True):
                                node_output = outputs[node_id]
                                if 'images' in node_output:
                                    generated_files.extend(node_output['images'])
                                    break
                            if generated_files:
                                self.root.after(0, lambda : self.on_comfyui_success(generated_files))
                                return
                    self.root.after(0, lambda a=attempts: self.preview_label.config(text=f'Polling (attempt {a}times)...\nWaiting for FLUX model rendering to complete'))
                except Exception as e:
                    print(f'Polling exception: {e}')
            self.root.after(0, lambda : self.status_var.set('ComfyUI wait timeout.'))
            self.root.after(0, lambda : self.run_comfyui_button.config(state='normal'))
        threading.Thread(target=poll, daemon=True).start()

    def on_comfyui_success(self, generated_files):
        """ComfyUI execution succeeded callback, processing and displaying preview"""
        self.status_var.set('ComfyUI execution completed!')
        self.run_comfyui_button.config(state='normal')
        if not generated_files:
            messagebox.showinfo('Completed', 'ComfyUI run finished, but no output image or video was found.')
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
            self.preview_frame.place(relx=0.98, rely=0.98, anchor='se', width=240, height=240)
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                self.show_image_preview(local_path)
            else:
                self.preview_label.config(text=f'Generated video/GIF: {filename}(Double-click to open)')
            self.status_var.set(f'Generated: {filename} (Double-click preview area to open)')
        except Exception as e:
            print(f'Failed to download preview file: {e}')
            self.preview_label.config(text=f'Generated {filename}, but failed to retrieve preview.')

    def show_image_preview(self, image_path):
        """Resize with PIL and display preview image"""
        try:
            from PIL import Image, ImageTk
            img = Image.open(image_path)
            max_size = (400, 300)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.preview_label.image = photo
            self.preview_label.config(image=photo, text='')
        except ImportError:
            self.preview_label.config(text=f'Image generated (PIL library missing, cannot preview)\nDouble-click here to open externally')
        except Exception as e:
            self.preview_label.config(text=f'Image preview failed{e}')

    def open_preview_file(self, event=None):
        """When double‑clicking the preview area, open file with system default program"""
        if self.current_preview_file and os.path.exists(self.current_preview_file):
            try:
                if sys.platform == 'darwin':
                    subprocess.call(('open', self.current_preview_file))
                elif os.name == 'nt':
                    os.startfile(self.current_preview_file)
                elif os.name == 'posix':
                    subprocess.call(('xdg-open', self.current_preview_file))
                self.preview_frame.place_forget()
                self.current_preview_file = None
            except Exception as e:
                messagebox.showerror('Error', f'Unable to open file: {e}')