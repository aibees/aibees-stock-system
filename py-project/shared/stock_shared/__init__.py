"""
stock_shared — py-naver-stock-theme / py-stock-batch 공용 패키지.

구성:
    stock_shared.base    : 공용 declarative Base
    stock_shared.models  : DB(stock) 스키마 기준 ORM 모델
    stock_shared.dao     : 두 프로젝트에서 공통으로 쓰는 DAO
    stock_shared.vo      : DAO 시그니처에 필요한 값 객체

ORM 모델은 운영 DB(stock) 스키마를 정본으로 삼아 생성되었다.
스키마가 바뀌면 모델도 DB 기준으로 갱신할 것.
"""

from stock_shared.base import Base

__all__ = ["Base"]
