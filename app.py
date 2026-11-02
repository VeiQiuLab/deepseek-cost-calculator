"""Chinese Tkinter desktop front end. Runtime dependencies: Python standard library."""
import csv
import json
import sys
import tkinter as tk
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from cost_model import Config, PRESETS, PRICE_DATE, totals, detail, affordable, number

FIELDS = [
    ('价格与预算', [
        ('hit_price','缓存命中价 / 百万 Tokens（美元）'),
        ('miss_price','缓存未命中价 / 百万 Tokens（美元）'),
        ('output_price','输出价 / 百万 Tokens（美元）'),
        ('fx','汇率：1 美元 = 多少人民币'),
        ('budget','预算（人民币元）'), ('rounds','要估算的轮数（0～100000）')]),
    ('对话与上下文', [
        ('user','每轮新增用户输入 Tokens'), ('answer','每轮可见回答 Tokens（不含思考）'),
        ('thinking','每轮思考 Tokens'), ('system','每次固定提示 Tokens'),
        ('tool_tokens','每轮工具返回 Tokens（送给模型）'),
        ('window','上下文窗口 Tokens（含本轮输出）'),
        ('history_limit','最多保留的历史 Tokens（0 = 自动上限）'),
        ('cache_pct','可复用前缀的预计命中率（%）')]),
    ('工具费用', [
        ('search_calls','每轮成功 Search 次数（可填平均数）'),
        ('search_price','Search / 千次成功请求（美元）'),
        ('fetch_calls','每轮成功 Fetch 次数（可填平均数）'),
        ('fetch_price','Fetch / 千次成功请求（美元）'),
        ('third_calls','每轮第三方工具调用次数'),
        ('third_price','第三方工具 / 次（美元）'),
        ('fixed_cny','其他每轮固定费用（人民币元）')]),
]
BOOLS = [('history','携带历史：上下文随轮数增长'),
         ('retain_thinking','保留历史思考（仅适用携带 tools 等场景）'),
         ('cache_after_trim','截断后仍按命中率估算（需有可复用前缀）'),
         ('free_search_fetch','Search/Fetch 免费情景（仅适用官方豁免）')]
HEADERS = [('round','轮次'),('input_tokens','输入 Tokens'),('hit_tokens','命中 Tokens'),
           ('miss_tokens','未命中 Tokens'),('output_tokens','输出含思考 Tokens'),
           ('hit_usd','命中费 USD'),('miss_usd','未命中费 USD'),('output_usd','输出费 USD'),
           ('search_usd','Search USD'),('fetch_usd','Fetch USD'),('third_usd','第三方 USD'),
           ('fixed_cny','其他 CNY'),('cny','本轮 CNY'),('cumulative_cny','累计 CNY'),('trimmed','截断历史')]


