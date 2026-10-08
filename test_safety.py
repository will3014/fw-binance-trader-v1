import unittest
from decimal import Decimal
from portfolio import PortfolioPolicy, RealOrderGateway, LiveTradingDisabled, ASSETS
from engine import PaperAccount, SYMBOLS

class SafetyTests(unittest.TestCase):
    def test_all_assets_present(self):
        self.assertEqual(set(SYMBOLS), {x+'USDT' for x in ASSETS})
    def test_protected_balance(self):
        p = PortfolioPolicy()
        p.protected_minimum['GRT'] = Decimal('100')
        p.approved_assets.add('GRT')
        self.assertEqual(p.available_to_sell('GRT', Decimal('150')), Decimal('50'))
        self.assertFalse(p.validate_sell('GRT', Decimal('51'), Decimal('150')))
        self.assertTrue(p.validate_sell('GRT', Decimal('50'), Decimal('150')))
        self.assertFalse(p.validate_sell('BTC', Decimal('1'), Decimal('2')))
    def test_live_is_hard_disabled(self):
        with self.assertRaises(LiveTradingDisabled):
            RealOrderGateway().place_order('BUY', 'BTCUSDT', 1)
    def test_risk_defaults(self):
        a = PaperAccount()
        self.assertEqual(a.initial_brl, 1000)
        self.assertEqual(a.risk_per_trade_pct, .005)
        self.assertEqual(a.max_daily_loss_pct, .02)
        self.assertEqual(a.max_positions, 3)
if __name__ == '__main__': unittest.main()
