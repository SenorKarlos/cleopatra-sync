import pymysql
import requests
import schedule
import time
import json
import toml
import os

# Load configuration
config = toml.load('config.toml')

source_db_config = config['source_db']
destination_db_config = config['destination_db']
discord_config = config['discord']

discord_webhook_url = discord_config['webhook_url']

state_file = 'sync_state.json'
pending_activations_file = 'pending_activations.json'

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
    pending_activations = load_state(pending_activations_file)
    
    last_id = state.get('last_id', 0)
    
    # Connect to source database
    source_conn = pymysql.connect(**source_db_config)
    source_cursor = source_conn.cursor()
    
    # Get new records from source
    created_query = f"SELECT id, username, password, refresh_token, activated FROM accounts WHERE id > {last_id} ORDER BY id ASC"
    source_cursor.execute(created_query)
    created_rows = source_cursor.fetchall()
    
    # Check for any pending activations
    pending_ids = ','.join(map(str, pending_activations.keys()))
    if pending_ids:
        activation_query = f"SELECT id, username, password, refresh_token FROM accounts WHERE id IN ({pending_ids}) AND activated = 1"
        source_cursor.execute(activation_query)
        activated_rows = source_cursor.fetchall()
    else:
        activated_rows = []
    
    if created_rows or activated_rows:
        new_last_id = last_id
        
        # Connect to destination database
        dest_conn = pymysql.connect(**destination_db_config)
        dest_cursor = dest_conn.cursor()
        
        # Track created and activated accounts
        created_count = 0
        activated_count = 0
        
        for row in created_rows:
            account_id, username, password, refresh_token, activated = row
            created_count += 1
            new_last_id = max(new_last_id, account_id)
            
            if activated == 1:
                # Insert into destination
                activated_count += 1
                dest_query = ("INSERT IGNORE INTO account (username, password, provider, refresh_token) "
                              "VALUES (%s, %s, 'nk', %s)")
                dest_cursor.execute(dest_query, (username, password, refresh_token))
            else:
                # Add to pending activations
                pending_activations[account_id] = {'username': username, 'password': password, 'refresh_token': refresh_token}
        
        for row in activated_rows:
            account_id, username, password, refresh_token = row
            activated_count += 1
            # Insert into destination
            dest_query = ("INSERT IGNORE INTO account (username, password, provider, refresh_token) "
                          "VALUES (%s, %s, 'nk', %s)")
            dest_cursor.execute(dest_query, (username, password, refresh_token))
            # Remove from pending activations
            if account_id in pending_activations:
                del pending_activations[account_id]
        
        dest_conn.commit()
        
        # Update state
        state['last_id'] = new_last_id
        state['lifetime_created'] = state.get('lifetime_created', 0) + created_count
        state['lifetime_activated'] = state.get('lifetime_activated', 0) + activated_count
        state['lifetime_sent'] = state.get('lifetime_sent', 0) + activated_count
        
        save_state(state_file, state)
        save_state(pending_activations_file, pending_activations)
        
        # Close connections
        dest_cursor.close()
        dest_conn.close()
    
    source_cursor.close()
    source_conn.close()
    
    # Send Discord notification
    send_discord_notification(state, created_count, activated_count)

# Function to send Discord notification
def send_discord_notification(state, hourly_created, hourly_activated):
    embed = {
        "username": "Cleopatra",
        "avatar_url": "https://cdn.vectorstock.com/i/preview-1x/48/31/icon-head-cleopatra-vector-4434831.jpg",
        "embeds": [{
            "title": "Cleopatra Status Summary",
            "thumbnail": {
                "url": "https://archives.bulbagarden.net/media/upload/thumb/1/1c/0149Dragonite.png/250px-0149Dragonite.png"
            },
            "fields": [
                {"name": "Lifetime Created", "value": str(state['lifetime_created']), "inline": True},
                {"name": "Lifetime Activated", "value": str(state['lifetime_activated']), "inline": True},
                {"name": "Lifetime Sent", "value": str(state['lifetime_sent']), "inline": True},
                {"name": "Hourly Created", "value": str(hourly_created), "inline": True},
                {"name": "Hourly Activated", "value": str(hourly_activated), "inline": True}
            ],
            "color": 7506394  # Blue color
        }]
    }
    requests.post(discord_webhook_url, json=embed)

# Schedule the sync to run hourly
schedule.every().hour.at(":00").do(sync_data)

# Run the scheduler
while True:
    schedule.run_pending()
    time.sleep(1)
