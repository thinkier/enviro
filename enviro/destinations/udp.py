from enviro import logging
from enviro.constants import UPLOAD_SUCCESS, UPLOAD_FAILED
import socket
import ujson as json
import config

def log_destination():
  logging.info(f"> uploading cached readings to udp server: {config.custom_udp_server}")

def upload_reading(reading):
  ip, port = config.custom_udp_server.split(":")

  try:
    # post reading data to udp endpoint
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = json.dumps(reading)
    sock.sendto(payload, (ip, int(port)))

    return UPLOAD_SUCCESS
  except:
    logging.debug(f"  - an exception occurred when uploading")

  return UPLOAD_FAILED

