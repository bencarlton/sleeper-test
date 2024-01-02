from AdpRecord import AdpRecord
from datetime import datetime
from datetime import timedelta
from EcrRecord import EcrRecord
from sleeper.api import DraftAPIClient
from sleeper.api import LeagueAPIClient
from sleeper.api import PlayerAPIClient
from sleeper.enum import (
    Sport,
    TransactionStatus,
    TransactionType
)
from sleeper.model import (
    Draft,
    League,
    Player,
    PlayerDraftPick,
    Transaction,
    User
)
import csv
import json
import math
import os
import pickle
import re
import requests

PLAYER_CACHE_MAX_AGE = timedelta(hours=24)
RANK_CACHE_MAX_AGE = timedelta(hours=12)

def build_user_map(league_id: str) -> dict[str, User]:
    user_map = {}
    league_users: list[User] = LeagueAPIClient.get_users_in_league(league_id=league_id)
    for user in league_users:
        user_map[user.user_id] = user
    return user_map

def build_keeper_exclusion_list(league_id: str) -> dict[str, dict]:
    keeper_exclusion_list = {}
    for week in range(1, 20):
        transactions: list[Transaction] = LeagueAPIClient.get_transactions(league_id=league_id, week=week)
        for transaction in transactions:
            if transaction.status == TransactionStatus.COMPLETE:
                if transaction.drops:
                    for key in transaction.drops:
                        if key not in keeper_exclusion_list.keys():
                            keeper_exclusion_list[key] = {
                                'week': transaction.leg,
                                'transaction_type': 'Traded' if transaction.type is TransactionType.TRADE else 'Dropped'
                            }
    return keeper_exclusion_list

def get_cached_data(cache_file_path: str, max_age: timedelta = timedelta(hours=24)) -> dict:
    if os.path.exists(cache_file_path) and datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file_path)) < max_age:
        with open(cache_file_path, 'rb') as f:
            return pickle.load(f)
    return None

def get_players(sport: Sport=Sport.NFL) -> dict[str, Player]:
    cache_file_name = f'{sport.name.lower()}_player_cache.pkl'
    if os.path.exists(cache_file_name) and datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file_name)) < PLAYER_CACHE_MAX_AGE:
        with open(cache_file_name, 'rb') as f:
            players: dict[str, Player] = pickle.load(f)
    else:
        players = PlayerAPIClient.get_all_players(sport=sport)
        with open(cache_file_name, 'wb') as f:
            pickle.dump(players, f)
    return players

def update_rankings_cache() -> None:
    response = requests.get('https://www.fantasypros.com/nfl/rankings/ppr-cheatsheets.php')
    ecr_match = re.search(r'var ecrData = ({.*?});', response.text)
    ecr_json: dict = json.loads(ecr_match.group(1))
    with open('nfl_ecr_ranking_cache.pkl', 'wb') as f:
        pickle.dump(ecr_json.get('players', None), f)
    adp_match = re.search(r'var adpData = (\[.*?\]);', response.text)
    adp_json = json.loads(adp_match.group(1))
    with open('nfl_adp_ranking_cache.pkl', 'wb') as f:
        pickle.dump(adp_json, f)

def get_player_ecr_rankings() -> dict[str, EcrRecord]:
    cache_file_name = 'nfl_ecr_ranking_cache.pkl'
    cached_data: list = get_cached_data(cache_file_path=cache_file_name, max_age=RANK_CACHE_MAX_AGE)
    if cached_data is None:
        update_rankings_cache()
        cached_data = get_cached_data(cache_file_path=cache_file_name, max_age=RANK_CACHE_MAX_AGE)
    return EcrRecord.dict_by_id(cached_data)

