import zipfile
import shutil
from os import getenv
from re import compile, match, findall
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "Data"
SAVE_FILES_DIR = DATA_DIR / "save_files"
PARSED_SAVE_DIR = DATA_DIR / "parsed_save_files"
PROVINCE_DATA_PATH = DATA_DIR / "provinces_stage2.csv"

load_dotenv(PROJECT_ROOT / ".env")
eu4_install_location = getenv("EU4_INSTALL_LOCATION")
if not eu4_install_location:
    raise RuntimeError(
        "EU4_INSTALL_LOCATION is not defined. Add it to the project's .env file."
    )

EU4_DIR = Path(eu4_install_location)
TAGS_FILE = EU4_DIR / "common" / "country_tags" / "00_countries.txt"
DESIRABLE_PROVINCE_DATA = ["num_of_times_developed_var", "owner", "controller", ]

df_provinces = pd.read_csv(PROVINCE_DATA_PATH)

class ProvinceDevelopment():
    def __init__(self, tax = 0, production = 0, manpower = 0):
        self.tax = tax
        self.production = production
        self.manpower = manpower
    def get_total_development(self):
        return self.tax + self.production + self.manpower
class ProvinceContext():
    def __init__(self, identifier = None, development = None, in_buildings_section = False, in_history_section = False, changed_owner_num = 0, changed_controller_num = 0, num_buildings = 0, current_owner = None, development_clicks = 0):
        self.identifier = identifier
        self.development = ProvinceDevelopment() if development is None else development
        self.in_history_section = in_history_section
        self.in_buildings_section = in_buildings_section
        self.changed_owner_num = changed_owner_num
        self.changed_controller_num = changed_controller_num
        self.num_buildings = num_buildings
        self.current_owner = current_owner
        self.development_clicks = development_clicks
    def get_old_development(self):
        row = df_provinces.loc[df_provinces["province_id"] == self.identifier]
        if row.empty:
            self.development = ProvinceDevelopment(0, 0, 0)
        else:
            assert len(row) == 1, f"Expected one source row for province {self.identifier}, found {len(row)}"
            source = row.iloc[0]
            self.development = ProvinceDevelopment(int(source.base_tax), int(source.base_production), int(source.base_manpower))
        return
    def store(self, save_context):
        if self.development.tax == 0 or self.development.production == 0 or self.development.manpower == 0:
            self.get_old_development()
        save_context.provinces.append(self)
        return save_context
class SaveFileGamestateContext():
    def __init__(self, prev_line = '', in_players_countries = False, in_province = None, player_countries = None, players = None, provinces = None, done = False):
        self.prev_line = prev_line
        self.in_players_countries = in_players_countries
        self.in_province = in_province
        self.player_countries = [] if player_countries is None else player_countries
        self.players = [] if players is None else players
        self.provinces = [] if provinces is None else provinces
        self.done = done
    def finalise(self):
        assert(self.done)
        self.players_countries_list = list(zip(self.players, self.player_countries))
        player_by_country = dict(zip(self.player_countries, self.players))
        list_of_provinces_dicts = []
        for province in self.provinces:
            list_of_provinces_dicts.append({"id": province.identifier, "new_tax": province.development.tax, "new_production": province.development.production, "new_manpower": province.development.manpower,
                                            "changed_owner_num": province.changed_owner_num, "changed_controller_num": province.changed_controller_num, "num_buildings": province.num_buildings,
                                            "current_owner": province.current_owner, "development_clicks": province.development_clicks,
                                            "is_player_owned": province.current_owner in player_by_country, "player": player_by_country.get(province.current_owner)})
        self.provinces = pd.DataFrame(list_of_provinces_dicts)
        self.provinces["save"] = self.file_name
        self.provinces["is_test_save"] = self.file_name.startswith("Test " )
        return

def extract_country_tags():
    tags = []
    with open(TAGS_FILE) as file:
        for line in file.readlines():
            line = line.strip()
            if line.startswith("#") or len(line) < 3:
                continue
            else:
                tags.append(line[0:3])    
    return tags

