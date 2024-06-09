import pymysql
import requests
import schedule
import time
import json
import toml
import os
import sys

# Load configuration
config = toml.load('config.toml')

source_db_config = config['source_db']
destination_db_config = config['destination_db']
discord_webhook_url = config['discord'].get('webhook_url', "")
dragonite_config = config['dragonite']

dragonite_api_url = dragonite_config.get('api_url', "")
use_admin = dragonite_config.get('use_admin', False)
admin_secret = dragonite_config.get('admin_secret', "")
reload_every_run = dragonite_config.get('reload_every_run', False)

state_file = 'sync_state.json'

# Function to load state
def load_state(file):
    if not os.path.exists(file):
        return {}
    with open(file, 'r') as f:
        return json.load(f)

# Function to save state
def save_state(file, state):
    with open(file, 'w') as f:
        json.dump(state, f)

# Function to sync data
def sync_data():
    state = load_state(state_file)
    
    total_created_prev = state.get('total_created', 0)
    total_activated_prev = state.get('total_activated', 0)
    
    # Connect to source database
    source_conn = pymysql.connect(**source_db_config)
    source_cursor = source_conn.cursor()
    
    # Get all records from source
    source_query = "SELECT username, password, activated FROM accounts"
    source_cursor.execute(source_query)
    rows = source_cursor.fetchall()
    
    total_created = len(rows)
    created_count = total_created - total_created_prev

    activated_rows = [row for row in rows if row[2] == 1]  # Filter where activated = 1
    total_activated = len(activated_rows)
    activated_count = total_activated - total_activated_prev
    
    if activated_rows and destination_db_config.get('host', ""):
        # Connect to destination database
        dest_conn = pymysql.connect(**destination_db_config)
        dest_cursor = dest_conn.cursor()
        
        for row in activated_rows:
            username, password = row[0], row[1]
            # Insert into destination
            dest_query = ("INSERT IGNORE INTO account (username, password, provider) "
                          "VALUES (%s, %s, 'nk')")
            dest_cursor.execute(dest_query, (username, password))
        
        dest_conn.commit()
        
        # Close connections
        dest_cursor.close()
        dest_conn.close()
    
    source_cursor.close()
    source_conn.close()
    
    # Update state
    state['total_created'] = total_created
    state['total_activated'] = total_activated
    
    save_state(state_file, state)
    
    # Send Discord notification if webhook URL is provided
    if discord_webhook_url:
        send_discord_notification(total_created_prev, state, created_count, activated_count, destination_db_config.get('host', ""))

    # Reload Dragonite if needed and API URL is provided
    if dragonite_api_url and (reload_every_run or activated_count > 0):
        reload_dragonite()

# Function to send Discord notification
def send_discord_notification(total_created_prev, state, hourly_created, hourly_activated, destination_db_host):
    if total_created_prev == 0:
        hourly_created_msg = "First Run - N/A"
        hourly_activated_msg = "First Run - N/A"
    else:
        hourly_created_msg = str(hourly_created)
        hourly_activated_msg = str(hourly_activated)

    if destination_db_config.get('host', ""):
        embed_fields = [
            {"name": ":calendar_spiral: **Lifetime Statistics**", "value": "----------------------"},
            {"name": "Lifetime Created", "value": str(state['total_created']), "inline": True},
            {"name": "Lifetime Activated/Sent", "value": str(state['total_activated']), "inline": True},
            {"name": ":clock1: **Hourly Statistics**", "value": "----------------------"},
            {"name": "Hourly Created", "value": hourly_created_msg, "inline": True},
            {"name": "Hourly Activated/Sent", "value": hourly_activated_msg, "inline": True}
        ]
    else:
        embed_fields = [
            {"name": ":calendar_spiral: **Lifetime Statistics**", "value": "----------------------"},
            {"name": "Lifetime Created", "value": str(state['total_created']), "inline": True},
            {"name": "Lifetime Activated", "value": str(state['total_activated']), "inline": True},
            {"name": ":clock1: **Hourly Statistics**", "value": "----------------------"},
            {"name": "Hourly Created", "value": hourly_created_msg, "inline": True},
            {"name": "Hourly Activated", "value": hourly_activated_msg, "inline": True}
        ]

    embed = {
        "username": "Cleopatra",
        "avatar_url": "https://cdn.vectorstock.com/i/preview-1x/48/31/icon-head-cleopatra-vector-4434831.jpg",
        "embeds": [{
            "title": "Cleopatra Status Summary",
            "thumbnail": {
                "url": "https://archives.bulbagarden.net/media/upload/thumb/1/1c/0149Dragonite.png/250px-0149Dragonite.png"
            },
            "fields": embed_fields,
            "color": 16766720  # Gold color
        }]
    }
    
    requests.post(discord_webhook_url, json=embed)

# Function to reload Dragonite
def reload_dragonite():
    if use_admin:
        api_endpoint = f"{dragonite_api_url}/api/reload/accounts"
    else:
        api_endpoint = f"{dragonite_api_url}/reload/accounts"

    headers = {}
    if use_admin and admin_secret:
        headers['Authorization'] = f"Bearer {admin_secret}"

    response = requests.post(api_endpoint, headers=headers)
    
    if response.status_code == 200:
        print("Successfully reloaded Dragonite.")
    else:
        print(f"Failed to reload Dragonite. Status code: {response.status_code}")

# Ensure at least one function is enabled
if not destination_db_config.get('host', "") and not discord_webhook_url:
    print("No functions enabled. Please provide at least one of destination database host or Discord webhook URL.")
    sys.exit()

# Ensure source db is configured
if not source_db_config.get('host', ""):
    print("No source database, please check configuration.")
    sys.exit()

# Schedule the sync to run hourly
schedule.every().hour.at(":00").do(sync_data)

# Run the scheduler
while True:
    schedule.run_pending()
    time.sleep(1)
