import imaplib
import email
from email.header import decode_header
import webbrowser
import os
import sched
import time
import email
import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from CommSys.Packet import Packet, SYNC_WORD, MIN_PACKET_SIZE, PacketError

class EmailHandler():
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.mail = imaplib.IMAP4_SSL('imap.gself.mail.com')
        (retcode, capabilities) = self.mail.login(self.username, self.password)
        self.mail.select("INBOX")

        self.emailPort = 465  # For SSL
        self.context = ssl.create_default_context()

    def clean(text):
        # clean text for creating a folder
        return "".join(c if c.isalnum() else "_" for c in text)

    def recieve_packet(self):
        status, messages = self.mail.uid('search', None, "UNSEEN")
        numUnread = len(messages[0].split())

        if(numUnread == 0):
            print("NO UNREAD MESSAGES")

        else:
            print(numUnread)
            print(messages)

        for i in range(numUnread):
            # fetch the eself.mail message by ID
            uid = messages[0].split()[i]
            res, msg = self.mail.fetch(uid, "(RFC822)")
            for response in msg:
                if isinstance(response, tuple):
                    # parse a bytes eself.mail into a message object
                    msg = email.message_from_bytes(response[1])
                    # decode the eself.mail subject
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        # if it's a bytes, decode to str
                        subject = subject.decode(encoding)
                    # decode eself.mail sender
                    From, encoding = decode_header(msg.get("From"))[0]
                    if isinstance(From, bytes):
                        From = From.decode(encoding)
                    print("Subject:", subject)
                    print("From:", From)
                    # if the eself.mail message is multipart
                    if msg.is_multipart():
                        # iterate over eself.mail parts
                        for part in msg.walk():
                            # extract content type of eself.mail
                            content_type = part.get_content_type()
                            content_disposition = str(
                                part.get("Content-Disposition"))
                            try:
                                # get the eself.mail body
                                body = part.get_payload(decode=True).decode()
                            except:
                                pass
                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                # print text/plain eself.mails and skip attachments
                                print("BODY")
                                print(body)
                            elif "attachment" in content_disposition:
                                print("ATTATCHMENT")
                                print(part.get_payload(decode=True))
                                # download attachment
                                # filename = part.get_filename()
                                # if filename:
                                #     folder_name = clean(subject)
                                #     if not os.path.isdir(folder_name):
                                #         # make a folder for this eself.mail (named after the subject)
                                #         os.mkdir(folder_name)
                                #     filepath = os.path.join(folder_name, filename)
                                #     # download attachment and save it
                                #     open(filepath, "wb").write(
                                #         part.get_payload(decode=True))
                    else:
                        # extract content type of eself.mail
                        content_type = msg.get_content_type()
                        # get the eself.mail body
                        body = msg.get_payload(decode=True).decode()
                        if content_type == "text/plain":
                            # print only text eself.mail parts
                            print(body)
                    if content_type == "text/html":
                        # if it's HTML, create a new HTML file and open it in browser
                        folder_name = self.clean(subject)
                        if not os.path.isdir(folder_name):
                            # make a folder for this eself.mail (named after the subject)
                            os.mkdir(folder_name)
                        filename = "index.html"
                        filepath = os.path.join(folder_name, filename)
                        # write the file
                        open(filepath, "w").write(body)
                    print("="*100)

    def write_packet(self, packet: Packet):
        with smtplib.SMTP_SSL("smtp.gmail.com", self.emailPort, context=self.context) as server:
            server.login(self.username, self.password)

            # TODO: Send email here
            sender_email = "iridium.yanglab@gmail.com"
            receiver_email = "data@sbd.iridium.com"
            subject = "300434065957410"

            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = receiver_email
            message["Subject"] = subject

            data = os.getcwd() + '\\WebGUI\\hello-world.sbd'

            with open(data, 'w') as f:
                f.write('Hello World my name is Triton!')

            with open(data, "rb") as attachment:
                # Add file as application/octet-stream
                # Email client can usually download this automatically as attachment
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())

            encoders.encode_base64(part)

            # Add header as key/value pair to attachment part
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= message.sbd",
            )

            message.attach(part)
            text = message.as_string()

            server.sendmail(sender_email, receiver_email, text)

    def logout(self):
        self.mail.close()
        self.mail.logout()
