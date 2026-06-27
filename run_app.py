import os, sys, traceback, importlib, pkgutil, time
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
def wait_exit(msg):
    print(msg)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('Error', msg)
    except:
        pass
    if sys.stdin and hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
        try: input('Press Enter to exit...')
        except: pass
    else:
        time.sleep(5)
def bootstrap():
    print('[Bootstrap] Initializing system...')
    entry_point = None
    import_error = None
    try:
        from mbk_tool import main
        entry_point = getattr(main, 'run', getattr(main, 'main', None))
    except Exception as e:
        import_error = f'{e}\n{traceback.format_exc()}'
    except BaseException as e:
        import_error = f'{e}\n{traceback.format_exc()}'
    if not entry_point:
        try:
            import mbk_tool
            for _, mod_name, _ in pkgutil.walk_packages(mbk_tool.__path__, mbk_tool.__name__ + '.'):
                try:
                    mod = importlib.import_module(mod_name)
                    entry = getattr(mod, 'run', getattr(mod, 'main', None))
                    if callable(entry): entry_point = entry; break
                except: continue
        except Exception as e:
            wait_exit(f'[Critical Error] Failed to load mbk_tool: {e}\n{traceback.format_exc()}')
            return
    if entry_point:
        print(f'[Bootstrap] Found entry point: {entry_point.__name__} in {entry_point.__module__}')
        try: entry_point()
        except Exception as e:
            wait_exit(f'Runtime Error: {e}\n{traceback.format_exc()}')
    else:
        err_msg = '[Critical Error] Could not find a valid run() or main() entry point.'
        if import_error:
            err_msg += f'\n\nFirst import attempt failed with:\n{import_error}'
        wait_exit(err_msg)
if __name__ == '__main__':
    bootstrap()
