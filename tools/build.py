"""Build in this isolated checkout; no dependency installation or system changes."""
from pathlib import Path
import os, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ.setdefault('PYTHONDONTWRITEBYTECODE','1')
os.environ.setdefault('PYINSTALLER_CONFIG_DIR',str(ROOT/'.build/pyinstaller-cache'))
def run(args, timeout=240):
 subprocess.run(args,check=True,timeout=timeout)
if sys.platform!='win32': raise SystemExit('Windows build required')
sys.path.insert(0,str(ROOT))
run([sys.executable,'-B','-m','unittest','discover','-v'])
run([sys.executable,'-B','app.py','--smoke-test'])
from tk_runtime import prepare_tk
prepare_tk()
import PyInstaller.__main__
PyInstaller.__main__.run(['--noconfirm','--clean','--onefile','--windowed','--name','DeepSeekCalculator','--distpath','dist','--workpath','.build/pyinstaller','--specpath','.build','--additional-hooks-dir','hooks','app.py'])
run([str(ROOT/'dist/DeepSeekCalculator.exe'),'--smoke-test'],timeout=45)
print('BUILD_PASS: DeepSeekCalculator.exe')
