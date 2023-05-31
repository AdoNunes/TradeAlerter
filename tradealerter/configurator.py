import configparser
import os
import os.path as op

package_dir = os.path.abspath(os.path.dirname(__file__))

config_path = package_dir + '/config.ini'
if not os.path.exists(config_path):
    print("\033[91mWARNING: DiscordAlertsTrader/config.ini not found. \033[0m")
    print("\033[91mWARNING: Rename DiscordAlertsTrader/config_example.ini to DiscordAlertsTrader/config.ini. \033[0m")
    print("\033[91mWARNING: Reverting to config_example.ini for now (might be necessary for testing). \033[0m")
    config_path = package_dir + '/config_example.ini'

# load configuration file
cfg = configparser.ConfigParser()
cfg.read(config_path, encoding='utf-8')
cfg['paths']= {'root': package_dir,
               'data': op.join(package_dir,'data')}
os.makedirs(op.join(cfg['paths']['data']), exist_ok=True)