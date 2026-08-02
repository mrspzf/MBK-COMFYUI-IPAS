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
    from .constants import MODEL_PARAMS_CONFIG, NODE_FINGERPRINTS
except ImportError:
    pass
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
NODE_FINGERPRINTS = {'positive_prompt': {'classes': ['CLIPTextEncode', 'CLIPTextEncodeFlux', 'ConditioningZeroOut', 'FluxGuidance'], 'inputs': ['text', 'clip', 'conditioning'], 'weight': 1.0}, 'negative_prompt': {'classes': ['CLIPTextEncode', 'ConditioningZeroOut'], 'inputs': ['text', 'clip'], 'negative_hint': True}, 'loader': {'classes': ['CheckpointLoaderSimple', 'VAELoader', 'UNETLoader', 'DiffusionModelLoaderKJ'], 'outputs': ['MODEL', 'CLIP', 'VAE']}, 'sampler': {'classes': ['KSampler', 'KSamplerAdvanced', 'SamplerCustomAdvanced', 'BasicGuider'], 'inputs': ['model', 'positive', 'negative', 'latent_image']}, 'face_detailer': {'classes': ['FaceDetailer', 'FaceDetailerAdvanced'], 'inputs': ['image', 'model', 'clip', 'vae', 'positive', 'negative', 'bbox_detector']}}

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