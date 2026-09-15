from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings
from app.metrics import get_metrics_content, http_requests_total

# Database setup
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ItemDB(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)


Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic models
class ItemCreate(BaseModel):
    title: str
    description: str


class Item(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    title: str
    description: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/")
async def root() -> dict[str, str]:
    http_requests_total.labels(method="GET", endpoint="/", status=200).inc()
    return {"message": "DevOps Platform API"}


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    http_requests_total.labels(method="GET", endpoint="/healthz", status=200).inc()
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, object]:
    http_requests_total.labels(method="GET", endpoint="/readyz", status=200).inc()
    return {"status": "ready", "dependencies": {"database": "connected"}}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    http_requests_total.labels(method="GET", endpoint="/metrics", status=200).inc()
    content, _ = get_metrics_content()
    return content.decode("utf-8")


@app.post("/items", status_code=201)
async def create_item(item: ItemCreate) -> Item:
    http_requests_total.labels(method="POST", endpoint="/items", status=201).inc()
    db = SessionLocal()
    try:
        db_item = ItemDB(title=item.title, description=item.description)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return Item.model_validate(db_item)
    finally:
        db.close()


@app.get("/items")
async def list_items() -> list[Item]:
    http_requests_total.labels(method="GET", endpoint="/items", status=200).inc()
    db = SessionLocal()
    try:
        items = db.query(ItemDB).all()
        return [Item.model_validate(item) for item in items]
    finally:
        db.close()


@app.get("/items/{item_id}")
async def get_item(item_id: int) -> Item:
    db = SessionLocal()
    try:
        db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
        if not db_item:
            http_requests_total.labels(method="GET", endpoint="/items/{item_id}", status=404).inc()
            raise HTTPException(status_code=404, detail="Item not found")
        http_requests_total.labels(method="GET", endpoint="/items/{item_id}", status=200).inc()
        return Item.model_validate(db_item)
    finally:
        db.close()


@app.put("/items/{item_id}")
async def update_item(item_id: int, item: ItemCreate) -> Item:
    db = SessionLocal()
    try:
        db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
        if not db_item:
            http_requests_total.labels(method="PUT", endpoint="/items/{item_id}", status=404).inc()
            raise HTTPException(status_code=404, detail="Item not found")
        db_item.title = item.title  # type: ignore[assignment]
        db_item.description = item.description  # type: ignore[assignment]
        db.commit()
        db.refresh(db_item)
        http_requests_total.labels(method="PUT", endpoint="/items/{item_id}", status=200).inc()
        return Item.model_validate(db_item)
    finally:
        db.close()


@app.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: int) -> Response:
    db = SessionLocal()
    try:
        db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
        if not db_item:
            http_requests_total.labels(method="DELETE", endpoint="/items/{item_id}", status=404).inc()
            raise HTTPException(status_code=404, detail="Item not found")
        db.delete(db_item)
        db.commit()
        http_requests_total.labels(method="DELETE", endpoint="/items/{item_id}", status=204).inc()
        return Response(status_code=204)
    finally:
        db.close()
