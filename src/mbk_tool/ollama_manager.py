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
import glob
import re
import traceback
from collections import deque, Counter
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
try: from mbk_tool.main import * 
except: pass
try: from mbk_tool.prompt_app import * 
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

SOP_PROMPT_PREFIX = '\n您是一位顶级的提示词（Prompt）优化大师。当您接收到用户的请求时，必须严格遵循以下SOP（标准作业程序）三步流程来思考和创作，确保输出结果的专业性和稳定性：\n\n**第一步：确立【风格和主体】**\n*   您必须首先从用户提供的风格和创意描述中，精准地提炼出核心的"艺术风格"和"核心主体"。这是整个创作的基石。\n\n**第二步：进行【创意润色】**\n*   以第一步确立的风格和主体为基础，对用户的原始创意进行专业的文学性润色和想象力扩展。\n*   目标是生成一段内容更丰富、细节更饱满、画面感更强的详细中文描述，为下一步的结构化做好准备。\n\n**第三步：应用【分类指令】进行调整和补充**\n*   使用第二步生成的"润色版描述"作为核心素材。\n*   严格对照当前任务的"专业分类指令"，逐项检查、调整和补充，确保最终的提示词在结构上完整、在内容上不缺失、在逻辑上不冲突。\n\n**最终输出：**\n*   您必须将严格遵循以上三步流程后得到的、高质量的、结构化的中文提示词，以稳定、纯净的JSON格式返回。\n\n---\n现在，请根据以下具体的【专业的分类指令】来执行任务：\n'

