from sqlalchemy import Column, String, Text, Integer, DateTime, PrimaryKeyConstraint, func

from stock_shared.base import Base


class StockAiContent(Base):
    __tablename__ = 'stock_ai_content'

    stock_code = Column(String(20), nullable=False)
    section = Column(String(20), nullable=False)  # 'overview' | 'theme' | 'news'
    content = Column(Text, nullable=False)
    model = Column(String(64))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        PrimaryKeyConstraint('stock_code', 'section'),
    )

    def to_dict(self):
        return {
            "stock_code": self.stock_code,
            "section": self.section,
            "content": self.content,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
