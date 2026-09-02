from pathlib import Path
from os import getenv, listdir 
from os.path import sep, isdir
import pandas as pd
from re import compile, search, match
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
DESIRED_PROV_DATA = ['owner', 'culture', 'religion', 'hre', 'base_tax', 'base_production', 'trade_goods', 'base_manpower', 'capital', 'is_city', 'center_of_trade']
EU4_DIR = getenv("EU4_INSTALL_LOCATION")
SEPARATOR = sep
PROV_HISTORY_DIR = EU4_DIR + SEPARATOR + 'history' + SEPARATOR + 'provinces'
TRADE_NODES_PATH = EU4_DIR + SEPARATOR + 'common' + SEPARATOR + 'tradenodes' + SEPARATOR + '00_tradenodes.txt'
NODE_NAME_REGEX = compile(r'\b(?!color\b)(?!outgoing\b)(?!path\b)(?!control\b)(?!members\b)\w+=\{')
MEMBERS_LIST_REGEX = compile(r'(members={)')
NUMBERS_IN_MEMBERS_LIST_REGEX = compile(r'\w+(\d+)\w')

assert(isdir(EU4_DIR))
class TradenodeFileContext():
    def __init__(self, node_data = None, inland = False, end_node = False, location = None, members = None, trade_node = '', in_members_segment = False):
        self.node_data = [] if node_data is None else node_data
        self.inland = inland
        self.end_node = end_node
        self.location = location
        self.members = [] if members is None else members
        self.trade_node = trade_node
        self.in_members_segment = in_members_segment
        return
    def store(self):
        self.node_data.append(self.trade_node, self.inland, self.end_node, len(self.members), self.location)
        return
def clean_and_extract_filename(filename):
    if '-' not in filename:
        reg = compile(r'\D\w+')
        name_start = search(reg, filename).start()
        filename = filename[:name_start] + '-' + filename[name_start:]
    path_no_spaces = filename.replace(' ', '')
    path_no_ext = path_no_spaces.split('.')[0]
    path_id_name = path_no_ext.split('-')
    province_id = path_id_name[0]
    province_name = path_id_name[1]
    return filename, province_id, province_name
def identify_and_clean_line(line):
    line = line.strip()
    line = line.replace('"', '')
    if '#' in line:
        return None, None
    if len(line) < 1:
        return None, None
    args = line.split(' ')
    if len(args) != 3:
        return None, None
    key = args[0]
    value = args[2]
    return key, value
def read_province_file(path, filename):
    filename, province_id, province_name = clean_and_extract_filename(filename)
    province_dict = {}
    with open(path) as file:
        for line in file:
            key, value = identify_and_clean_line(line)
            if key in DESIRED_PROV_DATA and key not in province_dict.keys():
                province_dict.update({key: value})
    for expected_key in DESIRED_PROV_DATA:
        if expected_key not in province_dict.keys():
            province_dict.update({expected_key: None})
    province_dict.update({'name': province_name, 'id': province_id})
    return province_dict
data = []
for file in listdir(PROV_HISTORY_DIR):
    province_dict = read_province_file(PROV_HISTORY_DIR + SEPARATOR + file, file)
    data.append(province_dict)
df = pd.DataFrame(data)
df.index = df.index.astype(int)
df = df.sort_index()

df['owner'] = df['owner'].fillna('Unowned')
df['culture'] = df['culture'].fillna('Unowned')
df['religion'] = df['religion'].fillna('Unowned')
df['hre'] = df['hre'].fillna('no')
df['base_tax'] = df['base_tax'].fillna(0)
df['base_production'] = df['base_production'].fillna(0)
df['base_manpower'] = df['base_manpower'].fillna(0)
df['capital'] = df['capital'].fillna(df['name'])
df['is_city'] = df['is_city'].fillna('no')
df['center_of_trade'] = df['center_of_trade'].fillna(0)

def process_tradenode_file_line(context, line):
    if match(NODE_NAME_REGEX, line):
        if len(context.trade_node) > 0:
            context.node_data.append([context.trade_node, context.inland, context.end_node, len(context.members), context.location])
        # Initialise all node values
        context.inland = False
        context.end_node = False
        context.location = None
        context.members = []
        context.trade_node = line.strip().rstrip('={') # Remove whitespace before removing ={
        return context
    if match(MEMBERS_LIST_REGEX, line):
        context.in_members_segment = True
        return context
    if context.in_members_segment and match(NUMBERS_IN_MEMBERS_LIST_REGEX, line):
        for member in line.strip().split(' '):
            context.members.append(member)
        for member in context.members:
            df.loc[df['id'] == member, 'trade_node'] = context.trade_node
        in_members_segment = False
        return context
    try:
        split_line = line.split('=')
    except:
        assert('=' not in line)
    if 'split_line' in locals() and len(split_line) > 0:
        if split_line[0].strip() == 'inland' and split_line[1].strip() == 'yes':
            context.inland = True
            return context
        if split_line[0].strip() == 'end' and split_line[1].strip() == 'yes':
            context.end_node = True
            return context
        if split_line[0].strip() == 'location':
            context.location = int(split_line[1].strip())
    if context.in_members_segment and '}' in line and not match(NUMBERS_IN_MEMBERS_LIST_REGEX, line):
        context.in_members_segment = False
    return context


df['trade_node'] = None
context = TradenodeFileContext()
with open(TRADE_NODES_PATH) as nodefile:
    for line in nodefile:
        line = line.strip()
        context = process_tradenode_file_line(context, line)
df_trade_nodes = pd.DataFrame(data=context.node_data, columns=['name', 'inland', 'end_node', 'member_count', 'location'])
df.to_csv('../data/provinces_stage1.csv')