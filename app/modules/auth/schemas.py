from pydantic import BaseModel


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    sales_rep_code: str | None = None

    model_config = {"from_attributes": True}
