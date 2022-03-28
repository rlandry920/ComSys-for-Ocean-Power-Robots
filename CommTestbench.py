from CommSys.Packet import Packet, MsgType, MIN_PACKET_SIZE
from CommSys.CommHandler import CommHandler, CommMode
import time
import logging
import serial
from CommSys.SerialHandler import PacketReaderThread


logging.basicConfig(filename='testbench.log',
                    level=logging.DEBUG,
                    format='%(asctime)s | %(funcName)s | %(levelname)s | %(message)s')

# General test bench parameters
window_size = 8
tx_timeout = 4

comm_handler: CommHandler


# Print iterations progress
# From https://stackoverflow.com/questions/3173320/text-progress-bar-in-terminal-with-block-characters
def printProgressBar(iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█', printEnd="\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=printEnd)
    # Print New Line on Complete
    if iteration == total:
        print()


# ---------------------------------------------- /// PACKET LOSS TEST /// ----------------------------------------------
packet_loss_data_amount_kb = 10  # Kilobytes
packet_loss_packet_size = 256  # Bytes
packet_loss_reliable = False
packet_loss_num_packets = int(packet_loss_data_amount_kb * 1000 / packet_loss_packet_size)


def packet_loss_test():
    print("-------------- Packet Loss Test ---------------")
    while True:
        user_in = input('"Sender" or "Receiver"? ')
        if user_in == "Sender":
            packet_loss_sender()
            break
        elif user_in == "Receiver":
            packet_loss_receiver()
            break
        else:
            print("Unknown input.")


def packet_loss_sender():
    global comm_handler
    print("----- / Packet Loss Test: Sender / -----")
    handshake_packet = Packet(MsgType.HANDSHAKE)
    test_packet = Packet(MsgType.IMAGE, data=b'A' * packet_loss_packet_size)
    stop_packet = Packet(MsgType.TEXT, data=b'STOP')
    comm_handler = CommHandler(tx_timeout=tx_timeout, window_size=window_size, reliable_img=packet_loss_reliable)

    # Handshake
    print("Connecting to receiver...")
    comm_handler.send_packet(handshake_packet)
    comm_handler.start(CommMode.HANDSHAKE)

    print("Connection established! Starting test...")
    printProgressBar(0, packet_loss_num_packets, printEnd='')

    # Send image packets
    for i in range(packet_loss_num_packets):
        test_packet.pid = i
        test_packet.checksum = test_packet.calc_checksum()
        comm_handler.send_packet(test_packet)
        printProgressBar(i + 1, packet_loss_num_packets, printEnd='')

    # Send stop packet
    comm_handler.send_packet(stop_packet)

    print('Test complete!')
    print("Check receiver's terminal for results.")
    comm_handler.stop()


def packet_loss_receiver():
    global comm_handler
    print("---- / Packet Loss Test: Receiver / ----")
    comm_handler = CommHandler(tx_timeout=tx_timeout, window_size=window_size, reliable_img=packet_loss_reliable)

    # Handshake
    print("Connecting to sender...")
    comm_handler.start(CommMode.HANDSHAKE)

    print("Connection established! Starting test...")
    comm_handler.rx_base = 0
    printProgressBar(0, latency_num_packets, printEnd='')

    # Receive and evaluate packets until stop packet
    bad_count = 0
    good_count = 0
    while True:
        if comm_handler.recv_flag():
            in_packet: Packet = comm_handler.recv_packet()

            if in_packet.type == MsgType.IMAGE:
                # Verify checksum
                if in_packet.checksum != in_packet.calc_checksum():
                    bad_count += 1
                else:
                    good_count += 1

                printProgressBar(good_count + bad_count, packet_loss_num_packets, printEnd='')
            elif in_packet.type == MsgType.TEXT and in_packet.data == b'STOP':
                break
            else:
                print("WARNING: Unexpected packet received!")

    # Evaluate
    total_recv = bad_count + good_count

    print("Test complete!")
    print(f"Packets received: {total_recv}/{packet_loss_num_packets}")
    if total_recv > 0:
        print(f'Uncorrupted packets: {good_count}')
        print(f"Corrupt packets received by application: {bad_count}, %.2f percent" % ((bad_count / total_recv) * 100))
    comm_handler.stop()


# ---------------------------------------------- /// THROUGHPUT TEST /// -----------------------------------------------
throughput_data_amount_kb = 10  # Kilobytes
throughput_packet_size = 256  # Bytes
throughput_num_packets = int((1000 * throughput_data_amount_kb) / throughput_packet_size)


def throughput_test():
    print("--------------- Throughput Test ---------------")
    print(f'Total data amount: {throughput_data_amount_kb} KB')
    print(f'Packet size: {throughput_packet_size} Bytes')
    while True:
        user_in = input('"Sender" or "Receiver"? ')
        if user_in == "Sender":
            throughput_sender()
            break
        elif user_in == "Receiver":
            throughput_receiver()
            break
        else:
            print("Unknown input.")


def throughput_sender():
    global comm_handler
    print("----- / Throughput Test: Sender / ------")
    handshake_packet = Packet(MsgType.HANDSHAKE)
    test_packet = Packet(MsgType.TEXT, data=b'A' * throughput_packet_size)
    comm_handler = CommHandler(tx_timeout=tx_timeout, window_size=window_size)

    # Handshake
    print("Connecting to receiver...")
    comm_handler.send_packet(handshake_packet)
    comm_handler.start(CommMode.HANDSHAKE)

    print("Connection established! Starting test...")
    printProgressBar(0, throughput_num_packets, printEnd='')
    start_time = time.time()
    for i in range(throughput_num_packets):
        comm_handler.send_packet(test_packet)

    print(f'All packets have been accepted by the sender - check receiver for results.')
    print(f'Waiting for stop notification from receiver...')

    while not comm_handler.recv_flag():
        pass

    comm_handler.stop()


def throughput_receiver():
    global comm_handler
    print("---- / Throughput Test: Receiver / -----")
    comm_handler = CommHandler(tx_timeout=tx_timeout, window_size=window_size)

    # Handshake
    print("Connecting to sender...")
    comm_handler.start(CommMode.HANDSHAKE)

    print("Connection established! Starting test...")
    printProgressBar(0, throughput_num_packets, printEnd='')
    start_time = time.time()

    # Wait until all packets have been received
    recv_packets = 0
    while recv_packets != throughput_num_packets:
        update = False
        while comm_handler.recv_flag():
            recv_packets += 1
            comm_handler.recv_packet()
            update = True

        if update:
            printProgressBar(recv_packets, throughput_num_packets, printEnd='')

    time_elapsed = time.time() - start_time
    throughput = throughput_data_amount_kb / time_elapsed

    print(f'Test complete!')
    print(f'Time elapsed: {int(time_elapsed / 60)} min, {int(time_elapsed % 60)} seconds.')
    print("Throughput: %.2f KBps" % throughput)
    comm_handler.stop()


# ------------------------------------------------ /// LATENCY TEST /// ------------------------------------------------
latency_num_packets = 20
latency_packet_size = 32  # Bytes


def latency_test():
    print("----------------- Latency Test ----------------")
    while True:
        user_in = input('"Sender" or "Receiver"? ')
        if user_in.lower() == "sender":
            latency_sender()
            break
        elif user_in.lower() == "receiver":
            latency_receiver()
            break
        else:
            print("Unknown input.")


def latency_sender():
    global comm_handler
    print("------- / Latency Test: Sender / -------")
    handshake_packet = Packet(MsgType.HANDSHAKE)
    test_packet = Packet(MsgType.TEXT, data=b'A' * latency_packet_size)
    comm_handler = CommHandler(tx_timeout=tx_timeout, window_size=window_size)

    # Handshake
    print("Connecting to receiver...")
    comm_handler.send_packet(handshake_packet)
    comm_handler.start(CommMode.HANDSHAKE)

    print("Connection established! Starting test...")

    rtt_measurements = []

    for i in range(latency_num_packets):
        # Send packet and start timer
        print(f'Packet #{i} ', end='')
        start_time = time.time()
        comm_handler.send_packet(test_packet)

        # Wait for echo
        while not comm_handler.recv_flag():
            pass
        comm_handler.recv_packet()  # clear echo from in_queue

        # Record data
        elapsed_time = time.time() - start_time
        rtt_measurements.append(elapsed_time)

        print("<ACKd RTT: %.4f seconds, size %i bytes>" % (elapsed_time, latency_packet_size))

    total_time = sum(rtt_measurements)
    avg_RTT = total_time / latency_num_packets

    print(f'Test complete!')
    print(f'Total time: {int(total_time / 60)} min {int(total_time % 60)} sec')
    print("Average RTT: %.4f seconds" % avg_RTT)
    comm_handler.stop()


def latency_receiver():
    global comm_handler
    print("------ / Latency Test: Receiver / ------")
    comm_handler = CommHandler(tx_timeout=tx_timeout, window_size=window_size)

    # Handshake
    print("Connecting to sender...")
    comm_handler.start(CommMode.HANDSHAKE)

    print("Connection established! Starting test...")
    # Wait until all packets have been received
    recv_packets = 0
    while recv_packets != latency_num_packets:
        if comm_handler.recv_flag():
            recv_packets += 1
            echo_request = comm_handler.recv_packet()
            print(f"Packet #{recv_packets} received. Echoing...")
            comm_handler.send_packet(echo_request)

    print('Test complete!')
    print("Check sender's terminal for results")
    comm_handler.stop()


# ------------------------------------------------ /// SERIAL TEST /// ------------------------------------------------
use_raw_serial = False
serial_num_packets = 10
serial_packet_size = 32  # Bytes


def serial_test():
    print("----------------- Serial Test ----------------")
    while True:
        user_in = input('"Sender" or "Receiver"? ')
        if user_in.lower() == "sender":
            serial_sender()
            break
        elif user_in.lower() == "receiver":
            serial_receiver()
            break
        else:
            print("Unknown input.")


def serial_sender():
    test_packet = Packet(MsgType.TEXT, data=b'A' * serial_packet_size)

    ser = serial.Serial("/dev/ttyAMA0", baudrate=115200)
    if not use_raw_serial:
        reader = PacketReaderThread()
        reader.start()

    expected_data_size = serial_num_packets * (serial_packet_size + MIN_PACKET_SIZE)  # bytes

    try:
        start_time = time.time()
        for i in range(serial_num_packets):
            if use_raw_serial:
                a = time.time()
                ser.write(test_packet.to_binary())
                b = time.time()
            else:
                a = time.time()
                reader.write_packet(test_packet)
                b = time.time()
            print(f'Packet #{i + 1} - Serial write time = %.4f seconds' % (b - a))
        end_time = time.time()
        print(f'Time taken: %.4f seconds. Throughput: %.4f bytes/second' % ((end_time-start_time),
                                                                            (expected_data_size/(end_time-start_time))))

    except KeyboardInterrupt:
        pass
    finally:
        if not use_raw_serial:
            reader.close()


def serial_receiver():
    ser = serial.Serial("/dev/ttyAMA0", baudrate=115200)
    if not use_raw_serial:
        reader = PacketReaderThread()
        reader.start()

    expected_data_size = serial_num_packets * (serial_packet_size + MIN_PACKET_SIZE)  # bytes
    received_data_size = 0
    last_packet_timestamp = time.time()
    try:
        while received_data_size < expected_data_size:
            if use_raw_serial:
                a = time.time()
                read_len = ser.inWaiting()
                read_chars = ser.read(read_len)
                b = time.time()
                if read_len > 0:
                    received_data_size += read_len
                    print(f'Read {read_len} bytes in %.4f seconds. {received_data_size}/{expected_data_size}' % (b - a))

            else:
                a = time.time()
                packet = reader.read_packet()
                b = time.time()
                if packet is not None:
                    print(f'Read {packet.length + MIN_PACKET_SIZE} byte long packet in %.4f seconds. '
                          f'Time since last read packet was %.4f seconds.' % ((b - a), (b - last_packet_timestamp)))
                    last_packet_timestamp = b
                    received_data_size += packet.length + MIN_PACKET_SIZE
    except KeyboardInterrupt:
        pass
    finally:
        if not use_raw_serial:
            reader.close()


if __name__ == "__main__":
    try:
        while True:
            user_in = input('Please select which test you would like to run -'
                            '"Throughput", "Packet Loss", "Serial", or "Latency": ')
            if user_in == "Throughput":
                throughput_test()
                break
            elif user_in == "Packet Loss":
                packet_loss_test()
                break
            elif user_in == "Latency":
                latency_test()
                break
            elif user_in == "Serial":
                serial_test()
                break
            else:
                print("Unknown input.")
    except KeyboardInterrupt:
        print("Stopping...")
        comm_handler.stop()
