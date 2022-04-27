import imaplib
import logging
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

# EmailHandler.py
#
# Last updated: 04/26/2022
# Allows the landbase to communiate with satellite via email. Packets can be sent using write_packet and
# an email will be created and sent using the gmail information that it is provided. Any messges sent from
# the satellite will be delievered to the email registered with the satellite. The email will have an attatchment
# that contains the body of the message. The read_packet function that will read any unread emails and if they are
# from the iridium service, it will try to read the message and turn it in to a packet that is able to be read
# by the CommSys
#
# TODO List:
# - Verify with satellite


logger = logging.getLogger(__name__)


class EmailHandler():
    def __init__(self, username, password):
        self.reliable = True
        self.username = username
        self.password = password
        self.mail = imaplib.IMAP4_SSL('imap.gmail.com')

        self.emailPort = 465  # For SSL
        self.context = ssl.create_default_context()

    def start(self):
        (retcode, capabilities) = self.mail.login(self.username, self.password)
        self.mail.select("INBOX")

    def clean(text):
        # clean text for creating a folder
        return "".join(c if c.isalnum() else "_" for c in text)

    def read_packets(self):
        recieved_packets = []

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
                                message = part.get_payload(decode=True)
                                print(message)
                                # Try to make a packet from read_buf
                                try:
                                    packet = Packet(data=message)
                                    if packet.checksum == packet.calc_checksum():
                                        # Valid packet was created
                                        recieved_packets.append(packet)
                                        message = message[(
                                            packet.length + MIN_PACKET_SIZE):]
                                    else:
                                        logger.debug(f"SerialHandler dropped packet (ID: {packet.id}) due to invalid checksum. "
                                                     f"Expected: {packet.checksum}, Actual: {packet.calc_checksum()}")
                                        logger.debug(
                                            f"Bad packet: {packet.to_binary()[0:32]}")
                                        # Force jump to next syncword
                                        self.read_buf = self.read_buf[len(
                                            SYNC_WORD):]
                                except PacketError as e:
                                    pass
                                except ValueError:  # Invalid MsgType was given
                                    logger.debug(
                                        f"SerialHandler dropped packet due to invalid MsgType")
                                    # Force jump to next syncword
                                    self.read_buf = self.read_buf[len(
                                        SYNC_WORD):]

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
                    print("="*100)
        return recieved_packets

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

            data = os.getcwd() + '\\CommSys\\message.sbd'

            with open(data, 'wb') as f:
                f.write(packet.to_binary())

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

    def close(self):
        self.logout()

    def logout(self):
        self.mail.close()
        self.mail.logout()
