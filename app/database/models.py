from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ASSISTANT = "assistant"
    USER = "user"


class EventStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    ACTIVE = "active"
    ARCHIVED = "archived"


class FieldType(str, enum.Enum):
    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    created_events = relationship("Event", foreign_keys="Event.created_by", back_populates="creator")
    approved_events = relationship("Event", foreign_keys="Event.approved_by", back_populates="approver")
    registrations = relationship("Registration", back_populates="user")
    event_permissions = relationship("UserEventPermission", back_populates="user")


class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    date_time = Column(DateTime, nullable=False)
    status = Column(SQLEnum(EventStatus), default=EventStatus.DRAFT, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    photo_file_id = Column(String(255), nullable=True)  # file_id фотографии в Telegram
    photo_file_ids = Column(JSON, nullable=True)  # Список file_id для нескольких фото
    max_participants = Column(Integer, nullable=True)  # Максимальное количество участников (None = без ограничений)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_events")
    approver = relationship("User", foreign_keys=[approved_by], back_populates="approved_events")
    fields = relationship("EventField", back_populates="event", cascade="all, delete-orphan", order_by="EventField.order")
    registrations = relationship("Registration", back_populates="event", cascade="all, delete-orphan")
    notifications = relationship("EventNotification", back_populates="event", cascade="all, delete-orphan")
    user_permissions = relationship("UserEventPermission", back_populates="event", cascade="all, delete-orphan")


class EventField(Base):
    __tablename__ = "event_fields"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    field_name = Column(String(255), nullable=False)
    field_type = Column(SQLEnum(FieldType), nullable=False)
    required = Column(Boolean, default=False, nullable=False)
    order = Column(Integer, default=0, nullable=False)
    options = Column(JSON, nullable=True)  # Для select полей
    
    # Relationships
    event = relationship("Event", back_populates="fields")


class Registration(Base):
    __tablename__ = "registrations"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    user_telegram_id = Column(Integer, ForeignKey("users.telegram_id"), nullable=False)
    data_json = Column(JSON, nullable=False)  # Данные заполненных полей
    confirmed = Column(Boolean, default=None, nullable=True)  # True - подтверждено, False - отказ, None - не отвечено
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    event = relationship("Event", back_populates="registrations")
    user = relationship("User", back_populates="registrations")
    scheduled_notifications = relationship("ScheduledNotification", back_populates="registration", cascade="all, delete-orphan")


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    time_before_event = Column(Integer, nullable=True)  # В минутах, может быть None для абсолютного времени
    absolute_datetime = Column(DateTime, nullable=True)  # Конкретная дата и время уведомления
    message_template = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    event_notifications = relationship("EventNotification", back_populates="template")


class EventNotification(Base):
    __tablename__ = "event_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("notification_templates.id"), nullable=True)
    custom_time = Column(Integer, nullable=True)  # В минутах, если не используется шаблон
    enabled = Column(Boolean, default=True, nullable=False)
    include_buttons = Column(Boolean, default=True, nullable=False)  # Включать кнопки подтверждения
    notification_recipients = Column(JSON, nullable=True)  # Список user_id получателей уведомлений
    
    # Relationships
    event = relationship("Event", back_populates="notifications")
    template = relationship("NotificationTemplate", back_populates="event_notifications")


class UserEventPermission(Base):
    __tablename__ = "user_event_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    can_edit = Column(Boolean, default=True, nullable=False)
    can_view_registrations = Column(Boolean, default=True, nullable=False)
    can_send_notifications = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="event_permissions")
    event = relationship("Event", back_populates="user_permissions")


class ScheduledNotification(Base):
    __tablename__ = "scheduled_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    registration_id = Column(Integer, ForeignKey("registrations.id"), nullable=False)
    notification_type = Column(String(50), nullable=False)  # 'template' или 'custom'
    scheduled_time = Column(DateTime, nullable=False)
    sent = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    registration = relationship("Registration", back_populates="scheduled_notifications")

