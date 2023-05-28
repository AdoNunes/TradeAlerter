
## Installation and Setup
 ______________________________

1. Install Python:
   - For Windows, open PowerShell and run the following command, verify that it prints out "Hello World!":
     ```powershell
     if (-not (Test-Path $env:USERPROFILE\scoop)) {
         # Install Scoop
         Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
         irm get.scoop.sh | iex
     }
     scoop install git
     # Check if extras are included
     $extras = scoop bucket list | Select-String -Pattern '^extras$'
     if (-not $extras) {
         # Add the extras bucket    
         scoop bucket add extras
     }
     # Install Miniconda3
     scoop install miniconda3     
     # Check python is installed
     python -c "print('Hello, World!')"
     ```

2. In the PowerShell terminal navigate to the directory where you want to clone the DiscordAlertsTrader package, e.g. type: `cd Desktop`.

3. Clone the package from the GitHub repository and install the package and its dependencies using pip:
   ```shell
   git clone https://github.com/AdoNunes/TradeAlerter.git
   cd TradeAlerter
   pip install -e .
   ```

5. Copy the example configuration file to `config.ini`:
   ```shell
   cp tradealerter/config_example.ini tradealerter/config.ini
   ```

6. Edit the `tradealerter/config.ini` file to add your brokerage keys:
   - Add your eTrade api keys, see next section for instructions
   - (Optional) Modify string_add_to_alert to add a text at the end of the alert
   - (Optional) If you have a TDA API, add it to the configuration.

**Setup eTrade API**
