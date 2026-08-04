"""
공용 declarative Base.

주의: 모든 shared 모델은 이 Base 하나만 상속한다.
(모델 파일마다 declarative_base() 를 새로 만들면 metadata 가 분리되어
 relationship / create_all / 단일 트랜잭션 flush 순서가 깨진다.)
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
