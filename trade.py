import requests
import time
import json
from datetime import datetime, timedelta

from tqdm import tqdm
from pathlib import Path
import concurrent.futures
import functools

def get_market_data(server_name, item_id):
    url = f"https://universalis.app/api/history/{server_name}/{item_id}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        market_board_sales = [entry for entry in data['entries'] if not entry['onMannequin']]
        
        daily_revenue = 0
        total_quantity = 0
        
        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)

        for entry in market_board_sales:
            purchase_time = datetime.fromtimestamp(entry['timestamp'])
            if purchase_time >= one_day_ago:
                daily_revenue += entry['pricePerUnit'] * entry['quantity']
                total_quantity += entry['quantity']

        data['daily_revenue'] = daily_revenue
        data['total_quantity'] = total_quantity
        return data
    else:
        return None


def get_item_name_from_xivapi(item_id):
    url = f"https://xivapi.com/Item/{item_id}?columns=Name"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data["Name"]
    else:
        return None


def get_item_name_from_cafemaker(item_id):
    url = f"https://cafemaker.wakingsands.com/Item/{item_id}"
    headers = {"Content-Language": "zh"}  # 设置语言为简体中文
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        
        return response.json()['Name']
    else:
        return None
    
def get_item_name(item_id):
    name = get_item_name_from_cafemaker(item_id)
    if name is None or name.strip() == "":
        name = get_item_name_from_xivapi(item_id)
    return name
    

def fetch_item(item_id, server_name):
    item_data = get_market_data(server_name, item_id)
    if item_data:
        item_name = get_item_name(item_id)
        daily_revenue, total_quantity = item_data['daily_revenue'], item_data['total_quantity']
        return {
            'id': item_id,
            'name': item_name,
            'daily_revenue': daily_revenue,
            'total_quantity': total_quantity
        }
    else:
        return None

def get_top_items(server_name, item_ids):
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        fetch_item_partial = functools.partial(fetch_item, server_name=server_name)
        items = list(tqdm(executor.map(fetch_item_partial, item_ids), total=len(item_ids), desc="Fetching items"))

    top_items = [item for item in items if item is not None]
    return top_items



def save_item_ids_to_file(item_ids, file_path):
    with open(file_path, 'w') as f:
        json.dump(item_ids, f)

def load_item_ids_from_file(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def calculate_daily_revenue_and_quantity(recent_history):
    now = datetime.now()
    one_day_ago = now - timedelta(days=1)
    daily_revenue = 0
    total_quantity = 0

    for entry in recent_history:
        entry_time = datetime.fromtimestamp(entry['timestamp'])
        if entry_time >= one_day_ago:
            daily_revenue += entry['quantity'] * entry['pricePerUnit']
            total_quantity += entry['quantity']
        else:
            break

    return daily_revenue, total_quantity

def save_top_items_to_txt(top_items, file_path, key='daily_revenue'):
    with open(file_path, 'w', encoding='utf-8') as f:
        if key=='daily_revenue':
            f.write('昨日猫小胖服务器交易金额前二十\n')
            for item in top_items:
                f.write(f"物品名称: {item['name']} - 交易金额: {item[key]}\n")
        elif key=='total_quantity':
            f.write('昨日猫小胖服务器交易量前二十\n')
            for item in top_items:
                f.write(f"物品名称: {item['name']} - 交易量: {item[key]}\n")
        

def is_Sat():
    return datetime.today().weekday() == 5


def get_all_marketable_item_ids():
    url = "https://universalis.app/api/marketable"
    response = requests.get(url)
    if response.status_code == 200:
        all_item_ids = response.json()
        filtered_item_ids = [item_id for item_id in all_item_ids if item_id > 34000]
        return filtered_item_ids
    else:
        return None

def read(file_path):
    with open(file_path, 'r',encoding="utf-8") as f:
        return f.read()
    
if __name__ == "__main__":
    server_name = "猫小胖"
    item_ids_file = "item_ids.json"
    previous_day_file_revenue = "previous_day_top50_revenue.json"
    previous_day_file_quantity = "previous_day_top50_quantity.json"
    results_file_revenue = "top_items_revenue.txt"
    results_file_quantity = "top_items_quantity.txt"

    if is_Sat() or not Path(item_ids_file).exists():
        item_ids = get_all_marketable_item_ids()
        if item_ids:
            save_item_ids_to_file(item_ids, item_ids_file)
        else:
            print("Failed to fetch marketable item IDs.")
            exit(1)
    else:
        item_ids = load_item_ids_from_file(item_ids_file)

    if not is_Sat() and (Path(previous_day_file_revenue).exists() and Path(previous_day_file_quantity).exists()):
        previous_top_items_revenue = load_item_ids_from_file(previous_day_file_revenue)
        previous_top_items_quantity = load_item_ids_from_file(previous_day_file_quantity)
        item_ids = list(set([item['id'] for item in previous_top_items_revenue] + [item['id'] for item in previous_top_items_quantity]))

    top_items = get_top_items(server_name, item_ids)

    top_items_revenue = sorted(top_items, key=lambda x: x['daily_revenue'], reverse=True)[:50]
    save_top_items_to_txt(top_items_revenue[:20], results_file_revenue, key='daily_revenue')
    save_item_ids_to_file(top_items_revenue, previous_day_file_revenue)

    top_items_quantity = sorted(top_items, key=lambda x: x['total_quantity'], reverse=True)[:50]
    save_top_items_to_txt(top_items_quantity[:20], results_file_quantity, key='total_quantity')
    save_item_ids_to_file(top_items_quantity, previous_day_file_quantity)

