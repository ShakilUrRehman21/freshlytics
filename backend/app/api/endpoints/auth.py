from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import PasswordChange, Token, UserCreate, UserResponse, UserUpdate

router = APIRouter()


@router.post("/register", response_model=Token, status_code=201)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    email = user_in.email.lower().strip()
    existing = await db.execute(select(User).where(func.lower(User.email) == email))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user = User(email=email, name=user_in.name.strip(), hashed_password=get_password_hash(user_in.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return Token(access_token=create_access_token(user.email), token_type="bearer",
                 user=UserResponse.model_validate(user))


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    email = form_data.username.lower().strip()
    user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.email), token_type="bearer",
                 user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(data: UserUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if data.name is not None:
        current_user.name = data.name.strip()
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/me/password", status_code=204)
async def change_password(data: PasswordChange, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    current_user.hashed_password = get_password_hash(data.new_password)
    await db.commit()
