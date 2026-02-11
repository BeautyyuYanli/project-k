from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic_ai.messages import ModelRequest, ModelResponse
from uuid6 import uuid7


class MemoryRecord(BaseModel):
    id_: UUID = Field(default_factory=uuid7)
    parents: list[UUID] = Field(default_factory=list)
    children: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

    raw_pair: tuple[str, str]
    compacted: list[str]
    detailed: list[ModelRequest | ModelResponse]

    @property
    def short_id(self) -> str:
        return str(self.id_.hex)[:8]

    def dump_raw_pair(self) -> str:
        return self.model_dump_json(exclude=["detailed", "compacted"])
    def dump_compated(self) -> str:
        return self.model_dump_json(exclude=["detailed"])