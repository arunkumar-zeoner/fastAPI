from pydantic import BaseModel, Field

class UserAttributes(BaseModel):
    custom_token: str = Field(..., alias="custom:token")
    site: str

class RequestData(BaseModel):
    userAttributes: UserAttributes

class AuthorizeRequest(BaseModel):
    request: RequestData
