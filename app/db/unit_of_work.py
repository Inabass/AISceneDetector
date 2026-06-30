from types import TracebackType

from sqlalchemy.orm import Session


class UnitOfWork:
    def __init__(self, db: Session) -> None:
        self.db = db

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
