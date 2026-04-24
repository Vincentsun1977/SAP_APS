"""PostgreSQL database connection and operations via SQLAlchemy."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from loguru import logger
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings


Base = declarative_base()


class SerializerMixin:
    """Utility mixin that serializes SQLAlchemy models to dicts."""

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for column in self.__table__.columns:  # type: ignore[attr-defined]
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        return result


class RawOrder(Base, SerializerMixin):
    __tablename__ = "raw_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), index=True, nullable=True)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FeatureRecord(Base, SerializerMixin):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), index=True, nullable=True)
    feature_version = Column(String(32), nullable=True)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PredictionRecord(Base, SerializerMixin):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), index=True, nullable=True)
    prediction_class = Column(Integer, nullable=True)
    prediction_proba = Column(Float, nullable=True)
    model_version = Column(String(64), nullable=True)
    payload = Column(JSONB, nullable=False)
    predicted_at = Column(DateTime(timezone=True), server_default=func.now())
    actual_result = Column(Integer, nullable=True)
    is_correct = Column(Boolean, nullable=True)


class ModelMetadata(Base, SerializerMixin):
    __tablename__ = "model_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_version = Column(String(64), unique=True, nullable=False)
    algorithm = Column(String(64), nullable=False)
    data_source = Column(String(128), nullable=True)
    training_date = Column(DateTime(timezone=True), nullable=False)
    train_samples = Column(Integer, nullable=True)
    val_samples = Column(Integer, nullable=True)
    total_samples = Column(Integer, nullable=True)
    num_features = Column(Integer, nullable=True)
    test_accuracy = Column(Float, nullable=True)
    precision_score = Column(Float, nullable=True)
    recall_score = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    roc_auc = Column(Float, nullable=True)
    delay_rate = Column(Float, nullable=True)
    date_range_start = Column(DateTime(timezone=True), nullable=True)
    date_range_end = Column(DateTime(timezone=True), nullable=True)
    feature_importance = Column(JSONB, nullable=True)
    hyperparameters = Column(JSONB, nullable=True)
    model_path = Column(String(512), nullable=False)
    is_active = Column(Boolean, default=True)
    extra_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DatabaseClient:
    """PostgreSQL database client wrapper."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.engine = self._create_engine()
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    def _create_engine(self):
        url = URL.create(
            "postgresql+psycopg2",
            username=self.settings.postgres_user,
            password=self.settings.postgres_password,
            host=self.settings.postgres_host,
            port=self.settings.postgres_port,
            database=self.settings.postgres_db,
        )

        connect_args = {}
        ssl_mode = (self.settings.postgres_ssl_mode or "disable").lower()
        if ssl_mode != "disable":
            connect_args["sslmode"] = ssl_mode

        try:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=self.settings.db_pool_size,
                max_overflow=self.settings.db_max_overflow,
                connect_args=connect_args,
                future=True,
            )
            logger.info(
                "Connected to PostgreSQL {host}:{port}/{db}",
                host=self.settings.postgres_host,
                port=self.settings.postgres_port,
                db=self.settings.postgres_db,
            )
            return engine
        except SQLAlchemyError as exc:
            logger.error("Failed to initialize PostgreSQL engine: {error}", error=exc)
            raise

    @contextmanager
    def session_scope(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def insert_orders(self, orders: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        records: List[RawOrder] = []
        with self.session_scope() as session:
            for order in orders:
                order_id = order.get("order_id") or order.get("Order") or order.get("order")
                records.append(RawOrder(order_id=order_id, payload=order))
            session.add_all(records)
        return [record.to_dict() for record in records]

    def get_orders(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            stmt = select(RawOrder).offset(offset).limit(limit)
            results = session.execute(stmt).scalars().all()
            return [row.to_dict() for row in results]

    def insert_features(self, features: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        records: List[FeatureRecord] = []
        with self.session_scope() as session:
            for feature in features:
                order_id = feature.get("order_id") or feature.get("Order")
                feature_version = feature.get("feature_version")
                records.append(
                    FeatureRecord(order_id=order_id, feature_version=feature_version, payload=feature)
                )
            session.add_all(records)
        return [record.to_dict() for record in records]

    def insert_predictions(self, predictions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        records: List[PredictionRecord] = []
        with self.session_scope() as session:
            for pred in predictions:
                records.append(
                    PredictionRecord(
                        order_id=pred.get("order_id") or pred.get("Order"),
                        prediction_class=pred.get("prediction_class"),
                        prediction_proba=pred.get("prediction_proba"),
                        model_version=pred.get("model_version"),
                        payload=pred,
                        actual_result=pred.get("actual_result"),
                        is_correct=pred.get("is_correct"),
                    )
                )
            session.add_all(records)
        return [record.to_dict() for record in records]

    def get_latest_model(self) -> Optional[Dict[str, Any]]:
        with self.session_scope() as session:
            stmt = (
                select(ModelMetadata)
                .where(ModelMetadata.is_active.is_(True))
                .order_by(ModelMetadata.training_date.desc())
                .limit(1)
            )
            record = session.execute(stmt).scalar_one_or_none()
            return record.to_dict() if record else None

    def save_model_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        handled_keys = {
            "model_version",
            "algorithm",
            "data_source",
            "training_date",
            "train_samples",
            "val_samples",
            "total_samples",
            "num_features",
            "test_accuracy",
            "precision_score",
            "recall_score",
            "f1_score",
            "roc_auc",
            "delay_rate",
            "date_range_start",
            "date_range_end",
            "feature_importance",
            "hyperparameters",
            "model_path",
            "is_active",
        }

        extra = {k: v for k, v in metadata.items() if k not in handled_keys}

        record = ModelMetadata(
            model_version=metadata["model_version"],
            algorithm=metadata.get("algorithm", "unknown"),
            data_source=metadata.get("data_source"),
            training_date=self._parse_datetime(metadata.get("training_date")),
            train_samples=metadata.get("train_samples"),
            val_samples=metadata.get("val_samples"),
            total_samples=metadata.get("total_samples"),
            num_features=metadata.get("num_features"),
            test_accuracy=metadata.get("test_accuracy"),
            precision_score=metadata.get("precision_score"),
            recall_score=metadata.get("recall_score"),
            f1_score=metadata.get("f1_score"),
            roc_auc=metadata.get("roc_auc"),
            delay_rate=metadata.get("delay_rate"),
            date_range_start=self._parse_datetime(metadata.get("date_range_start")),
            date_range_end=self._parse_datetime(metadata.get("date_range_end")),
            feature_importance=metadata.get("feature_importance"),
            hyperparameters=metadata.get("hyperparameters"),
            model_path=metadata.get("model_path"),
            is_active=metadata.get("is_active", True),
            extra_metadata=extra or None,
        )

        with self.session_scope() as session:
            session.add(record)
            session.flush()
            session.refresh(record)
            return record.to_dict()

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                return None


# Global instance
db = DatabaseClient()
