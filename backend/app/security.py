import os
from datetime import datetime,timedelta,timezone
from jose import jwt
from pwdlib import PasswordHash
from fastapi import Depends,HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .db import get_db,User
SECRET=os.getenv("SECRET_KEY","development-only-change-this-secret-before-deployment")
password_hash=PasswordHash.recommended();oauth=OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
def hash_password(value:str)->str:return password_hash.hash(value)
def verify_password(value:str,hashed:str)->bool:return password_hash.verify(value,hashed)
def create_token(user_id:int)->str:return jwt.encode({"sub":str(user_id),"exp":datetime.now(timezone.utc)+timedelta(days=7)},SECRET,algorithm="HS256")
def current_user(token:str=Depends(oauth),db:Session=Depends(get_db))->User:
 try:uid=int(jwt.decode(token,SECRET,algorithms=["HS256"])["sub"])
 except Exception:raise HTTPException(401,"Invalid or expired access token")
 user=db.get(User,uid)
 if not user:raise HTTPException(401,"Account not found")
 return user
