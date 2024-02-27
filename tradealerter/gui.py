""" GUI for showing new orders"""
import threading
import queue
from queue import Empty
from datetime import datetime
import PySimpleGUI as sg
import time
import pandas as pd
from discord_webhook import DiscordWebhook
from tradealerter.check_orders import orders_check
from tradealerter.configurator import cfg


DEV = cfg['alert_configs'].getboolean('DEV')
NORDERS = int(cfg['alert_configs']['norders'])

def reformat_date(date:str, in_form="%Y-%m-%d %H:%M:%S.%f", out_form="%m/%d %H:%M:%S")->str:
    dt = datetime.strptime(date, in_form)
    return dt.strftime(out_form)

def layout():
    tab1_els = [
        [sg.Button('Copy', key=f'-COPY{i}-', visible=False),sg.Push(),
        sg.Text(key=f'-DATE{i}-', text_color='black', visible=False), 
        sg.Text(key=f'-ORDER{i}-', visible=False), sg.Push(),
        sg.Button('Send', key=f'-SEND{i}-', visible=False)
        ] for i in range(NORDERS)
        ]
    tab1_els =[[sg.Text('Top is most recent, if a BTO is sent, the STC will be sent automatically')]]+tab1_els
    tab1 = sg.Tab("Last Orders", tab1_els)
    tab2 = sg.Tab("Parsed Orders", [        
        [sg.Text('List of Orders')],            
            [sg.Stretch()],
            ])
    # Initial layout
    tab_group_layout = [[tab1]]
    tab_group = sg.TabGroup(tab_group_layout)

    # Create the main layout
    layout = [[tab_group]]
    return layout

def send_order(order, port):  
    sent = False
    if len(cfg['discord']['webhook']):
        webhook = DiscordWebhook(
            url=cfg['discord']['webhook'], 
            username=cfg['discord']['webhook_name'], 
            content= order['alert'], 
            rate_limit_retry=True)
        response = webhook.execute()
        print("webhook alert sent")
        sent = True
    
    if sent:
        order['status'] = 'Sent'
        if order['alert'].startswith('BTO'):
            port.loc[order['port_ix'], 'BTOs-sent'] += 1
        elif order['alert'].startswith('STC'):
            port.loc[order['port_ix'], 'STCs-sent'] += 1
    return order


def gui():
    orders_queue = queue.Queue(maxsize=20) # list with alert, date and port ix
    ord_checker = orders_check(orders_queue)
    thread_orders = threading.Thread(target=ord_checker.check_orders, args=(1, DEV,), daemon=True)

    window = sg.Window('Trade Alerter', layout(), resizable=True, finalize=True)

    thread_orders.start()
    last_orders  = []
    last_items = []
    # Event Loop
    while True:
        event, values = window.read(1)

        # If user closes window or clicks cancel
        if event == sg.WINDOW_CLOSED:
            break

        try:
            new_order, date, port_ix = orders_queue.get(False)
            if port_ix is None:
                print("skipping as not in port", new_order)
                continue
            trade = ord_checker.port.loc[port_ix]
            if new_order.startswith("BTO"):
                if cfg['alert_configs']['send_all_BTOs']:
                    status = "do_send"
                elif (pd.Series(trade['BTOs-sent']) - trade['BTO-n']).lt(0).all():
                    status = "Send"
                else:
                    status = "Sent"
            elif new_order.startswith("STC"):
                # if not sent and but BTO not sent
                if pd.isna(trade['BTOs-sent']):
                    status = "Send"
                # if not sent and but BTO already sent
                elif (pd.Series(trade['STCs-sent']) - trade['STC-n']).lt(0).all() and \
                    (pd.Series(trade['BTOs-sent']) - trade['BTO-n']).ge(0).all():
                    status = "do_send"
                else:
                    status = "Send"
            
            order = {'alert': new_order, 'date': reformat_date(date), 'port_ix': port_ix, 'status': status}
            last_items.insert(0,order)
        
            for i in range(min([len(last_items),NORDERS])):
                color = "aquamarine4" if last_items[i]['alert'].startswith('BTO') else "indianred"
                status = last_items[i]['status']
                window[f'-COPY{i}-'].update(visible=True)
                window[f'-ORDER{i}-'].update(visible=True,value=last_items[i]['alert'], text_color =color, background_color='white')
                window[f'-DATE{i}-'].update(visible=True,value=last_items[i]['date'])                
                window[f'-SEND{i}-'].update(visible=True, disabled=(status=='Sent'), text=status)                
                if status == "do_send":
                    last_items[i] = send_order(last_items[i], ord_checker.port)
                    ord_checker.save_portfolio()
                    status = last_items[i]['status']
                    window[f'-SEND{i}-'].update(visible=True, disabled=(status=='Sent'), text=status)
                window.refresh()
                
        except Empty:
            pass
        
        # If copy button is clicked
        if event.startswith('-SEND'):
            # Get the index of the clicked button to retrieve the order
            index = int(event[-2]) 
            last_items[index] = send_order(last_items[index], ord_checker.port)
            ord_checker.save_portfolio()
            status = last_items[i]['status']
            window[f'-SEND{index}-'].update(disabled=(status=='Sent'), text=status)
            window.refresh()
        
        # If copy button is clicked
        if event.startswith('-COPY'):
            # Get the index of the clicked button
            index = int(event[5:-1])  
            # If there's at leaast nth order, copy to clipboard
            if len(last_items) and len(last_items) >= index:  
                sg.clipboard_set(last_items[index]['alert'])  

    window.close()

if __name__ == '__main__':
    gui()