import pandas as pd

print("Loading data...")

matches = pd.read_csv("results.csv")
rankings = pd.read_csv("fifa_ranking-2026-04-01_c.csv", encoding="latin1")

# Convert date columns to datetime type

matches['date'] = pd.to_datetime(matches['date'])
rankings['rank_date'] = pd.to_datetime(rankings['rank_date'])

# Verify that the data has been loaded correctly

print(f' Matches loaded: {len(matches):,}')
print(f' Rankings loaded: {len(rankings):,}')

KEEP_TOURNAMENTS = [
    'FIFA World Cup',
    'FIFA World Cup qualification',
    'Confederations Cup',
    'Copa América',
    'CONCACAF Nations League',
    'CONCACAF Nations League qualification',
    'UEFA Euro',
    'African Cup of Nations',
    'UEFA Euro qualification',
    'African Cup of Nations qualification',
    'AFC Asian Cup',
    'AFC Asian Cup qualification',
    'UEFA Nations League',
    'CECAFA Cup',
    'Gulf Cup',
    'Arab Cup',
    'Gold Cup',
    'Oceania Nations Cup',
    'CAFA Nations Cup',
]

# Filter matches to include only those from the specified tournaments, avoiding data noise

matches_filtered = matches[matches['tournament'].isin(KEEP_TOURNAMENTS)].copy()

print(f' Matches after filtering: {len(matches_filtered):,}')
print(f' Dates range from {matches_filtered["date"].min().date()} to {matches_filtered["date"].max().date()}')


rankings_matches = rankings[['rank_date',"country_full", 'rank', 'total_points']].copy()

matches_filtered = matches_filtered.sort_values('date')

# Merge the matches with the rankings to get the home team rankings at the time of each match

rankings_matches = rankings_matches.dropna(subset=["rank_date"])
home_rankings = pd.merge_asof(matches_filtered[['date','home_team', 'away_team', 'home_score', 'away_score', 'tournament', 'neutral']],
                              rankings_matches.rename(columns={
                                                               'country_full': 'home_team',
                                                               'rank': 'home_rank',
                                                               'total_points': 'home_points'
                                                              }),
                                                              left_on='date',
                                                              right_on='rank_date',
                                                              by='home_team',
                                                              direction='backward')

# Merge the matches with the rankings to get the away team rankings at the time of each match

full_data = pd.merge_asof(home_rankings.sort_values('date'),
                          rankings_matches.rename(columns ={ 
                                                            'country_full': 'away_team',
                                                            'rank': 'away_rank',
                                                            'total_points': 'away_points'
                                                          }),
                                                          left_on='date',
                                                          right_on='rank_date',
                                                          by='away_team',
                                                          direction='backward')

HOSTS_2026 = ['United States', 'Mexico', 'Canada']

def get_host_advantage(row):
    if row['tournament'] == 'FIFA World Cup':
     if row['home_team'] in HOSTS_2026:
        return 1
     elif row['away_team'] in HOSTS_2026:
        return -1
    return 0

full_data['host_advantage'] = full_data.apply(get_host_advantage, axis=1)

print(f' Final dataset size: {len(full_data):,}')
print(f' Rows where rankings were found for both teams: {(full_data[["home_rank", "away_rank"]].notna()).all(axis=1).sum():,}')

def get_result(row):
    if row['home_score'] > row['away_score']:
        return 'H'
    elif row['home_score'] < row['away_score']:
        return 'A'
    else:
        return 'D'
full_data['result'] = full_data.apply(get_result, axis=1)

print("Results distribution:")
print(full_data['result'].value_counts())

print("\nCalculating rolling form ...")

def get_team_points(row, team_col):
    if team_col == "home_team":
        if row["result"] == "H": return 3
        if row["result"] == "D": return 1
        return 0
    else:  # away_team
        if row["result"] == "A": return 3
        if row["result"] == "D": return 1
        return 0

home_games = full_data[["date", "home_team", "result"]].copy()
home_games["team"] = home_games["home_team"]
home_games["points"] = home_games.apply(lambda r: get_team_points(r, "home_team"), axis=1)
 
away_games = full_data[["date", "away_team", "result"]].copy()
away_games["team"] = away_games["away_team"]
away_games["points"] = away_games.apply(lambda r: get_team_points(r, "away_team"), axis=1)
 
all_games = pd.concat([
    home_games[["date", "team", "points"]],
    away_games[["date", "team", "points"]]
]).sort_values("date").reset_index(drop=True)

all_games["form"] = all_games.groupby("team")["points"].transform(
    lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
)

form_lookup = all_games.set_index(["date", "team"])["form"].to_dict()

full_data["home_form"] = full_data.apply(
    lambda r: form_lookup.get((r["date"], r["home_team"])), axis=1
)
full_data["away_form"] = full_data.apply(
    lambda r: form_lookup.get((r["date"], r["away_team"])), axis=1
)
 
print("Done.")

full_data["rank_diff"] = full_data["home_rank"] - full_data["away_rank"]
full_data["points_diff"] = full_data["home_points"] - full_data["away_points"]

output_cols = [
    "date", "home_team", "away_team",
    "home_score", "away_score", "result",
    "tournament", "neutral",
    "home_rank", "away_rank", "rank_diff",
    "home_points", "away_points", "points_diff",
    "home_form", "away_form"
]
 
full_data[output_cols].to_csv("matches_with_rankings.csv", index=False)
 
print(f"\n Saved: matches_with_rankings.csv")
print(f"  Rows: {len(full_data):,}")
print(f"  Columns: {len(output_cols)}")
print(f"\nSample row:")
print(full_data[output_cols].dropna().tail(3).to_string())