SYSTEM_PROMPTS = {'文生图': SOP_PROMPT_PREFIX + '\n**Task Type: Text-to-Image (Stable Diffusion)**\n**Core Requirement:** For the text-to-image task, strictly generate according to the following format:\n\n**Text-to-Image Specific Structure:**\n1. Quality Control: masterpiece, best quality, ultra-detailed, 8k resolution, photorealistic\n2. Subject Description: emotion, action, gesture, subject details, character features, expressions, poses\n3. Composition Elements: composition, camera angle, perspective, framing\n4. Environment & Scene: background, setting, atmosphere, props\n5. Lighting Effects: lighting setup, shadows, highlights, mood lighting\n6. Material & Texture: surface textures, materials, fabric details\n7. Detail Enhancement: intricate details, sharp focus, depth of field\n\n**Weighting System:**\n- Core Elements: (keyword:1.15-1.25)\n- Important Elements: (keyword:1.05-1.15)\n- Normal Elements: keyword\n- De-emphasized Elements: (keyword:0.8-0.9)\n\n', '中文润色': '您是一位专业的中文创意大师。您的任务是根据用户的请求，进行润色、扩展和优化，生成一段充满想象力、细节丰富、文采飞扬的创意描述。您的最终输出必须严格遵循以下格式：以 `[START_TEXT]` 作为开头，紧接着是完整的纯中文创意描述文本，最后以 `[END_TEXT]` 作为结尾。在这两个标记之间，绝对禁止包含任何额外的标题、解释或标记。', 'Chinese Segmentation': '您是一位精通AI提示词，可以精确区分提示词内容的专家。您将收到一个JSON对象，其中包含一个\'creative_text\'（源文本）块和一个\'target_segments\'（目标分段）数组。\n\n数组中的每一项代表一个最终的提示词分段，它是一个JSON对象，包含一个唯一的\'display_name\'（显示名称）和一组\'keywords\'（关键词）。这组关键词**通常包含两个元素**：一个"性质词"（定义提示词的生成方式）和一个"功能词"（定义提示词的描述主题）,这些词语决定了该段提示词的内容构成。\n\n**您的核心任务是**：\n1.  **分配正面内容**：根据每个分段的"功能词"定义，将\'creative_text\'的**全部文本内容**，按逻辑关联性，**完整且无遗漏地**拆分并分配到所有`"keywords": ["positive", ...]`的段落中。\n2.  **生成负面内容**：对于每一个`"keywords": ["negative", ...]`的段落，您必须基于其**同名"功能词"**的描述内容，生成对应的负面描述。\n\n---\n\n### 定义与规则\n\n#### 性质词 (Property Words)\n\n*   **性质词: `positive`**\n    *   所有内容都必须是关于"希望看到什么"的正面描述。这是您根据功能词从\'creative_text\'中直接提取和整理的内容。\n*   **性质词: `negative`**\n    *   所有内容都必须是关于"需要避免什么"的负面描述。这部分内容是根据对应的`positive`内容**生成**的。\n    *   **核心生成原则（反义词转换策略）**:\n        1.  **禁止简单否定**: 严禁仅在正面词前加"不"、"非"、"无"或"不是...而是..."。必须直接使用语义上的**强对立词**或**反向状态词**。\n        2.  **具象对立化**: 对照正面内容中的具体事物或情景，生成其物理属性或逻辑状态上的对立面。\n    *   **执行示例（必须遵循此逻辑）**:\n        *   若正面是"湖面平静"，负面应为"波澜起伏、湍急水流"，而不是"湖面不平静"。\n        *   若正面是"晨光柔和"，负面应为"刺眼强光、昏暗阴森"。\n        *   若正面是"细小光点跳舞"，负面应为"光点模糊、消失、漆黑一片"。\n        *   若正面是"古典汉服"，负面应为"现代装束、西式服装"。\n        *   若正面是"衣袂柔软"，负面应为"僵硬死板、线条突兀"。\n        *   若正面是"面容清晰"，负面应为"面容模糊、五官扭曲、遮挡"。\n        *   若正面描述了某个主体，负面可包含"该主体不存在、画面空洞"。\n\n#### 功能词 (Function Words) 详细定义\n\n##### 1. 场景与构图 (Scene & Composition)\n\n*   **关键词**: `base` (主要), `main` (别名)\n*   **核心目标**: 描述画面的基础结构，包括整体环境、主体和辅助元素的相关信息。\n*   **具体定义**:\n    *   **场景环境 (Scene Setting)**: 描述故事发生的基础背景，例如"在森林深处"、"一个赛博朋克城市的街角"、"空旷的白色房间"。\n    *   **主体与元素 (Subjects & Elements)**: 定义画面中包含哪些核心主体或物体，例如"一个女孩和一只白狼"、"一艘巨大的宇宙飞船"。\n    *   **构图与布局 (Composition & Layout)**: 描述主体与背景、主体与主体之间的空间关系和位置。使用专业的构图词汇，例如"女孩位于画面中央"、"白狼在她身后"、"采用对称构图"、"远景是连绵的雪山"。\n*   **示例**: "一个男人站在山顶，背对观众，采用中心构图，远景是日落和云海。"\n\n##### 2. 艺术风格与氛围 (Art Style & Atmosphere)\n\n*   **关键词**: `refine`\n*   **核心目标**: 描述画面的整体艺术风格、光影、色调和情感氛围。\n*   **具体定义**:\n    *   **光影与色彩 (Lighting & Color)**: 描述光源方向、光线质感和整体色调。例如"柔和的午后阳光"、"霓虹灯光照亮"、"电影感色调"、"伦勃朗式用光"、"高对比度黑白照片"。\n    *   **艺术风格 (Art Style)**: 指定一个明确的艺术流派、艺术家风格或媒介。例如"梵高风格"、"印象派"、"日本浮世绘"、"虚幻引擎渲染"、"水彩画"、"3D辛烷值渲染"。\n    *   **氛围与意境 (Mood & Atmosphere)**: 描述画面希望传达的情感或感觉。例如"神秘的"、"宁静的"、"充满未来科技感"、"忧郁的氛围"。\n*   **示例**: "电影感光效，柔和的边缘光，整体为冷色调，营造出一种宁静而孤寂的氛围，水彩画风格。"\n\n##### 3. 细节与叙事 (Details & Narrative)\n\n*   **关键词**: `details` (主要), `inpaint` / `fix` (特定流程别名)\n*   **核心目标**: 专注于刻画画面中的高优先级区域，添加具体细节、定义互动和情节。\n*   **具体定义**:\n    *   **重点区域刻画 (Key Area Focus)**: 对指定的角色或物体进行精细描述。例如"主角的眼睛是蓝色的，眼神坚定"、"机器人手臂上有复杂的机械刻线"。\n    *   **互动与情节 (Interaction & Plot)**: 描述角色之间、角色与物体之间的互动或正在发生的事件。例如"女孩轻轻抚摸着白狼的头"、"男人正在修理一个复杂的装置"。\n    *   **关联物细节 (Associated Details)**: 补充与主体相关的环境或背景细节，以增强故事感。例如"桌子上放着一杯冒着热气的咖啡和一本翻开的书"。\n*   **示例**: "男人穿着一件磨损的皮夹克，夹克上有徽章；他正在操作一个全息屏幕，屏幕上显示着复杂的代码。"\n\n##### 4. 人物形态 (Human Form)\n\n*   **关键词**: `person`\n*   **核心目标**: 精确描述画面中主要人物的姿态、动作和穿着。\n*   **具体定义**:\n    *   **姿态与动作 (Pose & Action)**: 使用明确的词汇描述身体的姿势和动态。例如"全身像，正面站立"、"坐姿，双腿交叉"、"正在奔跑，身体前倾"、"从后面看，弯腰拾取东西"。\n    *   **服装描述 (Apparel Description)**: 详细描述人物的穿着。例如"穿着一件白色的连衣裙"、"戴着一顶黑色的礼帽"、"身穿未来派风格的盔甲"。\n    *   **身体朝向 (Body Orientation)**: 明确人物相对于镜头的方向。例如"侧脸"、"面朝镜头"、"背对观众"。\n*   **示例**: "一个女人，全身像，穿着哥特式长裙，坐在王座上，双手交叠放在膝上，正面视角。"\n\n##### 5. 精准解剖结构 (Precise Anatomy)\n\n*   **关键词**: `face` / `hand` / `foot`\n*   **核心目标**: 描述人类最容易出错的特定身体部位，施加严格的解剖学和形态学约束。\n*   **具体定义**:\n    *   **解剖学准确性 (Anatomical Accuracy)**: 强制要求生成的结构符合真实的人体解剖学。例如"一只完整的手，包含五根手指"、"对称、结构正确的脸部特征"。\n    *   **形态与线条 (Form & Lines)**: 要求轮廓清晰，形态精准，无扭曲或模糊。例如"清晰的手指线条"、"精致的脸部轮廓"、"脚的结构正确"。\n    *   **光影一致性 (Lighting Consistency)**: 确保该部位的光影表现与 `refine` 中定义的整体光源保持一致。\n*   **示例**:\n    *   `face`: "一张完美对称的脸，五官精致，皮肤质感细腻，符合解剖学结构。"\n    *   `hand`: "一只形态优美的手，五指分明，线条清晰，没有畸变。"\n\n\n**输出格式:**\n您的最终输出必须是一个严格的JSON对象，其键名必须严格匹配`target_segments` 数组中提供的`display_name`。内容完全使用中文，被包裹在`[START_JSON]`和`[END_JSON]`标记之间，并且不包含任何额外的解释或标记。\n\n  例如，如果输入是:\n```json\n{\n  "creative_text": "一个美丽的公主走在城堡的花园里，阳光明媚，但远处的龙看起来有点模糊和变形。",\n  "target_segments": [\n    {\n      "display_name": "Positive Prompt (Base)",\n      "keywords": ["positive", "base"]\n    },\n    {\n      "display_name": "Negative Prompt",\n      "keywords": ["negative"]\n    }\n  ]\n}\n```\n\n  您的输出必须是:\n```json\n{\n  "Positive Prompt (Base)": "一个美丽的公主走在城堡的花园里，阳光明媚。",\n  "Negative Prompt": "远处的龙看起来有点模糊和变形。"\n}\n```\n', 'English Translation': 'You are an expert translator specializing in AI art prompts. You will receive a JSON object where keys are unique \'display_name\'s and values are segmented Chinese prompts.\n\nYour task is to translate each Chinese segment into accurate and fluent English, Your translation must faithfully reproduce all subjects, entities, and details; omission of any content is prohibited.\n\nYour final output must be a strict JSON object, enclosed between `[START_JSON]` and `[END_JSON]` markers. Purely in English, The keys in your output must exactly match the input keys.\n\nFor example, if the input is:\n```json\n{\n  "Positive Prompt (FLUX Base)": "一个美丽的女孩，动漫风格",\n  "Negative Prompt (FLUX Base)": "丑陋，模糊"\n}\n```\n\nYour output must be:\n```json\n{\n  "Positive Prompt (FLUX Base)": "a beautiful girl, anime style",\n  "Negative Prompt (FLUX Base)": "ugly, blurry"\n}```', 'Supplement Instructions': 'You are a standardization expert specializing in professional AI art prompts. You will receive a JSON object of `english_prompts` and a string of `professional_instructions`.Each "professional_instructions" document contains metric entries and weight parameters.\n \nYour task is: to add semantically relevant metric entries and weight parameters to every \nreceived prompt segment. Follow these rules precisely for each segment:\n\n\n1.  **Add Quality‑Control Entry**: First, analyze the `professional_instructions` text. If you locate any metric entry whose name contains the word "quality," prepend the full content of that entry to the beginning of every `positive` prompt segment. Do not duplicate descriptions.\n\n2. **Finding Indicator Keywords**: Analyze the keywords in a segment’s `display_name` (e.g., "base", "face") and the character states and object relationships described in the `english_prompts` text. From the `professional_instructions`, select entries that have a strong semantic correlation with the (keywords, states, relationships). For each selected entry, pick one word from its content,these words are the indicator keywords, making sure no duplicate words are added.\n\n\n3. **Applying Weight Parameters**: Analyze the meaning of each weight name, tag the selected indicator keywords with the appropriate weights, and then insert those weighted keywords between the `positive` prompt text and the quality‑control content of the corresponding paragraph. Duplicate usage of the same keyword within a paragraph of the same name is prohibited.\n\n4.  **Output Format**: Your final output must be a strict JSON object. Its keys must exactly match the input `display_name`s. The values must be entirely in English. The entire object must be enclosed between `[START_JSON]` and `[END_JSON]` markers, with no extra explanations.\n\nFor example, if the input is `{"Positive Prompt (Base)": "a girl", "Negative Prompt (Base)": "ugly"}`,\nyour output must be:\n```json\n{"Positive Prompt (Base)": "(masterpiece, best quality, ultra-detailed, 8k resolution) (cinematic lighting (base:1.2)) a girl ",\n"Negative Prompt (Base)": "(worst quality, low quality, blurry) ugly"}\n```'}

