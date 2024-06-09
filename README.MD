## Cleopatra-Sync

Simple quiet utility which will sync your accounts automatically, track stats and post to discord on the hour (:00) every hour.

It only produces log output on crashes, dragonite reloads and misconfiguration exits.

It can run in sync only mode, stats only mode, or both.

## Setup

1. Python 3 Required. Install the required Python packages:
  ```bash
  pip install -r requirements.txt
  ```

2. Copy the example configuration file and fill in your own details:
  ```bash
  cp config.toml.example config.toml
  ```
  
3. Edit `config.toml` with your database, Discord webhook details and dragonite api details. The example states required and optional settings.

4. Run the script: `python cleo_sync.py` or start in in a process manager or screen. Adjust as necessary for your enviroment.