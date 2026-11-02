"""Keep Tk detection consistent with the app's portable-Windows Tcl startup."""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import tcl_tk


def pre_find_module_path(hook_api):
    if sys.platform == 'win32':
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from app import prepare_windows_tcl
        prepare_windows_tcl()
        import tkinter
        import _tkinter
        tcl = tkinter.Tcl()
        info = dict(available=True, tkinter_extension_file=_tkinter.__file__,
                    tcl_version=_tkinter.TCL_VERSION, tk_version=_tkinter.TK_VERSION,
                    tcl_threaded=tcl.eval('info exists tcl_platform(threaded)') == '1',
                    tcl_data_dir=tcl.eval('info library'))
        tcl_tk._get_tcl_tk_info = lambda: info
    if not tcl_tk.tcltk_info.available:
        raise RuntimeError('Tcl/Tk unavailable: refusing to build an exe without tkinter')
