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
try: from mbk_tool.ollama_manager import * 
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

class PromptApp:

    def __init__(self, root):
        self.root = root
        self.root.title('mbk-comfyui-ipb_amcsystem 开源版')
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
        self.root.after(1500, self.initial_ollama_check)
        self.root.after(3000, self._init_watermark)
        self.root.after(5000, self._ensure_watermark_integrity)
        self.root.bind('<Configure>', self._sync_wm_position)

    def initial_ollama_check(self):
        """程序启动时检查OLLAMA状态"""
        threading.Thread(target=self.refresh_ollama_status, daemon=True).start()

    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        style = ttk.Style(self.root)
        style.configure('Execute.TButton', foreground='white', background='#c00000', font=('微软雅黑', 12, 'bold'))
        style.map('Execute.TButton', background=[('active', '#e00000'), ('disabled', '#a0a0a0')], foreground=[('disabled', 'darkgrey')])
        style = ttk.Style(self.root)
        style.configure('Yellow.Horizontal.TProgressbar', background='gold')
        main_frame = ttk.Frame(self.notebook)
        self.notebook.add(main_frame, text='主控制台')
        setup_frame = ttk.Frame(self.notebook)
        self.notebook.add(setup_frame, text='OLLAMA设置')
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
        ttk.Button(workflow_frame, text='识别工作流', command=self.recognize_workflows_in_folder).grid(row=0, column=4, sticky='w', padx=10)
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
        download_frame = ttk.LabelFrame(left_frame, text='在线模型下载 (开源版不可用)', padding='10')
        download_frame.pack(fill='both', expand=True)
        search_bar_frame = ttk.Frame(download_frame)
        search_bar_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(search_bar_frame, text='搜索关键词:').pack(side='left')
        self.search_model_var = tk.StringVar()
        search_entry = ttk.Entry(search_bar_frame, textvariable=self.search_model_var, width=20, state='disabled')
        search_entry.pack(side='left', padx=5, expand=True, fill='x')
        search_button = ttk.Button(search_bar_frame, text='搜索', command=self.search_and_display_models, state='disabled')
        search_button.pack(side='left', padx=5)
        search_result_frame = ttk.Frame(download_frame)
        search_result_frame.pack(fill='both', expand=True, pady=(5, 5))
        self.online_model_listbox = tk.Listbox(search_result_frame, height=10, state='disabled')
        self.online_model_listbox.pack(side='left', fill='both', expand=True)
        online_scrollbar = ttk.Scrollbar(search_result_frame, orient='vertical', command=self.online_model_listbox.yview)
        online_scrollbar.pack(side='right', fill='y')
        self.online_model_listbox.config(yscrollcommand=online_scrollbar.set)
        self.download_progress_var = tk.StringVar(value='开源版不支持在线下载')
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
            self.status_var.set(f'已选择新路径，请点击"识别工作流"')
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
        if has_video_output:
            return '图生视频' if has_image_input else '文生视频'
        else:
            return '图生图' if has_image_input else '文生图'

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
            self.client = openai.OpenAI(api_key='dummy', base_url='http://localhost:11434/v1')
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
        self.root.after(0, lambda : self.status_var.set('正在刷新状态...'))

        def task():
            is_running = False
            running_models = []
            try:
                response = requests.get('http://localhost:11434/api/tags', timeout=2)
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
                        self.client = openai.OpenAI(api_key='dummy', base_url='http://localhost:11434/v1')
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
                list(self.client.chat.completions.create(model=model_name, messages=[{'role': 'user', 'content': 'Hi'}], max_tokens=1, stream=True))
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
        is_model_ready = len(self.running_models_cache) > 0
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
            messagebox.showwarning('警告', '请先在"OLLAMA设置"标签页中选择并加载一个AI模型')
            return
        self.conversion_progressbar.start(40)
        self.status_var.set(status_text)
        button.config(state='disabled')

        def ai_task():
            try:
                completion = self.client.chat.completions.create(messages=[{'role': 'system', 'content': SYSTEM_PROMPTS[system_prompt_key]}, {'role': 'user', 'content': json.dumps(user_content_json, ensure_ascii=False)}], model=self.selected_model_for_conversion.get(), temperature=0.7, response_format={'type': 'json_object'})
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
            match = re.search('\\[START_JSON\\](.*?)\\[END_JSON\\]', response_text, re.DOTALL)
            json_string = ''
            if match:
                json_string = match.group(1).strip()
            else:
                fallback_match = re.search('{\\s*.*\\s*}', response_text, re.DOTALL)
                try:
                    first_brace = response_text.index('{')
                    last_brace = response_text.rindex('}')
                    json_string = response_text[first_brace:last_brace + 1]
                except ValueError:
                    raise ValueError('AI响应中未找到[START_JSON]...[END_JSON]标记，也未能定位到有效的JSON对象边界。')
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
        image_path = self.image_path_var.get().strip()
        is_image_workflow = self.current_workflow_type in ['图生图', '图生视频']
        messages = []
        if is_image_workflow and image_path and os.path.exists(image_path):
            self.status_var.set('正在读取图片并准备分析...')
            try:
                with open(image_path, 'rb') as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                image_format = os.path.splitext(image_path)[1].lower().replace('.', '')
                if image_format == 'jpg':
                    image_format = 'jpeg'
                messages = [{'role': 'user', 'content': [{'type': 'text', 'text': f"你是一位顶级的图像分析专家和创意大师。请使用中文，精准、完整、并富有想象力地详细描述这张图片的所有内容，包括主体、环境、氛围、光线、构图和潜在的动态。你的描述将作为后续AI生成视频的灵感来源，因此请务必详尽。请在描述时自然地融合'{selected_style}'风格。"}, {'type': 'image_url', 'image_url': {'url': f'data:image/{image_format};base64,{base64_image}'}}]}]
                self.status_var.set('正在分析图片并生成中文创意...')
            except Exception as e:
                self.on_task_error(f'读取或处理图片时出错: {e}')
                return
        else:
            if not user_text:
                if is_image_workflow:
                    messagebox.showwarning('提示', '这是一个图片工作流，建议您先选择一张图片以获得更好的创意描述。\n\n您也可以继续手动输入文字创意。')
                    return
                else:
                    messagebox.showwarning('警告', '请输入您的中文创意。')
                    return
            content = f"请将以下描述文字('{user_text}')融合'{selected_style}'风格，进行润色、扩展和优化，使其更生动、更富有想象力、更包含细节和文采。"
            messages = [{'role': 'system', 'content': SYSTEM_PROMPTS['中文润色']}, {'role': 'user', 'content': content}]
            self.status_var.set('正在根据文本生成中文创意...')

        def callback(response_text):
            try:
                match = re.search('\\START_TEXT\\ (.*?)\\[END_TEXT\\]', response_text, re.DOTALL)
                if match:
                    self.creative_chinese_text = match.group(1).strip()
                else:
                    prefix_pattern = '^(?:THINKING|THINK|思考|分析|ANSWER|Action|输出|Result|正文)[:：].*?(\\n|\\Z)'
                    cleaned_text = re.sub(prefix_pattern, '', response_text, flags=re.MULTILINE | re.DOTALL).strip()
                    if not cleaned_text:
                        raise ValueError('AI响应中未找到[START_TEXT]...[END_TEXT]标记，且无法回退清洗。')
                    self.creative_chinese_text = cleaned_text
                    cleaned_text = cleaned_text.replace('[START_TEXT]', '').replace('[END_TEXT]', '')
                    self.creative_chinese_text = cleaned_text.strip()
                    self.creative_chinese_text = cleaned_text if cleaned_text else response_text.strip()
                self._update_ui_with_creative_chinese(self.creative_chinese_text)
                self.creative_chinese_generated = True
                self.status_var.set('1. 中文创意已生成')
            except Exception as e:
                self.on_task_error(f'处理AI响应失败: {e}')
            finally:
                self.conversion_progressbar.stop()
                self.update_button_states()
        if not self.selected_model_for_conversion.get():
            messagebox.showwarning('警告', '请先在"OLLAMA设置"标签页中选择并加载一个AI模型。\n\n(注意: 图片分析功能需要多模态模型, 如 LLaVA)')
            return
        self.conversion_progressbar.start(40)
        self.convert_cn_button.config(state='disabled')

        def ai_task():
            try:
                completion = self.client.chat.completions.create(messages=messages, model=self.selected_model_for_conversion.get(), temperature=0.7)
                self.root.after(0, callback, completion.choices[0].message.content)
            except Exception as e:
                if 'multimodal' in str(e).lower() or 'image' in str(e).lower():
                    self.root.after(0, self.on_task_error, f"""模型 '{self.selected_model_for_conversion.get()}' 可能不支持图片输入。请在"OLLAMA设置"中选择一个多模态模型（例如 LLaVA）。\n\n详细错误: {e}""")
                else:
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
        user_content = {'prompts_to_translate': prompts}

        def callback(response_text):
            self._process_ai_response(response_text, list(prompts.keys()), on_translation_success)

        def on_translation_success(result):
            self._update_ui_tabs(result)
            self.english_translated = True
            self.status_var.set('3. 英文转换完成')
            self.conversion_progressbar.stop()
            self.update_button_states()
        self._prepare_and_run_ai_task(self.convert_en_button, '正在转换为英文...', 'English Translation', user_content, callback)

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
        """阶段一：基于扩展节点知识库和图拓扑的工作流分类算法。"""
        VIDEO_OUTPUT_NODE_TYPES = {'SaveAnimatedWEBP', 'SaveAnimatedPNG', 'SaveAnimation', 'VHS_VideoCombine', 'ExportVideo', 'VideoCombine'}
        IMAGE_OUTPUT_NODE_TYPES = {'SaveImage', 'PreviewImage'}
        VIDEO_FINGERPRINT_NODE_TYPES = {'SVD_img2vid_Conditioning', 'VideoLinearCFGGuidance', 'AnimateDiffCombine'}
        VIDEO_FINGERPRINT_SUBSTRINGS = {'AnimateDiffLoader'}
        IMAGE_INPUT_NODE_TYPES = {'LoadImage', 'LoadImageMask', 'ImageLoad', 'ImpactLoadImage'}
        all_node_types = {n.get('type', '') for n in nodes}
        all_node_ids = set(nodes_map.keys())
        source_node_ids = graph_topology.get('source_node_ids', set())
        destination_node_ids = graph_topology.get('destination_node_ids', set())
        initial_node_ids = all_node_ids - destination_node_ids
        final_node_ids = all_node_ids - source_node_ids
        initial_node_types = {nodes_map[nid]['type'] for nid in initial_node_ids if nid in nodes_map}
        final_node_types = {nodes_map[nid]['type'] for nid in final_node_ids if nid in nodes_map}
        has_video_output = any((t in VIDEO_OUTPUT_NODE_TYPES for t in final_node_types))
        has_image_input = any((t in IMAGE_INPUT_NODE_TYPES for t in initial_node_types))
        has_video_fingerprint = any((t in VIDEO_FINGERPRINT_NODE_TYPES for t in all_node_types)) or any((any((sub in t for t in all_node_types)) for sub in VIDEO_FINGERPRINT_SUBSTRINGS))
        if has_video_output or has_video_fingerprint:
            return '文生图'
        has_image_output = any((t in IMAGE_OUTPUT_NODE_TYPES for t in final_node_types))
        if has_image_output:
            return '文生图'
        return '未分类'

    def _identify_injection_points(self, nodes, nodes_map, graph_topology, workflow_data):
        """阶段二：识别所有提示词注入点，并包含节点顺序号。"""
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
                widget_info = None
                if 'widgets_values' in node and isinstance(node['widgets_values'], list):
                    for (i, value) in enumerate(node['widgets_values']):
                        if isinstance(value, str):
                            widget_info = {'type': 'widgets_values', 'index': i}
                            break
                elif 'inputs' in node and any((inp.get('name') == 'text' for inp in node['inputs'])):
                    widget_info = {'type': 'inputs', 'name': 'text'}
                if not widget_info:
                    continue
                title = node.get('title', '').strip()
                is_unnamed = not title
                type_from_title = 'positive' if re.search('positive|正面', title, re.I) else 'negative' if re.search('negative|负面', title, re.I) else 'unknown'
                modifier_from_title = 'base' if re.search('base|main|主体', title, re.I) else 'inpaint' if re.search('inpaint|重绘', title, re.I) else 'refine' if re.search('refine|精炼|修复', title, re.I) else 'face' if re.search('face|面部', title, re.I) else 'hand' if re.search('hand|手部', title, re.I) else 'person' if re.search('person|身体|全身', title, re.I) else 'base'
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
                if final_type == 'unknown':
                    final_type = 'positive'
                segment = f'{final_modifier}_{final_type}'
                if is_unnamed:
                    property_str = segment
                    title = f'UNKNOWN{unnamed_node_counter}({property_str})'
                    unnamed_node_counter += 1
                node_type = node.get('type', '')
                if 'CLIPTextEncode' in node_type and (found_consumer or type_from_title != 'unknown'):
                    node_order_number = next((i for (i, n) in enumerate(nodes) if str(n.get('id')) == str(node.get('id'))), -1)
                    injection_points.append({'segment': segment, 'node_id': str(node['id']), 'node_title': title, 'node_type': node.get('type'), 'widget_info': widget_info, 'node_order_number': node_order_number})
            except Exception as e:
                print(f"分析节点 {node.get('id')} 出错: {e}")

    def execute_workflow(self):
        """执行工作流注入：将提示词结果注入到 ComfyUI 工作流 JSON 中。"""
        workflow_filename = self.specific_workflow_var.get()
        if not workflow_filename:
            messagebox.showwarning('警告', '请先选择一个具体的工作流文件。')
            return
        proj_path = self.proj_path.get()
        json_path = os.path.join(proj_path, workflow_filename)
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            prompts_to_inject = self._get_prompts_from_ui()
            image_path_to_inject = self.image_path_var.get().strip()
            analysis_data = self.workflow_analysis_cache.get(workflow_filename, {})
            summary_table = self._get_prepared_summary_table()
            if not summary_table:
                messagebox.showwarning('警告', '该工作流没有可用的注入点。')
                return
            updated_count = self._inject_data_into_workflow(workflow_data, summary_table, prompts_to_inject, image_path_to_inject)
            if updated_count > 0:
                backup_path = json_path + '.bak'
                if not os.path.exists(backup_path):
                    shutil.copy2(json_path, backup_path)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(workflow_data, f, indent=4, ensure_ascii=False)
                comfyui_base = self._find_comfyui_path()
                sync_msg = ''
                if comfyui_base:
                    target_dir = os.path.join(comfyui_base, 'user', 'default', 'workflows')
                    try:
                        if not os.path.exists(target_dir):
                            os.makedirs(target_dir, exist_ok=True)
                        target_path = os.path.join(target_dir, workflow_filename)
                        shutil.copy2(json_path, target_path)
                        sync_msg = f'\n\n已同步至 ComfyUI 目录:\n{target_path}'
                    except Exception as e:
                        sync_msg = f'\n\n同步至 ComfyUI 失败: {e}'
                else:
                    sync_msg = '\n\n提示: 未在程序前后三层目录内找到 ComfyUI 运行文件夹，未执行自动同步。'
                self.status_var.set(f'注入完成：成功更新了 {updated_count} 个节点。')
                messagebox.showinfo('成功', f'工作流已更新！\n\n成功注入了 {updated_count} 个节点。\n原文件已备份为: {os.path.basename(backup_path)}{sync_msg}')
            else:
                messagebox.showwarning('提示', '未找到匹配的节点进行注入，请检查工作流文件。')
        except Exception as e:
            self.on_task_error(f'执行工作流注入失败: {e}')

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
            except:
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

    def _inject_data_into_workflow(self, workflow_data, summary_table, prompts_to_inject, image_path_to_inject):
        """核心注入逻辑"""
        updated_count = 0
        nodes_dict = {}
        if 'nodes' in workflow_data and isinstance(workflow_data['nodes'], list):
            nodes_dict = {str(n.get('id')): n for n in workflow_data['nodes']}
        else:
            nodes_dict = {str(k): v for (k, v) in workflow_data.items() if isinstance(v, dict) and 'class_type' in v}
        for item in summary_table:
            node_id = str(item['injection_location']['node_id'])
            injection_type = item['injection_type']
            details = item['injection_location']
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
                except:
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
            self.image_label.bind('<B1-Motion>', self._do_wm_drag)
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
        except:
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
        except:
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
        self.ollama_manager.stop_ollama()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = PromptApp(root)
    root.mainloop()