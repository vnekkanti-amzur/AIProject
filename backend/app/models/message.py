from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Message(TimestampMixin, Base):
    __tablename__ = "messages"

    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
