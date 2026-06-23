import os, sys, traceback, importlib, pkgutil
curr_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(curr_dir, 'src'))
def bootstrap():
    print('[Bootstrap] Initializing system...')
    entry_point = None
    try:
        # 1. 优先尝试标准入口 mbk_tool.main
        try:
            from mbk_tool import main
            entry_point = getattr(main, 'run', getattr(main, 'main', None))
        except ImportError: pass
        
        # 2. 如果失败，全局扫描 mbk_tool 子模块寻找入口
        if not entry_point:
            import mbk_tool
            for loader, module_name, is_pkg in pkgutil.walk_packages(mbk_tool.__path__, mbk_tool.__name__ + '.'):
                try:
                    mod = importlib.import_module(module_name)
                    entry_point = getattr(mod, 'run', getattr(mod, 'main', None))
                    if entry_point: break
                except: continue
        
        if not entry_point:
            print('\n[Critical Error] Import Failed: Could not find run() or main() in any mbk_tool modules.')
            print('Ensure your source code contains a valid entry point.')
            input('Press Enter to exit...')
            sys.exit(1)
        
        print(f'[Bootstrap] Found entry point: {entry_point.__name__} in {entry_point.__module__}')
        entry_point()
    except Exception as e:
        print(f'\n[Runtime Error] {e}')
        traceback.print_exc()
        input('Press Enter to exit...')

if __name__ == '__main__':
    bootstrap()
