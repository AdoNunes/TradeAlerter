""" GUI for showing new orders"""
import threading
import queue
from queue import Empty
from datetime import datetime
import PySimpleGUI as sg

from tradealerter.check_orders import orders_check

DEV = True

def reformat_date(date:str, in_form="%Y-%m-%d %H:%M:%S.%f", out_form="%m/%d %H:%M:%S")->str:
    dt = datetime.strptime(date, in_form)
    return dt.strftime(out_form)

def gui():
    orders_queue = queue.Queue(maxsize=20)
    ord_checker = orders_check(orders_queue)
    thread_orders =  threading.Thread(target=ord_checker.check_orders, args=(1, DEV,), daemon=True)

    # Initial layout
    layout = [[sg.Text('Last Orders, top is most recent')],
            [[
                sg.Button('Copy', key=f'-COPY{i}-'),
                sg.Text(key=f'-DATE{i}-', text_color='black'), 
                sg.Text(key=f'-ORDER{i}-'), sg.Push(),
                sg.Button('Send', key=f'-SEND{i}-', visible=False)] for i in range(5)
                ] + 
            [sg.Stretch()],
            ]

    window = sg.Window('Trade Alerter', layout, resizable=True, finalize=True)

    thread_orders.start()
    last_orders, last_dates = [], []
    # Event Loop
    while True:
        event, values = window.read(1)

        # If user closes window or clicks cancel
        if event == sg.WINDOW_CLOSED:
            break

        try:
            new_order, date = orders_queue.get(False)
            print(new_order)        
            last_orders.insert(0,new_order)
            last_dates.insert(0, reformat_date(date))
            prev_disab, prev_txt = False, 'Send'
            for i in range(min([len(last_orders),5])):
                color = "green" if last_orders[i].startswith('BTO') else "red"
                window[f'-ORDER{i}-'].update(value=last_orders[i], text_color =color, background_color='white')
                window[f'-DATE{i}-'].update(value=last_dates[i])
                next_state =  window[f'-SEND{i}-'].get_text()
                if "STC" in last_orders[i]:
                    window[f'-SEND{i}-'].update(visible=True, disabled=True, text='Sent')
                else:
                    window[f'-SEND{i}-'].update(visible=True, disabled=prev_disab, text=prev_txt)
                prev_disab, prev_txt = next_state == 'Sent', next_state
        except Empty:
            pass
        
        # If copy button is clicked
        if event.startswith('-SEND'):
            # Get the index of the clicked button
            index = int(event[-2]) 
            window[f'-SEND{index}-'].update(disabled=True, text='Sent')
            
        # If copy button is clicked
        if event.startswith('-COPY'):
            # Get the index of the clicked button
            index = int(event[-2])  
            # If there's at leaast nth order, copy to clipboard
            if len(last_orders) and len(last_orders) >= index:  
                sg.clipboard_set(last_orders[index])  

    window.close()

if __name__ == '__main__':
    gui()