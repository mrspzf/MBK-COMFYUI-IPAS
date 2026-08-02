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