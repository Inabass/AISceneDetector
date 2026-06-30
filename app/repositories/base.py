from typing import Generic, TypeVar

from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class Repository(Generic[ModelT]):
    def __init__(self, db: Session) -> None:
        self.db = db

    # Repositories never commit or rollback. Transaction boundaries belong to
    # services or UnitOfWork so multi-repository operations stay atomic.
