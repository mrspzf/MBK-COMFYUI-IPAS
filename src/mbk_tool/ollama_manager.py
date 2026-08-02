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
    from .constants import MODEL_LIBRARY_URL, MODEL_PARAMS_CONFIG, OLLAMA_BASE_URL
except ImportError:
    pass
try:
    from .utils import get_model_params
except ImportError:
    pass
MODEL_LIBRARY_URL = 'https://ollama.com/library'
OLLAMA_BASE_URL = 'http://localhost:11434'
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