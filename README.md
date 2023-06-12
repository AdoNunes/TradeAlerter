# Trade Alerter #

This Package provides real-time trade notifications using brokerage APIs (currently supporting etrade). It instantly alerts you when a stock or option buy or sell order is executed, ensuring efficient trade alerting. You can either copy the text alert or send it if you have a webhook (soon send it as a discord user). Don't waste time typing trade alerts manually - start using TradeAlerter to effortlessly share your alerts on Discord without typos and delays!


### Key Features:
**Instant Trade Notifications**: Send real-time (for real) alerts for filled orders without delay.

**Automated Sell Alerts**: Automatically send sell alerts (STC) if the buy alert (BTO) was sent.

**Discord Integration**: Effortlessly send trade alerts to your designated Discord channel. Eliminate the need for manual alerts in Discord servers.



### Upcoming Features:
**Expanded Brokerage Support**: Integration with more brokerages and monitor order fills through emails.

**Automated Buy Alerts**: Choose between automatic buy-to-open (BTO) orders or set a specific number of alerts to be sent automatically.

**Discord User Alerts**: Send trade alerts directly as a Discord user, simplifying the process further.

**Advanced STC Details**: Include additional information in STC alerts such as bought price, profit, and more.


This app can help to reduce delays in trade alerts, this is crucial for momentum trading. Traders alerting trades in discord servers should NOT send alerts manually!

Contact me if you want the upcoming features faster :)


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

##Setup eTrade API
__________________

Create a sandbox (mock) api key (you must be logged in in another tab before clicking the link):
https://us.etrade.com/etx/ris/apikey

To get the production (real) keys, fill out the forms at the bottom of:
https://developer.etrade.com/getting-started


Disclaimer
_________

The code and package provided in this repository is provided "as is" and without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the author or contributors be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the code or package or the use or other dealings in the code or package.

Please use this code and package at your own risk. The author and contributors disclaim all liability and responsibility for any errors or issues that may arise from its use. It is your responsibility to test and validate the code and package for your particular use case.
