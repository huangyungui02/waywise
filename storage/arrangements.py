"""按会话保存、确认和删除交通住宿安排。"""

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from models.arrangements import TravelArrangements
from storage.models import ArrangementsRecord


class ArrangementsStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    def present(
        self, conversation_id: str, arrangements: TravelArrangements, proposal_id: str
    ) -> None:
        with Session(self.engine) as session:
            record = session.get(
                ArrangementsRecord, conversation_id
            ) or ArrangementsRecord(conversation_id=conversation_id)
            record.pending_data = arrangements.model_dump_json()
            record.pending_id = proposal_id
            session.add(record)
            session.commit()

    def confirm(
        self, conversation_id: str, proposal_id: str | None = None
    ) -> TravelArrangements:
        with Session(self.engine) as session:
            record = session.get(ArrangementsRecord, conversation_id)
            if record is None or record.pending_data is None:
                raise ValueError("没有待确认方案，请先整理交通和住宿。")
            if proposal_id is not None and record.pending_id != proposal_id:
                raise ValueError("方案已更新，请确认最新方案。")
            arrangements = TravelArrangements.model_validate_json(record.pending_data)
            if issues := arrangements.issues():
                raise ValueError("；".join(issues))
            record.data = record.pending_data
            record.confirmed_id = record.pending_id
            record.pending_data = None
            record.pending_id = None
            session.add(record)
            session.commit()
            return arrangements

    def get_state(self, conversation_id: str) -> dict:
        with Session(self.engine) as session:
            record = session.get(ArrangementsRecord, conversation_id)
            return {
                "arrangements": TravelArrangements.model_validate_json(record.data)
                if record and record.data
                else None,
                "pending_arrangements": TravelArrangements.model_validate_json(
                    record.pending_data
                )
                if record and record.pending_data
                else None,
                "pending_id": record.pending_id if record else None,
                "confirmed_id": record.confirmed_id if record else None,
            }

    def get(self, conversation_id: str) -> TravelArrangements | None:
        return self.get_state(conversation_id)["arrangements"]

    def delete(self, conversation_id: str) -> None:
        with Session(self.engine) as session:
            record = session.get(ArrangementsRecord, conversation_id)
            if record is not None:
                session.delete(record)
                session.commit()
