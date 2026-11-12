"""按会话保存、确认和删除交通住宿安排。"""

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.tables import ArrangementsRecord
from app.models.arrangements import TravelArrangements


class ArrangementStore:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def present(
        self, conversation_id: str, arrangements: TravelArrangements, proposal_id: str
    ) -> None:
        async with AsyncSession(self.engine) as session:
            statement = insert(ArrangementsRecord).values(
                conversation_id=conversation_id,
                pending_data=arrangements.model_dump(mode="json"),
                pending_id=proposal_id,
            )
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[ArrangementsRecord.conversation_id],
                    set_={
                        "pending_data": statement.excluded.pending_data,
                        "pending_id": statement.excluded.pending_id,
                    },
                )
            )
            await session.commit()

    async def confirm(
        self, conversation_id: str, proposal_id: str | None = None
    ) -> TravelArrangements:
        async with AsyncSession(self.engine) as session:
            record = await session.get(
                ArrangementsRecord, conversation_id, with_for_update=True
            )
            if (
                record is not None
                and record.pending_data is None
                and record.data is not None
                and (proposal_id is None or record.confirmed_id == proposal_id)
            ):
                return TravelArrangements.model_validate(record.data)
            if record is None or record.pending_data is None:
                raise ValueError("没有待确认方案，请先整理交通和住宿。")
            if proposal_id is not None and record.pending_id != proposal_id:
                raise ValueError("方案已更新，请确认最新方案。")
            arrangements = TravelArrangements.model_validate(record.pending_data)
            if issues := arrangements.issues():
                raise ValueError("；".join(issues))
            record.data = record.pending_data
            record.confirmed_id = record.pending_id
            record.pending_data = None
            record.pending_id = None
            session.add(record)
            await session.commit()
            return arrangements

    async def get_state(self, conversation_id: str) -> dict:
        async with AsyncSession(self.engine) as session:
            record = await session.get(ArrangementsRecord, conversation_id)
            return {
                "arrangements": TravelArrangements.model_validate(record.data)
                if record and record.data
                else None,
                "pending_arrangements": TravelArrangements.model_validate(
                    record.pending_data
                )
                if record and record.pending_data
                else None,
                "pending_id": record.pending_id if record else None,
                "confirmed_id": record.confirmed_id if record else None,
            }

    async def get(self, conversation_id: str) -> TravelArrangements | None:
        return (await self.get_state(conversation_id))["arrangements"]

    async def delete(self, conversation_id: str) -> None:
        async with AsyncSession(self.engine) as session:
            await session.execute(
                delete(ArrangementsRecord).where(
                    ArrangementsRecord.conversation_id == conversation_id
                )
            )
            await session.commit()