def get_player_adp_rankings() -> dict[str, AdpRecord]:
    cache_file_name = 'nfl_adp_ranking_cache.pkl'
    cached_data: list = get_cached_data(cache_file_path=cache_file_name, max_age=RANK_CACHE_MAX_AGE)
    if cached_data is None:
        update_rankings_cache()
        cached_data = get_cached_data(cache_file_path=cache_file_name, max_age=RANK_CACHE_MAX_AGE)
    return AdpRecord.dict_by_id(cached_data)

def build_sportradar_player_map() -> dict[str, Player]:
    sportradar_player_map: dict[str, Player] = {}
    player_map: dict[str, Player] = get_players(Sport.NFL)
    for key in player_map:
        sportradar_player_map[player_map[key].sportradar_id] = player_map[key]
    return sportradar_player_map

if __name__ == "__main__":
    league: League = LeagueAPIClient.get_league(league_id=os.environ.get('LEAGUE_ID'))
    previous_league: League = LeagueAPIClient.get_league(league_id=league.previous_league_id)
    keeper_exclusion_list: dict[str, dict] = build_keeper_exclusion_list(league_id=previous_league.league_id)
    users: dict[str, User] = build_user_map(league_id=previous_league.league_id)
    league_draft: Draft = DraftAPIClient.get_drafts_in_league(league_id=previous_league.league_id)[0]
    draft_picks: list[PlayerDraftPick] = DraftAPIClient.get_player_draft_picks(draft_id=league_draft.draft_id, sport=Sport.NFL)
    players: dict[str, Player] = get_players(sport=Sport.NFL)
    yahoo_player_map: dict[str, Player] = build_sportradar_player_map()
    ecr_rankings = get_player_ecr_rankings()
    adp_rankings = get_player_adp_rankings()
    fields = [
        'Pick',
        'Draft Round',
        'Keeper Round',
        'Player',
        'Position',
        'Team',
        'Active',
        'Manager',
        'Eligible',
        'Reason for Ineligibility',
        'ECR Rank',
        'ECR Round',
        'ECR Round Differential',
        'ADP Rank',
        'ADP Round',
        'ADP Round Differential']
    filename = 'MWLSE 2023 Keeper Eligibility.csv'
    potential_keepers = []
    with open(filename, 'w') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(fields)
        for pick in draft_picks:
            player = players[pick.player_id]
            user = users[pick.picked_by]
            keeper_eligible = True
            ineligibility_reason = None
            keeper_round: int = pick.round - 5
            ecr_rank: int = None
            ecr_round_projection: int = None
            adp_rank: int = None
            adp_round_projection: int = None
            ecr_round_differential: int = None
            adp_round_differential: int = None
            if keeper_round < 1:
                keeper_eligible = False
                ineligibility_reason = 'Pre-6th Round'
            elif pick.player_id in keeper_exclusion_list.keys():
                keeper_eligible = False
                ineligibility_reason = f"{keeper_exclusion_list[pick.player_id]['transaction_type']} - Week {keeper_exclusion_list[pick.player_id]['week']}"
            yahoo_id = player.sportradar_id
            if yahoo_id in ecr_rankings:
                ecr_rank: int = ecr_rankings[yahoo_id].rank_ecr
                ecr_round_projection: int = math.ceil(ecr_rank / 10.0)
                ecr_round_differential = keeper_round - ecr_round_projection if keeper_round > 0 else None
            if yahoo_id in adp_rankings:
                adp_rank: int = adp_rankings[yahoo_id].rank_ecr
                adp_round_projection: int = math.ceil(adp_rank / 10.0)
                adp_round_differential = keeper_round - adp_round_projection if keeper_round > 0 else None
            writer.writerow([
                pick.pick_no,
                pick.round,
                keeper_round if keeper_round > 0 else None,
                f'{player.first_name} {player.last_name}',
                player.position.name,
                player.team.name,
                player.active,
                user.display_name,
                keeper_eligible,
                ineligibility_reason,
                ecr_rank,
                ecr_round_projection,
                ecr_round_differential,
                adp_rank,
                adp_round_projection,
                adp_round_differential])
