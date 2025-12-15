from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Registration, Event, User, EventStatus
from api.models.registration import RegistrationCreate, RegistrationResponse
from api.auth import validate_telegram_webapp_data
from fastapi import Header
from typing import Optional

router = APIRouter(prefix="/api/registrations", tags=["registrations"])


async def get_current_user(
    x_init_data: Optional[str] = Header(None, alias="X-Init-Data"),
    db: Session = Depends(get_db)
) -> User:
    """Получить текущего пользователя из Telegram WebApp данных"""
    if not x_init_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    
    user_data = validate_telegram_webapp_data(x_init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Неверные данные авторизации")
    
    telegram_id = user_data.get('id')
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Неверные данные пользователя")
    
    # Получаем или создаем пользователя
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=user_data.get('username'),
            full_name=f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user


@router.post("/", response_model=RegistrationResponse)
async def create_registration(
    registration: RegistrationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создать регистрацию на событие"""
    # Проверяем существование события
    event = db.query(Event).filter(Event.id == registration.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    
    if event.status not in [EventStatus.APPROVED, EventStatus.ACTIVE]:
        raise HTTPException(status_code=403, detail="Регистрация на это событие недоступна")
    
    # Проверяем, не зарегистрирован ли уже пользователь
    existing = db.query(Registration).filter(
        Registration.event_id == registration.event_id,
        Registration.user_telegram_id == user.telegram_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Вы уже зарегистрированы на это событие")
    
    # Валидируем данные регистрации
    required_fields = {f.field_name for f in event.fields if f.required}
    provided_fields = set(registration.data.keys())
    
    missing_fields = required_fields - provided_fields
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Отсутствуют обязательные поля: {', '.join(missing_fields)}"
        )
    
    # Создаем регистрацию
    new_registration = Registration(
        event_id=registration.event_id,
        user_telegram_id=user.telegram_id,
        data_json=registration.data
    )
    db.add(new_registration)
    db.commit()
    db.refresh(new_registration)
    
    return RegistrationResponse(
        id=new_registration.id,
        event_id=new_registration.event_id,
        user_telegram_id=new_registration.user_telegram_id,
        data=new_registration.data_json,
        created_at=new_registration.created_at
    )


@router.get("/my", response_model=list[RegistrationResponse])
async def get_my_registrations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить мои регистрации"""
    registrations = db.query(Registration).filter(
        Registration.user_telegram_id == user.telegram_id
    ).order_by(Registration.created_at.desc()).all()
    
    return [
        RegistrationResponse(
            id=reg.id,
            event_id=reg.event_id,
            user_telegram_id=reg.user_telegram_id,
            data=reg.data_json,
            created_at=reg.created_at
        )
        for reg in registrations
    ]

