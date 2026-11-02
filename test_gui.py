"""Real Tk widgets/callbacks; only save dialogs are replaced in automated tests."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class GuiTests(unittest.TestCase):
    def setUp(self):
        app.prepare_windows_tcl()
        self.root=app.tk.Tk()
        self.gui=app.App(self.root)
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def test_real_widgets_curve_and_presets(self):
        g=self.gui
        self.assertEqual(len(g.tree.get_children()),100)
        self.assertTrue(g.canvas.find_all())
        g.preset.set('Pro · 高峰');g.use_preset();g.calculate()
        self.assertEqual(g.result[0].output_price,app.Decimal('3.96'))
        g.vars['rounds'].set('100000');g.calculate()
        self.assertEqual(len(g.tree.get_children()),500)
        self.assertEqual(g.result[1],100000)
        g.vars['rounds'].set('0');g.calculate()
        self.assertEqual(len(g.tree.get_children()),0)
        self.assertTrue(g.canvas.find_all())

    def test_parameters_and_full_csv(self):
        g=self.gui
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'中文 参数.json'
            csv_path=Path(folder)/'中文 明细.csv'
            with patch('app.filedialog.asksaveasfilename',return_value=str(config)):
                g.save_config()
            data=json.loads(config.read_text(encoding='utf-8'))
            self.assertEqual(data['rounds'],'100')
            g.vars['user'].set('999')
            with patch('app.filedialog.askopenfilename',return_value=str(config)):
                g.load_config()
            self.assertEqual(g.vars['user'].get(),'100')
            g.vars['rounds'].set('501');g.calculate()
            with patch('app.filedialog.asksaveasfilename',return_value=str(csv_path)),patch('app.messagebox.showinfo'):
                g.export_csv()
            with csv_path.open(encoding='utf-8-sig',newline='') as f:
                rows=list(csv.reader(f))
            self.assertEqual(len(rows),502)
            self.assertEqual(rows[-1][0],'501')
            self.assertEqual(app.Decimal(rows[-1][-2]),app.totals(g.result[0],501)['cny'])
            self.assertTrue(csv_path.read_bytes().startswith(b'\xef\xbb\xbf'))

    def test_invalid_data_preserves_last_result(self):
        g=self.gui
        original=g.result
        with patch('app.messagebox.showerror') as error:
            g.vars['cache_pct'].set('101');g.calculate()
            error.assert_called_once()
        self.assertEqual(g.result,original)
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'invalid-encoding.json'
            file.write_bytes(b'\xff\xfe\xff')
            with patch('app.filedialog.askopenfilename',return_value=str(file)),patch('app.messagebox.showerror') as error:
                g.load_config()
                error.assert_called_once()
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'bad.json'
            file.write_text('{"fx": 0}',encoding='utf-8')
            with patch('app.filedialog.askopenfilename',return_value=str(file)),patch('app.messagebox.showerror') as error:
                g.load_config()
                error.assert_called_once()
        self.assertEqual(g.result,original)


if __name__=='__main__':
    unittest.main(verbosity=2)
