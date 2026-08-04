"""
하위호환 shim.

공용 declarative Base 는 stock_shared.base 로 이전되었다.
남아 있는 py-stock-batch 전용 모델들이 shared 모델과 같은 metadata 를
공유하도록 여기서 재수출한다. 신규 코드는 stock_shared.base 를 직접 import 할 것.
"""

from stock_shared.base import Base

__all__ = ["Base"]
