from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional

@dataclass(kw_only=True)
class EcrRecord:
    fantasy_pros_player_id: int
    yahoo_player_id: str
    cbs_player_id: str
    sportsradar_id: str
    player_name: str
    rank_ecr: int
    rank_min: int
    rank_max: int
    rank_avg: int
    rank_std: float
    tier: int
    positional_rank: str

    @staticmethod
    def from_dict(record_dict: dict) -> Optional[EcrRecord]:
        if record_dict is None:
            return None
        return EcrRecord(
            fantasy_pros_player_id=record_dict.get("player_id"),
            yahoo_player_id=record_dict.get("player_yahoo_id"),
            cbs_player_id=record_dict.get("cbs_player_id"),
            sportsradar_id=record_dict.get("sportsdata_id"),
            player_name=record_dict.get("player_name"),
            rank_ecr=record_dict.get("rank_ecr"),
            rank_min=record_dict.get("rank_min"),
            rank_max=record_dict.get("rank_max"),
            rank_avg=record_dict.get("rank_ave"),
            rank_std=record_dict.get("rank_std"),
            tier=record_dict.get("tier"),
            positional_rank=record_dict.get("pos_rank"),
        )

    @staticmethod
    def dict_by_id(record_dict_list: list) -> dict[str, EcrRecord]:
        records_by_id = dict()
        for record_dict in record_dict_list:
            record = EcrRecord.from_dict(record_dict=record_dict)
            records_by_id[record.sportsradar_id] = record
        return records_by_id