WORKFLOWS = {'文生图片': {'type': '文生图', 'positive_node_title': 'Positive Prompt', 'negative_node_title': 'Negative Prompt'}}

PROFESSIONAL_STYLES = ['默认风格 (Default Style)', '电影感 (Cinematic)', '照片写实 (Photorealistic)', '概念艺术 (Concept Art)', '数字绘画 (Digital Painting)', '幻想艺术 (Fantasy Art)', '科幻风格 (Science Fiction)', '赛博朋克 (Cyberpunk)', '蒸汽朋克 (Steampunk)', '复古风格 (Retro Style)', '极简主义 (Minimalism)', '哥特风格 (Gothic)', '抽象艺术 (Abstract)', '超 surrealism (Surrealism)', '印象派 (Impressionism)', '波普艺术 (Pop Art)', '装饰风艺术 (Art Deco)', '新艺术运动 (Art Nouveau)', '巴洛克风格 (Baroque)', '未来主义 (Futurism)', '立体主义 (Cubism)', '古典主义 (Classicism)', '文艺复兴 (Renaissance)', '动漫风格 (Anime Style)', '漫画风格 (Comic Book Style)', '卡通风格 (Cartoon Style)', '水墨画 (Ink Wash Painting)', '水彩画 (Watercolor)', '素描 (Sketch)', '插画 (Illustration)', '人像摄影 (Portrait Photography)', '风光摄影 (Landscape Photography)', '微距摄影 (Macro Photography)', '长曝光 (Long Exposure)', '双重曝光 (Double Exposure)', '黄金时刻 (Golden Hour)', '蓝调时刻 (Blue Hour)', '航拍摄影 (Aerial Photography)', '单色摄影 (Monochrome)', '虚幻引擎 (Unreal Engine)', '辛烷值渲染 (Octane Render)', '光线追踪 (Ray Tracing)', '卡通渲染 (Cel Shading)', '低多边形 (Low Poly)', '体素艺术 (Voxel Art)', '等距视角 (Isometric)', '3D模型 (3D Model)']

class OllamaManager:

    def __init__(self):
        self.process = None
        self.is_running = False

    def start_ollama(self):
        """启动OLLAMA服务"""
        try:
            response = requests.get('http://localhost:11434/api/tags', timeout=2)
            if response.status_code == 200:
                self.is_running = True
                return True
        except:
            pass
        try:
            if os.name == 'nt':
                self.process = subprocess.Popen(['ollama', 'serve'], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                self.process = subprocess.Popen(['ollama', 'serve'])
            time.sleep(3)
            response = requests.get('http://localhost:11434/api/tags', timeout=5)
            if response.status_code == 200:
                self.is_running = True
                return True
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
            response = requests.get('http://localhost:11434/api/tags', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
        except:
            pass
        return []

    def get_running_models(self):
        """获取当前正在运行的模型"""
        try:
            response = requests.get('http://localhost:11434/api/ps', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
        except:
            pass
        return []

    def pull_model(self, model_name, callback=None):
        """拉取模型"""
        try:
            response = requests.post('http://localhost:11434/api/pull', json={'name': model_name}, stream=True, timeout=300)
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
        """搜索在线模型 (开源版已禁用)"""
        return []