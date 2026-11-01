import os
from datetime import datetime
from sqlalchemy import create_engine,String,Text,DateTime,ForeignKey,Integer,Float
from sqlalchemy.orm import DeclarativeBase,mapped_column,Mapped,sessionmaker,relationship
url=os.getenv("DATABASE_URL","sqlite:///./hardware_foundry.db").replace("postgres://","postgresql+psycopg://",1)
connect_args={"check_same_thread":False} if url.startswith("sqlite") else {}
engine=create_engine(url,pool_pre_ping=True,connect_args=connect_args)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False)
class Base(DeclarativeBase):pass
class User(Base):
 __tablename__="users"
 id:Mapped[int]=mapped_column(Integer,primary_key=True);email:Mapped[str]=mapped_column(String(320),unique=True,index=True);password_hash:Mapped[str]=mapped_column(String(255));created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
 projects:Mapped[list["Project"]]=relationship(back_populates="owner",cascade="all, delete-orphan")
class Project(Base):
 __tablename__="projects"
 id:Mapped[int]=mapped_column(Integer,primary_key=True);owner_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(180));brief:Mapped[str]=mapped_column(Text);design_json:Mapped[str]=mapped_column(Text,default="{}");created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow);updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
 owner:Mapped[User]=relationship(back_populates="projects")
Base.metadata.create_all(engine)
def get_db():
 db=SessionLocal()
 try:yield db
 finally:db.close()
