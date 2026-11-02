import random
import unittest
from dataclasses import replace
from decimal import Decimal as D

from cost_model import Config, PRESETS, totals, detail, affordable, number, MAX_ROUNDS


def reference(c, n):
    """Independent iterative oracle; no production helpers/formula for history sum."""
    history = 0
    total = D(0)
    for i in range(n):
        output = c.answer+c.thinking
        base = c.system+c.user+c.tool_tokens
        cap = c.window-output-base
        if c.history_limit:
            cap = min(cap,c.history_limit)
        trimmed = history > cap
        retained = min(history,cap)
        hit = D(0)
        if i and (not trimmed or c.cache_after_trim):
            hit = D(c.system+retained)*c.cache_pct/100
        miss = D(base+retained)-hit
        usd = (hit*c.hit_price+miss*c.miss_price+D(output)*c.output_price)/1_000_000
        if not c.free_search_fetch:
            usd += (c.search_calls*c.search_price+c.fetch_calls*c.fetch_price)/1000
        usd += c.third_calls*c.third_price
        total += usd*c.fx+c.fixed_cny
        if c.history:
            history += c.user+c.tool_tokens+c.answer+(c.thinking if c.retain_thinking else 0)
    return total


class CostTests(unittest.TestCase):
    def test_hand_calculated_first_round(self):
        c=Config(user=100,system=200,answer=300,thinking=50,fx=D(7))
        r=detail(c,1)
        self.assertEqual(r['hit_tokens'],0)
        self.assertEqual(r['miss_tokens'],300)
        self.assertEqual(r['output_tokens'],350)
        self.assertEqual(r['cny'],D('0.001785'))

    def test_context_and_cache(self):
        c=Config(user=100,system=200,answer=300,cache_pct=100)
        self.assertEqual(detail(c,2)['input_tokens'],700)
        self.assertEqual(detail(c,2)['hit_tokens'],600)
        self.assertEqual(detail(c,2)['miss_tokens'],100)
        self.assertEqual(detail(c,1)['hit_tokens'],0)

    def test_truncation_boundary(self):
        c=Config(user=10,system=20,answer=30,window=100,cache_pct=100)
        self.assertFalse(detail(c,2)['trimmed'])
        self.assertEqual(detail(c,2)['hit_tokens'],60)
        self.assertTrue(detail(c,3)['trimmed'])
        self.assertEqual(detail(c,3)['input_tokens'],70)
        self.assertEqual(detail(c,3)['hit_tokens'],0)
        self.assertEqual(detail(replace(c,cache_after_trim=True),3)['hit_tokens'],60)

    def test_no_history_and_zero_cap(self):
        c=Config(history=False,cache_pct=100)
        self.assertEqual(detail(c,9)['input_tokens'],300)
        self.assertEqual(detail(c,9)['hit_tokens'],200)
        c=Config(user=10,system=20,answer=30,window=60)
        self.assertEqual(detail(c,2)['input_tokens'],30)
        self.assertTrue(detail(c,2)['trimmed'])

    def test_thinking_history(self):
        c=Config(thinking=100)
        self.assertEqual(detail(c,2)['input_tokens'],700)
        self.assertEqual(detail(replace(c,retain_thinking=True),2)['input_tokens'],800)

    def test_tools_units_currency(self):
        c=Config(user=0,answer=0,system=0,fx=7,search_calls=2,fetch_calls=3,
                 third_calls=D('0.5'),third_price=D('0.02'),fixed_cny=D('0.1'))
        self.assertEqual(totals(c,1)['cny'],D('0.19625'))
        self.assertEqual(totals(replace(c,free_search_fetch=True),1)['cny'],D('0.17'))

    def test_budget_exact_and_next_round(self):
        for c in [Config(),Config(window=1500),Config(history=False),Config(fixed_cny=1)]:
            for n in [0,1,2,20,1000]:
                budget=totals(c,n)['cny']
                count,capped=affordable(c,budget)
                self.assertEqual((count,capped),(n,False))
                self.assertLessEqual(totals(c,count)['cny'],budget)
                self.assertGreater(totals(c,count+1)['cny'],budget)

    def test_free_and_limits(self):
        c=Config(user=0,answer=0,system=0)
        self.assertEqual(affordable(c,0),(MAX_ROUNDS,True))
        self.assertEqual(affordable(Config(),0),(0,False))
        self.assertEqual(affordable(Config(),1,limit=0),(0,True))
        self.assertEqual(totals(Config(),0)['cny'],0)

    def test_invalid_inputs(self):
        for kwargs in [dict(cache_pct=101),dict(fx=0),dict(user=-1),dict(user='1.2'),
                       dict(window=0),dict(window=200),dict(hit_price='NaN'),
                       dict(third_price='Infinity'),dict(history='false'),dict(fixed_cny=-1)]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                Config(**kwargs)
        for value in ['NaN','-Infinity','-1','abc','1e19']:
            with self.assertRaises(ValueError): number(value)
        for n in [-1,1.5,True,MAX_ROUNDS+1]:
            with self.assertRaises(ValueError):totals(Config(),n)

    def test_presets(self):
        self.assertEqual(len(PRESETS),4)
        for name,prices in PRESETS.items():
            self.assertGreater(totals(Config(hit_price=prices[0],miss_price=prices[1],output_price=prices[2]),1)['cny'],0)

    def test_random_iterative_oracle(self):
        rng=random.Random(20261030)
        for _ in range(300):
            u,a,t,s,x=[rng.randrange(80) for _ in range(5)]
            c=Config(user=u,answer=a,thinking=t,system=s,tool_tokens=x,
                window=u+a+t+s+x+rng.randrange(300),history_limit=rng.choice([0,20,100]),
                history=rng.choice([False,True]),retain_thinking=rng.choice([False,True]),
                cache_after_trim=rng.choice([False,True]),cache_pct=rng.choice([0,33,50,100]),
                free_search_fetch=rng.choice([False,True]),search_calls=D('0.5'),fetch_calls=2,
                third_calls=2,third_price=D('0.001'),fixed_cny=D('0.00001'))
            n=rng.randrange(100)
            self.assertEqual(totals(c,n)['cny'],reference(c,n))
            self.assertEqual(sum((detail(c,i)['cny'] for i in range(1,n+1)),D(0)),totals(c,n)['cny'])
            if n:
                row=detail(c,n)
                self.assertEqual(row['hit_tokens']+row['miss_tokens'],row['input_tokens'])
                self.assertLessEqual(row['input_tokens']+row['output_tokens'],c.window)


if __name__=='__main__':
    unittest.main(verbosity=2)
