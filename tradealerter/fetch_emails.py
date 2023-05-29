import os

from tradealerter.configurator import cfg


import email
import imaplib

EMAIL = 'adonay.s.nunes@gmail.com'
PASSWORD = 'xucsnnnwrycvelyy'
SERVER = 'imap.gmail.com'

mail = imaplib.IMAP4_SSL(SERVER)
mail.login(EMAIL, PASSWORD)
mail.select('tda')
status, data = mail.search(None, 'ALL')
mail_ids = []
for block in data:
    mail_ids += block.split()

for i in mail_ids:
    status, data = mail.fetch(i, '(RFC822)')
    for response_part in data:
        if isinstance(response_part, tuple):
            message = email.message_from_bytes(response_part[1])
            mail_from = message['from']
            if "tdameritrade.com"  in mail_from:
                print('From : ' + mail_from + '\n')
            
            mail_subject = message['subject']
            if message.is_multipart():
                mail_content = ''

                for part in message.get_payload():
                    if part.get_content_type() == 'text/plain':
                        mail_content += part.get_payload()
            else:
                mail_content = message.get_payload()
            print(f'From: {mail_from}')
            print(f'Subject: {mail_subject}')
            print(f'Content: {mail_content}')
            

"You bought to open 14 contracts of AMD May 26 2023 104 Put at $0.69 on 05/24/2023"