class App:
    def __init__(self, root):
        self.root = root
        root.title('DeepSeek API 费用计算器')
        root.geometry('1220x850')
        root.minsize(900, 650)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 10))
        style.configure('Treeview', rowheight=27)
        defaults = asdict(Config()) | {'budget': '1', 'rounds': '100'}
        self.vars = {k: tk.BooleanVar(value=v) if type(v) is bool else tk.StringVar(value=str(v))
                     for k, v in defaults.items()}
        header = ttk.Frame(root, padding=(16,12))
        header.pack(fill='x')
        ttk.Label(header,text='DeepSeek 费用计算器',font=('Microsoft YaHei UI',18,'bold')).pack(side='left')
        ttk.Label(header,text='离线估算 · 无需 API Key · 不发起收费请求').pack(side='right')
        main = ttk.Panedwindow(root, orient='horizontal')
        main.pack(fill='both',expand=True,padx=12)
        left, right = ttk.Frame(main), ttk.Frame(main)
        main.add(left,weight=0)
        main.add(right,weight=1)
        self.preset = tk.StringVar(value=next(iter(PRESETS)))
        ttk.Label(left,text=f'官方价格快照 {PRICE_DATE} · 切换预设会覆盖三项模型价').pack(anchor='w',pady=5)
        combo = ttk.Combobox(left,textvariable=self.preset,values=list(PRESETS),state='readonly')
        combo.pack(fill='x',pady=(0,8))
        combo.bind('<<ComboboxSelected>>', self.use_preset)
        nb = ttk.Notebook(left)
        nb.pack(fill='both',expand=True)
        for title, items in FIELDS:
            page = ttk.Frame(nb,padding=10)
            nb.add(page,text=title)
            for key,label in items:
                ttk.Label(page,text=label).pack(anchor='w',pady=(7,2))
                ttk.Entry(page,textvariable=self.vars[key],width=41).pack(fill='x')
            if title == '对话与上下文':
                for key,label in BOOLS[:3]:
                    ttk.Checkbutton(page,text=label,variable=self.vars[key]).pack(anchor='w',pady=7)
            if title == '工具费用':
                key,label = BOOLS[-1]
                ttk.Checkbutton(page,text=label,variable=self.vars[key]).pack(anchor='w',pady=10)
                ttk.Label(page,text='工具返回的文本也会消耗模型输入 Tokens。\n有多次模型往返时，请汇总全部 usage；\n本程序用每轮一次请求作近似。',foreground='#666').pack(anchor='w')
        actions = ttk.Frame(left,padding=(0,10))
        actions.pack(fill='x')
        for label,command in [('计算 / 反推预算',self.calculate),('保存参数',self.save_config),('载入参数',self.load_config)]:
            ttk.Button(actions,text=label,command=command).pack(side='left',padx=2)
        self.summary = tk.StringVar()
        ttk.Label(right,textvariable=self.summary,font=('Microsoft YaHei UI',11),justify='left',padding=12).pack(fill='x')
        tabs = ttk.Notebook(right)
        tabs.pack(fill='both',expand=True)
        curve, table_page, notes = ttk.Frame(tabs), ttk.Frame(tabs), ttk.Frame(tabs)
        tabs.add(curve,text='累计成本曲线')
        tabs.add(table_page,text='逐轮明细')
        tabs.add(notes,text='公式与使用说明')
        self.canvas = tk.Canvas(curve,bg='#fcfdff',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw_chart())
        self.tree = ttk.Treeview(table_page,columns=[k for k,_ in HEADERS],show='headings')
        for key,label in HEADERS:
            self.tree.heading(key,text=label)
            self.tree.column(key,width=120,anchor='e')
        self.tree.grid(row=0,column=0,sticky='nsew')
        ys = ttk.Scrollbar(table_page,orient='vertical',command=self.tree.yview)
        xs = ttk.Scrollbar(table_page,orient='horizontal',command=self.tree.xview)
        ys.grid(row=0,column=1,sticky='ns'); xs.grid(row=1,column=0,sticky='ew')
        self.tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        table_page.columnconfigure(0,weight=1); table_page.rowconfigure(0,weight=1)
        ttk.Label(table_page,text='大于 500 轮时仅显示前 250 轮与后 250 轮；CSV 导出全部轮次。').grid(row=2,column=0,sticky='w')
        ttk.Button(table_page,text='导出完整 CSV（当前计算结果）',command=self.export_csv).grid(row=3,column=0,sticky='w',pady=8)
        text = tk.Text(notes,wrap='word',font=('Microsoft YaHei UI',11),padx=15,pady=15)
        text.pack(fill='both',expand=True)
        text.insert('1.0',HELP)
        text.config(state='disabled')
        ttk.Label(root,text='估算依据是 Tokens，不是汉字数。价格、汇率和命中率均可手动修改；实际以账单 usage 为准。',padding=10).pack(fill='x')
        self.result = None
        self.calculate()

    def use_preset(self, _=None):
        for key,value in zip(('hit_price','miss_price','output_price'),PRESETS[self.preset.get()]):
            self.vars[key].set(value)

    def inputs(self):
        raw = {k:v.get() for k,v in self.vars.items()}
        rounds = number(raw.pop('rounds'))
        budget = number(raw.pop('budget'))
        if rounds != int(rounds) or rounds > 100000:
            raise ValueError('估算轮数必须为 0～100000 的整数；预算反推可搜索至 10^12 轮')
        return Config(**raw),int(rounds),budget

    def calculate(self):
        try:
            c,n,budget = self.inputs()
            total = totals(c,n)
            count,capped = affordable(c,budget)
            self.result = (c,n,budget)
            model_cny = (total['hit_usd']+total['miss_usd']+total['output_usd'])*c.fx
            tools_cny = (total['search_usd']+total['fetch_usd']+total['third_usd'])*c.fx+total['fixed_cny']
            label = f'≥ {count:,} 轮（达到搜索上限）' if capped else f'{count:,} 轮'
            avg = total['cny']/n if n else Decimal(0)
            remainder = budget-totals(c,count)['cny']
            extra = '' if capped else f'；剩余 ¥{remainder:.8f}'
            self.summary.set(f'{n:,} 轮合计  ¥{total["cny"]:.8f}    /    ${total["usd"]:.8f} + ¥{total["fixed_cny"]:.8f}\n'
                             f'模型 ¥{model_cny:.8f}    工具及其他 ¥{tools_cny:.8f}    平均 ¥{avg:.8f}/轮\n'
                             f'预算 ¥{budget} 可完成：{label}{extra}\n'
                             f'输入 {total["input_tokens"]:,.0f} Tokens，其中预计命中 {total["hit_tokens"]:,.2f}')
            self.tree.delete(*self.tree.get_children())
            indices = range(1,n+1) if n <= 500 else list(range(1,251))+list(range(n-249,n+1))
            for i in indices:
                row = detail(c,i)
                self.tree.insert('', 'end',values=[self.display(row[k]) for k,_ in HEADERS])
            self.draw_chart()
        except (ValueError, ArithmeticError) as e:
            messagebox.showerror('请检查输入',str(e))

    @staticmethod
    def display(value):
        if isinstance(value,bool):
            return '是' if value else '否'
        if isinstance(value,Decimal):
            return format(value,'.8f').rstrip('0').rstrip('.') or '0'
        return value

    def draw_chart(self):
        if not self.result:
            return
        c,n,budget = self.result
        canvas = self.canvas
        canvas.delete('all')
        w,h = canvas.winfo_width(),canvas.winfo_height()
        if w < 160 or h < 160:
            return
        left,top,right,bottom = 90,40,w-30,h-55
        ymax = max(totals(c,n)['cny'],budget,Decimal('0.00000001'))*Decimal('1.1')
        def xy(i,cost):
            return left+(right-left)*i/max(n,1),bottom-float(cost/ymax)*(bottom-top)
        for j in range(6):
            value = ymax*j/5
            y = xy(0,value)[1]
            canvas.create_line(left,y,right,y,fill='#e5eaf0')
            canvas.create_text(left-8,y,text=f'{value:.6g}',anchor='e',fill='#56616d')
        canvas.create_text(left,18,text='累计费用（人民币元）',anchor='w')
        canvas.create_line(left,top,left,bottom,fill='#8190a0')
        canvas.create_line(left,bottom,right,bottom,fill='#8190a0')
        for j in range(5):
            i = n*j//4
            canvas.create_text(xy(i,0)[0],bottom+18,text=f'{i:,}')
        canvas.create_text(right,bottom+38,text='轮次',anchor='e')
        y = xy(0,budget)[1]
        canvas.create_line(left,y,right,y,fill='#d8902b',dash=(5,4))
        canvas.create_text(right,y-9,text=f'预算 ¥{budget}',anchor='e',fill='#996514')
        indices = sorted(set(n*j//min(max(n,1),600) for j in range(min(n,600)+1)))
        points = [coord for i in indices for coord in xy(i,totals(c,i)['cny'])]
        if len(points) >= 4:
            canvas.create_line(*points,fill='#2869c9',width=3)
        else:
            x,y = xy(0,0); canvas.create_oval(x-3,y-3,x+3,y+3,fill='#2869c9')

    def save_config(self):
        try:
            self.inputs()
            filename = filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('参数 JSON','*.json')])
            if filename:
                Path(filename).write_text(json.dumps({k:v.get() for k,v in self.vars.items()},ensure_ascii=False,indent=2),encoding='utf-8')
        except (ValueError,OSError) as e:
            messagebox.showerror('保存失败',str(e))

    def load_config(self):
        filename = filedialog.askopenfilename(filetypes=[('参数 JSON','*.json')])
        if not filename:
            return
        try:
            raw = json.loads(Path(filename).read_text(encoding='utf-8-sig'))
            if not isinstance(raw,dict) or set(raw) != set(self.vars):
                raise ValueError('参数文件字段不完整或包含未知字段')
            cfg = Config(**{k:v for k,v in raw.items() if k not in ('rounds','budget')})
            n,b = number(raw['rounds']),number(raw['budget'])
            if n != int(n) or n > 100000:
                raise ValueError('估算轮数必须为 0～100000 的整数')
            for k,v in (asdict(cfg)|{'rounds':str(n),'budget':str(b)}).items():
                self.vars[k].set(v if isinstance(v,bool) else str(v))
            self.preset.set('自定义 / 已载入参数')
            self.calculate()
        except (ValueError,OSError,TypeError,UnicodeError) as e:
            messagebox.showerror('载入失败',str(e))

    def export_csv(self):
        if not self.result:
            return
        filename = filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('Excel 可读 CSV','*.csv')])
        if not filename:
            return
        try:
            c,n,_ = self.result
            with open(filename,'w',newline='',encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([label for _,label in HEADERS])
                for i in range(1,n+1):
                    row = detail(c,i)
                    writer.writerow([str(row[k]) for k,_ in HEADERS])
            messagebox.showinfo('导出完成',f'已导出 {n:,} 轮完整明细。')
        except OSError as e:
            messagebox.showerror('导出失败',str(e))


HELP = '''费用是估算，不是官方账单。默认汇率 7.00 仅为示例。

一轮 = 一次用户输入 + 一次模型生成。回答 Tokens 不含思考；思考另填，按输出价计费，避免重复相加。工具多次往返的中间输出和重复输入须额外汇总；此模型不会自动推断代理内部调用。

第 i 轮历史 = min((i−1) × 增长量, 历史上限)。
增长量 = 用户输入 + 工具返回 + 可见回答 +（勾选时的思考）。
历史上限 = 窗口 − 固定提示 − 新输入 − 工具返回 − 本轮全部输出；再与手动历史上限取较小值。窗口含输出预留；只裁历史，不裁固定提示或新输入。此处按 Token 滑动截断，不模拟消息边界、摘要或真实 tokenizer。

输入 = 固定提示 + 新输入 + 工具返回 + 保留历史。
首轮冷缓存。后续可复用部分 = 固定提示 + 历史。
命中 = 可复用部分 × 命中率；未命中 = 总输入 − 命中。
截断可能改变前缀：默认截断后全部按未命中计费。只有确认仍有可复用前缀时才勾选“截断后仍按命中率估算”。命中率是情景假设，并非官方保证；可能产生小数 Tokens 的期望值。

模型美元费用 = (命中×命中价 + 未命中×未命中价 + (回答+思考)×输出价) / 1,000,000。
工具美元费用 = Search次数×单价/1,000 + Fetch次数×单价/1,000 + 第三方次数×每次价。
总人民币 = (模型美元 + 工具美元)×汇率 + 其他人民币费用。
每轮不做货币舍入，只在界面显示时保留 8 位小数。预算反推从空历史开始，找累计费用不超过预算的完整轮数；最多搜索 10^12 轮，达到上限显示“≥”，不声称无限。

价格快照：2026-10-30，美元计价。高峰为非中国法定节假日的周一至周五北京时间 09:00–12:00、14:00–18:00，其余为非高峰；手动选择统一情景，不自动混合跨时段价格。
Search/Fetch 只统计成功且有结果的请求；经 Harness/Claude Code/Codex 的服务端调用当前豁免，官方公告从北京时间 2026-11-01 00:00 开始按次收费。默认采用收费情景，需要豁免时手动勾选。

参考：
https://api-docs.deepseek.com/quick_start/pricing/
https://api-docs.deepseek.com/guides/kv_cache/
https://api-docs.deepseek.com/guides/thinking_mode/
https://api-docs.deepseek.com/guides/search/
'''


def prepare_windows_tcl():
    """Initialize Tcl's cwd before Tcl_Init on portable Windows Python.

    Some relocated Python/Tcl builds fail their first library-path lookup until
    the native cwd is initialized. No change to cwd, registry, or environment.
    Frozen PyInstaller places the DLL beside its collected files.
    """
    if sys.platform != 'win32':
        return
    import ctypes
    base = Path(getattr(sys, '_MEIPASS', sys.base_prefix))
    candidates = [base/'tcl86t.dll',base/'DLLs'/'tcl86t.dll']
    for path in candidates:
        if path.is_file():
            dll = ctypes.WinDLL(str(path))
            dll.Tcl_CreateInterp.restype = ctypes.c_void_p
            dll.Tcl_Eval.argtypes = [ctypes.c_void_p,ctypes.c_char_p]
            dll.Tcl_DeleteInterp.argtypes = [ctypes.c_void_p]
            interp = dll.Tcl_CreateInterp()
            try:
                dll.Tcl_Eval(interp,b'pwd')
            finally:
                dll.Tcl_DeleteInterp(interp)
            return


def main():
    prepare_windows_tcl()
    root = tk.Tk()
    app = App(root)
    if '--smoke-test' in sys.argv:
        # Test real Tk construction, callbacks, rendering and input state, then exit.
        root.update()
        assert app.result is not None
        assert len(app.tree.get_children()) == 100
        assert app.canvas.find_all()
        root.after(350,root.destroy)
    root.mainloop()


if __name__ == '__main__':
    main()
