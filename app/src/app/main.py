from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from time import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings
from app.metrics import get_metrics_content, http_request_duration_seconds, http_requests_total


# Database setup
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class ItemDB(Base):
    __tablename__ = "items"
    id: Any = Column(Integer, primary_key=True, index=True)
    title: Any = Column(String, index=True)
    description: Any = Column(String)


Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
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


@app.middleware("http")
async def measure_request_duration(request: Request, call_next: Any) -> Response:
    start_time = time()
    response = await call_next(request)
    duration = time() - start_time

    method = request.method
    endpoint = request.url.path

    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

    return response


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
    db_connected = check_database_connection()
    status_code = 200 if db_connected else 503
    http_requests_total.labels(method="GET", endpoint="/readyz", status=status_code).inc()

    if not db_connected:
        raise HTTPException(status_code=503, detail="Database not available")

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
        db_item.title = item.title
        db_item.description = item.description
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
