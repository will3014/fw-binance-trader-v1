"""Protection policy for future holdings. No authenticated exchange calls."""
from dataclasses import dataclass, field
from decimal import Decimal

ASSETS = ('GRT', 'PEPE', 'BTC', 'ETH', 'XRP', 'SOL', 'ADA', 'DOGE')

@dataclass
class PortfolioPolicy:
    protected_minimum: dict = field(default_factory=lambda: {asset: Decimal('0') for asset in ASSETS})
    approved_assets: set = field(default_factory=set)
    live_enabled: bool = False

    def available_to_sell(self, asset: str, balance: Decimal) -> Decimal:
        if asset not in ASSETS:
            raise ValueError('Ativo não autorizado')
        return max(Decimal('0'), balance - self.protected_minimum[asset])

    def validate_sell(self, asset: str, quantity: Decimal, balance: Decimal) -> bool:
        return asset in self.approved_assets and quantity > 0 and quantity <= self.available_to_sell(asset, balance)

class LiveTradingDisabled(RuntimeError):
    pass

class RealOrderGateway:
    """Intentional hard block. Live gateway requires a separate reviewed implementation."""
    def place_order(self, *args, **kwargs):
        raise LiveTradingDisabled('ORDENS REAIS DESATIVADAS: esta versão não implementa envio de ordens')