def extract_eu4_save(save_path, output_dir):
    save_path = Path(save_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    destination = output_dir / f"{save_path.name}-gamestate"

    try:
        with zipfile.ZipFile(save_path, "r") as archive:
            if "gamestate" not in archive.namelist():
                raise FileNotFoundError(
                    f"{save_path.name} does not contain a gamestate file"
                )

            with archive.open("gamestate") as source:
                with destination.open("wb") as target:
                    shutil.copyfileobj(source, target)

    except zipfile.BadZipFile:
        print(f"{save_path.name} is not a compressed EU4 save.")
        return None

    return destination

# Clear the generated extraction directory before producing the new set.
PARSED_SAVE_DIR.mkdir(parents=True, exist_ok=True)
for old_file in PARSED_SAVE_DIR.iterdir():
    if old_file.is_file():
        old_file.unlink()

extracted_files = []
for save_path in SAVE_FILES_DIR.glob("*.eu4"):
    extracted_path = extract_eu4_save(save_path, PARSED_SAVE_DIR)
    if extracted_path is not None:
        extracted_files.append(extracted_path)

print(f"Extracted {len(extracted_files)} saves")
tags = extract_country_tags()

PLAYER_FLAG = "players_countries={"
PROVINCE_FLAG = compile(r'(-\d{1,4}={)')
COUNTRY_FLAG = "countries={"
CLOSE_SCOPE = "}"
OWNER_CHANGE_REGEX = compile(r'^owner="(\w{3})"$')
DEVELOPMENT_CLICKS_KEYS = {"num_of_times_developed_var", "num_of_times_developed"}
CONTROLLER_OPEN_SCOPE_REGEX = r'controller={'
TAG_ASSIGNMENT_REGEX = compile(r'(tag="\w{3}")')
YEAR_SCOPE = compile(r'(\d{4}.\d{1,2}.\d{1,2}={)')
BUILDINGS = ["courthouse", "town_hall", "university", "workshop", "counting_house", "temple", "cathedral", "marketplace", "trade_depot", "stock_exchange", "dock", "drydock", "shipyard", "grand_shipyard", "coastal_defence", "naval_battery", "barracks", "training_fields", "regimental_camp", "conscription_center", "fort_15th", "fort_16th", "fort_17th", "fort_18th", "farm_estate", "weapons", "textile", "plantations", "tradecompany", "mills", "wharf", "furnace", "state_house", "naval_equipment_manufactory"]
HISTORY_SECTION = r'history={'
BUILDINGS_SECTION = r'buildings={'

def identify_line(line, context):
    if line is None or line == '' or line.startswith('#'):
        context.prev_line = line
        return context # Empty line or commented out
    if line == PLAYER_FLAG:
        context.in_players_countries = True
        context.prev_line = line
        return context
    if line == CLOSE_SCOPE:
        if context.in_players_countries:
            context.in_players_countries = False
            context.prev_line = line
            return context
    if context.in_players_countries:
        if line.startswith('"') and line.endswith('"'):
            tag_or_player = line.strip('"')
            if tag_or_player in tags:
                tag = tag_or_player
                context.player_countries.append(tag)
            else: 
                player = tag_or_player
                context.players.append(player)
        context.prev_line = line
        return context
    if match(PROVINCE_FLAG, line):
        if context.in_province is not None:
            context.in_province.store(context)
        identifier = int(line.lstrip("-").rstrip("={"))
        province = ProvinceContext(identifier)
        context.in_province = province
        context.prev_line = line
        return context
    if context.in_province is not None:
        if line == CLOSE_SCOPE and context.in_province.in_buildings_section:
            context.in_province.in_buildings_section = False
            context.prev_line = line
            return context
        if context.in_province.in_buildings_section:
            if '=' in line:
                key, value = line.split('=', 1)
                if key in BUILDINGS and value == 'yes':
                    context.in_province.num_buildings += 1
            context.prev_line = line
            return context
        if '=' in line:
            key, value = line.split('=', 1)
            if key in DEVELOPMENT_CLICKS_KEYS:
                context.in_province.development_clicks = int(float(value))
                context.prev_line = line
                return context
        owner_match = match(OWNER_CHANGE_REGEX, line)
        if owner_match:
            owner_tag = owner_match.group(1)
            if not context.in_province.in_history_section and context.in_province.current_owner is None:
                context.in_province.current_owner = owner_tag
            else:
                context.in_province.changed_owner_num += 1
            context.prev_line = line
            return context
        if line == CONTROLLER_OPEN_SCOPE_REGEX:
            context.prev_line = line
            return context
        if context.prev_line == CONTROLLER_OPEN_SCOPE_REGEX and match(TAG_ASSIGNMENT_REGEX, line):
            context.in_province.changed_controller_num += 1
            return context
        if line == HISTORY_SECTION:
            context.in_province.in_history_section = True
            context.prev_line = line
            return context
        if context.in_province.in_history_section == False:
            if '=' in line:
                parts = line.split("=")
                key = parts[0]
                value = parts[1]
                if line.startswith("base"):
                    if key == 'base_tax' and context.in_province.development.tax == 0:
                        context.in_province.development.tax = int(float(value))
                    if key == 'base_production' and context.in_province.development.production == 0:
                        context.in_province.development.production = int(float(value))
                    if key == 'base_manpower' and context.in_province.development.manpower == 0:
                        context.in_province.development.manpower = int(float(value))
                if line == BUILDINGS_SECTION:
                    context.in_province.in_buildings_section = True
                context.prev_line = line
                return context
    if line == COUNTRY_FLAG:
        if context.in_province is not None:
            context.in_province.store(context)
        context.done = True
        context.prev_line = line
        return context
    context.prev_line = line
    return context

saves = []
for file_path in extracted_files:
    with file_path.open(encoding="utf-8", errors="replace") as file:
        context = SaveFileGamestateContext()
        context.file_name = file_path.name.removesuffix(".eu4-gamestate")

        for line in file:
            context = identify_line(line.strip(), context)
            if context.done:
                break

        if not context.done:
            raise ValueError(
                f"Could not find the countries section while parsing {file_path.name}"
            )

        context.finalise()
        saves.append(context)
all_saves_provinces = pd.DataFrame()
for save in saves:
    all_saves_provinces = pd.concat([all_saves_provinces, save.provinces], ignore_index=True)
all_saves_provinces = all_saves_provinces.rename(columns={"id": "province_id"})

source_provinces = df_provinces.drop(
    columns="Unnamed: 0",
    errors="ignore",
).copy()

all_saves_provinces["province_id"] = (
    all_saves_provinces["province_id"].astype(int)
)
source_provinces["province_id"] = source_provinces["province_id"].astype(int)

joined_dfs = all_saves_provinces.merge(
    source_provinces,
    how="left",
    left_on="province_id",
    right_on="province_id",
    suffixes=("_save", "_original"),
    validate="many_to_one",
)

LEGACY_VALUE_DEFINERS = ["changed_tax", "changed_production", "changed_manpower", "changed_owner_num", "num_buildings"]
TARGET_COLUMN = "investment_preference_target"

joined_dfs["changed_tax"] = joined_dfs["new_tax"] - joined_dfs["base_tax"].fillna(0).astype(int)
joined_dfs["changed_production"] = joined_dfs["new_production"] - joined_dfs["base_production"].fillna(0).astype(int)
joined_dfs["changed_manpower"] = joined_dfs["new_manpower"] - joined_dfs["base_manpower"].fillna(0).astype(int)
joined_dfs["legacy_heuristic_score"] = joined_dfs[LEGACY_VALUE_DEFINERS].sum(axis=1)

# The behavioral target is defined only where a real save province is currently
# owned by a human player and has a matching source-data row. Test saves are
# retained for parser checks but excluded from model labels.
joined_dfs["has_source_data"] = joined_dfs["name"].notna()
joined_dfs["target_eligible"] = (
    joined_dfs["is_player_owned"]
    & ~joined_dfs["is_test_save"]
    & joined_dfs["has_source_data"]
)
joined_dfs[TARGET_COLUMN] = np.nan
eligible = joined_dfs["target_eligible"]
joined_dfs.loc[eligible, TARGET_COLUMN] = (
    joined_dfs.loc[eligible]
    .groupby(["save", "current_owner"])["development_clicks"]
    .rank(method="average", pct=True)
)

joined_dfs["high_investment_target"] = pd.NA
joined_dfs.loc[eligible, "high_investment_target"] = (
    joined_dfs.loc[eligible, TARGET_COLUMN] >= 0.75
).astype(int)

LEAKAGE_COLUMNS = [
    "development_clicks", "new_tax", "new_production", "new_manpower",
    "changed_tax", "changed_production", "changed_manpower",
    "num_buildings", "changed_owner_num", "changed_controller_num",
    "legacy_heuristic_score", TARGET_COLUMN, "high_investment_target",
]
training_df = joined_dfs.loc[eligible].copy()
joined_dfs.to_csv(DATA_DIR / "provinces_stage3.csv")
