from pydantic import BaseModel, Field

from app.modules.auth.domain.entities import User


class SessionCreateIn(BaseModel):
    email: str = Field(min_length=3, max_length=200, examples=["gerencia@mederi.pe"])
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    phone: str | None
    role: str = Field(description="manager (gerencia) | salesperson (vendedor)")
    salesperson_code: str | None
    active: bool

    @classmethod
    def from_domain(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email.value,
            full_name=user.full_name,
            phone=user.phone,
            role=user.role.value,
            salesperson_code=user.salesperson_code,
            active=user.active,
        )


class SessionOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MeUpdateIn(BaseModel):
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)


class UserCreateIn(BaseModel):
    email: str = Field(max_length=200)
    full_name: str = Field(min_length=1, max_length=150)
    role: str = Field(description="manager | salesperson")
    password: str = Field(max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    salesperson_code: str | None = Field(default=None, max_length=3, description="Obligatorio para salesperson")


class UserUpdateIn(BaseModel):
    role: str | None = None
    salesperson_code: str | None = Field(default=None, max_length=3)
    active: bool | None = None


class UserPageOut(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    per_page: int
