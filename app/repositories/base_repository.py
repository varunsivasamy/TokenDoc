from collections.abc import Sequence

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from app.models.base import Base


class BaseTenantRepository[ModelType: Base]:
    """Base repository enforcing multi-tenant data isolation.

    Every select, insert, update, and delete operation is strictly scoped
    to the injected clinic_id, preventing any cross-tenant data leakage.
    """

    def __init__(self, model_class: type[ModelType], db: Session, clinic_id: str):
        self._model_class = model_class
        self._db = db
        self._clinic_id = clinic_id

    @property
    def clinic_id(self) -> str:
        """The tenant identifier enforced by this repository instance."""
        return self._clinic_id

    @property
    def db(self) -> Session:
        """The underlying database session."""
        return self._db

    def _scoped_query(self) -> Select:
        """Construct a SELECT statement pre-filtered by tenant clinic_id."""
        return select(self._model_class).where(self._model_class.clinic_id == self._clinic_id)

    def get_by_id(self, entity_id: str) -> ModelType | None:
        """Retrieve an entity by primary key within the current tenant."""
        statement = self._scoped_query().where(self._model_class.id == entity_id)
        return self._db.scalars(statement).first()

    def list_all(self, offset: int = 0, limit: int = 100) -> Sequence[ModelType]:
        """Retrieve paginated records belonging exclusively to the current tenant."""
        statement = self._scoped_query().offset(offset).limit(limit)
        return self._db.scalars(statement).all()

    def create(self, entity: ModelType) -> ModelType:
        """Persist a new entity, explicitly setting the tenant clinic_id."""
        entity.clinic_id = self._clinic_id
        self._db.add(entity)
        self._db.commit()
        self._db.refresh(entity)
        return entity

    def delete_by_id(self, entity_id: str) -> bool:
        """Delete an entity by primary key within the tenant."""
        statement = delete(self._model_class).where(
            self._model_class.id == entity_id,
            self._model_class.clinic_id == self._clinic_id,
        )
        result = self._db.execute(statement)
        self._db.commit()
        return result.rowcount > 0
