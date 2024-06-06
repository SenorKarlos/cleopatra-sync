## Cleopatra-Sync

Simple quiet utility which will sync your accounts automatically, track stats and post to discord on the hour.

## Setup

1. Python 3 Required. Install the required Python packages:
  ```bash
  pip install -r requirements.txt
  ```

2. Copy the example configuration file and fill in your own details:
  ```bash
  cp config.toml.example config.toml
  ```
  
3. Edit `config.toml` with your database and Discord webhook details.

4. Run the script: `python cleo_sync.py` or start in in a process manager or screen. Adjust as necessary for your enviroment.