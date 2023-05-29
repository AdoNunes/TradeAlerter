
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

2. In the PowerShell terminal navigate to the directory where you want to clone the TradeAlerter package, e.g. type: `cd Desktop`.

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

7. Run the software by typing in the terminal:
    ```shell 
    python -c'from tradealerter.gui import gui; gui()'
    ```

**Setup eTrade API**

Create a sandbox (mock) api key:
https://us.etrade.com/etx/ris/apikey

To get the production (real) keys, fill out the forms at the bottom of:
https://developer.etrade.com/getting-started


**Setup gmail api**

1. Go to `https://console.developers.google.com/` and search for `gmail API`, click on it and enable it.
2. In Gmail API, go on the left section and click Credentials, on the top click `+ create credentials` and then `OAuth client ID`.
Application type, select Web applicaiton, chose a name, and click create on the bottom. 
Download the JSON file to /tradealerter and save it as `gmail_api_keys.json`