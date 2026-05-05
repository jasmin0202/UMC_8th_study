from sqlalchemy import create_engine
from app.config.settings import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

# 1) 받은 csv를 기반으로 trend_index 값들을 계산하는 로직

# 2) 계산된 trend_index 값들과 product 정보를 DB에 업데이트하는 로직