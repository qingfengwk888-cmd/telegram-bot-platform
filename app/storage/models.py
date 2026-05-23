from sqlalchemy import String, Integer, BigInteger, Boolean, Text, DateTime, func, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_name: Mapped[str] = mapped_column(String(255), default="")
    admin_chat_id: Mapped[int] = mapped_column(BigInteger, default=0)
    creator_username: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(32), default="other")
    status: Mapped[str] = mapped_column(String(32), default="active")
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)

    started_user_count: Mapped[int] = mapped_column(Integer, default=0)
    today_started_user_count: Mapped[int] = mapped_column(Integer, default=0)

    data: Mapped[dict] = mapped_column(SQLITE_JSON, default=dict)

    created_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)


class Bot(Base):
    __tablename__ = "bots"

    bot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    bot_token: Mapped[str] = mapped_column(Text, default="")
    bot_username: Mapped[str] = mapped_column(String(255), default="")
    tenant_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="active")

    started_user_count: Mapped[int] = mapped_column(Integer, default=0)
    blacklisted_user_count: Mapped[int] = mapped_column(Integer, default=0)

    data: Mapped[dict] = mapped_column(SQLITE_JSON, default=dict)

    created_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)


class StartedUser(Base):
    __tablename__ = "started_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String(128), index=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)

    username: Mapped[str] = mapped_column(String(255), default="")
    first_name: Mapped[str] = mapped_column(String(255), default="")
    last_name: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(255), default="direct")
    bot_username: Mapped[str] = mapped_column(String(255), default="")

    data: Mapped[dict] = mapped_column(SQLITE_JSON, default=dict)

    started_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)

    __table_args__ = (
        UniqueConstraint("bot_id", "user_id", name="uq_started_user_bot_user"),
    )


class BotBlacklistUser(Base):
    __tablename__ = "bot_blacklist_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)

    __table_args__ = (
        UniqueConstraint("bot_id", "user_id", name="uq_bot_black_user"),
    )


class ApplyRecord(Base):
    __tablename__ = "apply_records"

    apply_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    tenant_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    bot_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    applicant_chat_id: Mapped[int] = mapped_column(BigInteger, default=0)

    data: Mapped[dict] = mapped_column(SQLITE_JSON, default=dict)

    created_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)


class KVStore(Base):
    __tablename__ = "kv_store"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[dict] = mapped_column(SQLITE_JSON, default=dict)
    expire_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
