from sqlalchemy import (
    MetaData, Table, Column, 
    Integer, Date, BigInteger,
    Numeric, Text, String, Boolean, Enum, ForeignKey
)

metaData = MetaData()

product = Table(
    "product",
    metaData,
    Column("id", BigInteger, primary_key=True),
    Column("itemcode", String(255), nullable=False, unique=True),
    Column("brand_id", BigInteger, ForeignKey("brand.id"), nullable=False),
    Column("product_name", String(255), nullable=False),
    Column("thumbnail", Text),
    Column("gender", Enum("여성", "남성", "공용", name="gender_enum")),
    Column("material", Text),
    Column("product_detail_url", Text),
    Column("regular_price", String(255)),
    Column("current_price", String(255)),
    Column("discount_rate", Numeric(5, 2)),
    Column("reviews", Integer),
    Column("rating", Numeric(2, 1)),
    Column("stop_selling_date", Date),
    Column("details", Text),
    Column("release_date", Date),
    Column("main_color_id", BigInteger, ForeignKey("main_color.id")),
    
    # DB에 추가해야 하는 필드
    Column("is_platform", Boolean),
    Column("neckline", String(255)),
    Column("length", String(255)),
    Column("sleeve", String(255)),
    Column("fit", String(255)),
    Column("detail_category", String(255)),
    Column("liked", Integer),
    Column("sales_count", Integer),
    Column("reorder", Integer),
    
    Column("trend_index", Numeric(7, 2)),
    Column("brand_index", Numeric(7, 2)),
    Column("search", Integer), # 크롤링해서 가져오기
    Column("category_index", Numeric(7, 2)),
    
    # 백분위 필드들은 스프링에서 결과 가지고 계산
    
)

brand = Table(
    "brand",
    metaData,
    Column("id", BigInteger, primary_key=True),
    Column("brand_name", String(255), nullable=False, unique=True),
    Column("brand_type_id", Integer, ForeignKey("brand_type.id"), nullable=False),
    
)

brand_type = Table(
    "brand_type",
    metaData,
    Column("id", Integer, primary_key=True),
    Column("brand_type_name", String(255), nullable=False, unique=True), # 일단 수정해두고 테이블도 같이 수정하기 
)

# N:N 연결 테이블들

# ----- 색상 -----

color = Table(
    "color",
    metaData,
    Column("id", BigInteger, primary_key=True),
    Column("color_name", String(255), nullable=False, unique=True),
    Column("color_hex", String(7), nullable=False, unique=True),
    Column("r", Integer, nullable=False),
    Column("g", Integer, nullable=False),
    Column("b", Integer, nullable=False),
)

product_color = Table(
    "product_color",
    metaData,
    Column("product_id", BigInteger, ForeignKey("product.id"), primary_key=True),
    Column("color_id", BigInteger, ForeignKey("color.id"), primary_key=True),
)

# ----- 카테고리 -----

category = Table(
    "category",
    metaData,
    Column("id", BigInteger, primary_key=True),
    Column("category_name", String(255), nullable=False, unique=True),
    Column("category_parent_id", BigInteger)
)

product_category = Table(
    "product_category",
    metaData,
    Column("product_id", BigInteger, ForeignKey("product.id"), primary_key=True),
    Column("category_id", BigInteger, ForeignKey("category.id"), primary_key=True),
)

# ----- 패턴 -----
pattern = Table(
    "pattern",
    metaData,
    Column("id", BigInteger, primary_key=True),
    Column("pattern_name", String(50), nullable=False, unique=True),
)

product_pattern = Table(
    "product_pattern",
    metaData,
    Column("product_id", BigInteger, ForeignKey("product.id"), primary_key=True),
    Column("pattern_id", BigInteger, ForeignKey("pattern.id"), primary_key=True),
)

# ----- 디테일 -----
detail = Table(
    "detail",
    metaData,
    Column("id", BigInteger, primary_key=True),
    Column("detail_name", String(50), nullable=False, unique=True),
)

product_detail = Table(
    "product_detail",
    metaData,
    Column("product_id", BigInteger, ForeignKey("product.id"), primary_key=True),
    Column("detail_id", BigInteger, ForeignKey("detail.id"), primary_key=True),
)